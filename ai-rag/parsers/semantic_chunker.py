import re
from typing import List, Dict, Any

class SemanticChunker:
    """
    A semantic chunker that splits markdown by header boundaries, limits chunk sizes 
    (500-800 tokens with overlap), and prepends contextual headers for embedding.
    """
    def __init__(self, min_tokens: int = 500, max_tokens: int = 800, overlap_tokens: int = 100):
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        # Matches markdown headers # to ######
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.*)')

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate tokens. In a production environment, you should replace this 
        with tiktoken or the exact tokenizer used by your embedding model.
        Here we use a common rule of thumb: ~4 characters per token.
        """
        return len(text) // 4

    def chunk_markdown(self, text: str, doc_title: str, version: str) -> List[Dict[str, Any]]:
        """
        Splits markdown by header boundaries and token limits, prepending 
        context headers to each chunk.
        """
        lines = text.split('\n')
        chunks = []
        
        current_header = "General"
        current_chunk_lines = []
        current_tokens = 0
        current_start_line = 1
        
        def flush_chunk(lines_to_flush: List[str], header: str, start_line: int, end_line: int):
            content = '\n'.join(lines_to_flush).strip()
            if not content:
                return
                
            # Prepend contextual header as requested
            prefix = f"[Doc: {doc_title} | Version: {version} | Section: {header}]\n\n"
            final_content = prefix + content
            
            chunks.append({
                "content": final_content,
                "section_header": header,
                "start_line": start_line,
                "end_line": end_line,
                "token_estimate": self.estimate_tokens(final_content)
            })

        for i, line in enumerate(lines):
            line_num = i + 1
            header_match = self.header_pattern.match(line)
            
            if header_match:
                # Header boundary hit. Flush current chunk if it has content.
                if current_chunk_lines:
                    flush_chunk(current_chunk_lines, current_header, current_start_line, line_num - 1)
                    current_chunk_lines = []
                    current_tokens = 0
                
                current_header = header_match.group(2).strip()
                current_start_line = line_num
                current_chunk_lines.append(line)
                current_tokens += self.estimate_tokens(line + '\n')
            else:
                line_tokens = self.estimate_tokens(line + '\n')
                
                # Check if adding this line would exceed max_tokens
                if current_tokens + line_tokens > self.max_tokens and current_tokens >= self.min_tokens:
                    # Flush current chunk
                    flush_chunk(current_chunk_lines, current_header, current_start_line, line_num - 1)
                    
                    # Compute overlap from the end of current_chunk_lines
                    overlap_lines = []
                    overlap_tokens = 0
                    for overlap_line in reversed(current_chunk_lines):
                        ot = self.estimate_tokens(overlap_line + '\n')
                        if overlap_tokens + ot <= self.overlap_tokens:
                            overlap_lines.insert(0, overlap_line)
                            overlap_tokens += ot
                        else:
                            break
                            
                    current_chunk_lines = overlap_lines
                    current_tokens = overlap_tokens
                    # Adjust start line for the new chunk to reflect the overlap
                    current_start_line = line_num - len(overlap_lines)
                
                current_chunk_lines.append(line)
                current_tokens += line_tokens
                
        # Flush any remaining content at the end
        if current_chunk_lines:
            flush_chunk(current_chunk_lines, current_header, current_start_line, len(lines))
            
        return chunks
