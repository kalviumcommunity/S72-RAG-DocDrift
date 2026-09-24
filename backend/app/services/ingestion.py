import os
import uuid
import asyncio
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.entities import Document, DocumentChunk, DocStatusEnum
from app.services.vector_store import vector_store
from app.schemas.vector_payload import VectorChunkMetadata
from app.core.logging import logger

def simple_markdown_chunker(text: str):
    """A basic markdown chunker that splits by double newlines for simplicity."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_start_line = 1
    for i, p in enumerate(paragraphs):
        p = p.strip()
        if not p:
            continue
        line_count = len(p.split("\n"))
        chunks.append({
            "section_header": "",
            "section_level": 1,
            "start_line": current_start_line,
            "end_line": current_start_line + line_count - 1,
            "content": p,
            "tags": ["markdown"]
        })
        current_start_line += line_count + 1
    return chunks

async def process_document_pipeline(document_id: str):
    """
    Background task to process a document: parses it, chunks it, and indexes it into the vector database.
    Updates the document status in the database throughout the process.
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Fetch document
            result = await db.execute(select(Document).filter(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if not doc:
                logger.error(f"Document {document_id} not found for processing.")
                return

            # Update status to PARSING
            doc.status = DocStatusEnum.PARSING
            await db.commit()

            # 2. Parse and chunk
            if not doc.file_path or not os.path.exists(doc.file_path):
                raise ValueError("File path is invalid or file does not exist.")

            with open(doc.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            doc.raw_content = content
            
            # Here we use a simple chunker. In production, this would use the advanced MarkdownParser.
            parsed_chunks = simple_markdown_chunker(content)
            
            if not parsed_chunks:
                raise ValueError("No chunks could be extracted from the document.")

            # Update status to INDEXING
            doc.status = DocStatusEnum.INDEXING
            await db.commit()

            # 3. Save chunks to DB and Vector Store
            ids = []
            documents = []
            metadatas = []
            db_chunks = []
            
            for i, chunk_data in enumerate(parsed_chunks):
                chunk_id = str(uuid.uuid4())
                
                # DB Entity
                db_chunk = DocumentChunk(
                    id=chunk_id,
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk_data["content"],
                    embedding_id=chunk_id,
                    section_header=chunk_data.get("section_header", ""),
                    section_level=chunk_data.get("section_level", 1),
                    start_line=chunk_data.get("start_line", 1),
                    end_line=chunk_data.get("end_line", 1),
                    version_tag=doc.version_tag,
                    doc_type=doc.doc_type,
                    chunk_metadata={"tags": chunk_data.get("tags", [])}
                )
                db_chunks.append(db_chunk)
                db.add(db_chunk)

                # Vector Store Metadata
                meta = VectorChunkMetadata(
                    doc_id=doc.id,
                    version=doc.version_tag,
                    doc_type=doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type),
                    section_header=chunk_data.get("section_header", "") or "default",
                    section_level=chunk_data.get("section_level", 1),
                    start_line=chunk_data.get("start_line", 1),
                    end_line=chunk_data.get("end_line", 1),
                    file_name=doc.source_filename,
                    tags=chunk_data.get("tags", [])
                )
                
                ids.append(chunk_id)
                documents.append(chunk_data["content"])
                metadatas.append(meta)

            # Flush to get chunks saved in Postgres
            await db.flush()

            # Offload synchronous vector store indexing to threadpool
            await run_in_threadpool(vector_store.add_chunks, ids, documents, metadatas)

            # 4. Finalize
            doc.status = DocStatusEnum.INDEXED
            doc.total_chunks = len(db_chunks)
            await db.commit()
            logger.info(f"Successfully processed and indexed document {document_id}")

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}")
            await db.rollback()
            
            # Try to update status to FAILED in a new transaction
            try:
                result = await db.execute(select(Document).filter(Document.id == document_id))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = DocStatusEnum.FAILED
                    doc.error_message = str(e)
                    await db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to update document {document_id} to FAILED state: {str(inner_e)}")
