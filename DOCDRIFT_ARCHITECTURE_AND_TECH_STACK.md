# 🧭 DocDrift: Architecture, Tech Stack & System Reference Guide

> **Version-Aware RAG Engine with Real-Time Drift Detection, Grounded Citation Inspector, and Multi-Version Documentation Isolation.**

---

## 📖 Table of Contents
1. [Executive Summary & Problem Statement](#-executive-summary--problem-statement)
2. [Complete Tech Stack Breakdown](#-complete-tech-stack-breakdown)
3. [End-to-End System Architecture](#-end-to-end-system-architecture)
4. [Core Features & How Each Functionality Works](#-core-features--how-each-functionality-works)
   - [1. Multi-Format Ingestion & Semantic Chunking](#1-multi-format-ingestion--semantic-chunking)
   - [2. Version-Strict Vector Retrieval & Metadata Filtering](#2-version-strict-vector-retrieval--metadata-filtering)
   - [3. Server-Sent Events (SSE) Streaming RAG Engine](#3-server-sent-events-sse-streaming-rag-engine)
   - [4. Inline Citation Tagging & Faithfulness Verifier](#4-inline-citation-tagging--faithfulness-verifier)
   - [5. Raw Document Preview & Fuzzy Offset Locator](#5-raw-document-preview--fuzzy-offset-locator)
   - [6. Version Drift & Breaking Change Diff Engine](#6-version-drift--breaking-change-diff-engine)
   - [7. Dynamic LLM & Workspace Settings Management](#7-dynamic-llm--workspace-settings-management)
   - [8. Production Security & Rate Limiting](#8-production-security--rate-limiting)
5. [API Endpoint Catalog](#-api-endpoint-catalog)
6. [Pre-Loaded Multi-Version Datasets & Seeding Script](#-pre-loaded-multi-version-datasets--seeding-script)
7. [Getting Started & Local Execution](#-getting-started--local-execution)

---

## 🎯 Executive Summary & Problem Statement

Large Language Models (LLMs) frequently hallucinate outdated APIs, mixing legacy code signatures (e.g., deprecated Stripe `charges.create` with modern `payment_intents.create`, or FastAPI `@app.on_event` with modern `lifespan`). Standard RAG implementations retrieve mixed document versions without version boundaries, giving developers subtly broken code.

**DocDrift** solves this through:
- **Version Isolation**: ChromaDB metadata filtering ensures queries only retrieve context strictly belonging to the requested software version.
- **Strict Grounding**: System prompts enforce version boundaries and mandate inline `[^chunk_id]` citation tags.
- **Automated Claim Verification**: An independent verifier calculates a 0–100% faithfulness score for every citation.
- **Version Drift & Diff Engine**: Automatically analyzes differences between two doc versions to output structured breaking changes, deprecations, and migration guides.

---

## 💻 Complete Tech Stack Breakdown

| Layer | Technologies Used | Purpose / Responsibility |
|---|---|---|
| **Backend Framework** | **FastAPI** (Python 3.10+) | High-performance asynchronous REST API and SSE streaming endpoints |
| **Data Validation & Schemas** | **Pydantic v2** & `pydantic-settings` | Request/response validation, environment settings, and data serialization |
| **Relational Database & ORM** | **SQLAlchemy 2.0 (Async)**, **PostgreSQL** / **SQLite** | Workspace, Document, Chunk, and Chat Session persistence |
| **Vector Database** | **ChromaDB** (Cosine Space HNSW) | Vector indexing with composite metadata filters (`version`, `doc_type`, `is_deprecated`) |
| **Embeddings & AI Models** | **Google Gemini 1.5** (`gemini-1.5-pro` / `text-embedding-004`), **OpenAI** (`gpt-4o` / `text-embedding-3-small`), **Deterministic Cosine Fallback** | Text embedding generation, LLM streaming inference, and offline deterministic embeddings |
| **Streaming Protocol** | **Server-Sent Events (SSE)** (`EventSourceResponse` / `StreamingResponse`) | Token-by-token real-time streaming with trailing structured JSON citation payloads |
| **Security & Middleware** | Custom Sliding-Window Rate Limiter, `X-Request-ID` tracing, API Key Redaction | DDoS prevention, error shielding, request correlation |
| **Testing & Evaluation** | **Pytest**, **TestClient**, Automated 20-Query RAG Benchmark | Integration testing, version strictness evaluation, hallucination rate scoring |
| **Deployment & Containers** | **Docker**, **Docker Compose**, **Uvicorn** | Containerized multi-service deployment with persistent volumes |

---

## 🏗️ End-to-End System Architecture

```
                                  ┌───────────────────────────────┐
                                  │      Client / Frontend        │
                                  └───────────────┬───────────────┘
                                                  │ HTTP / SSE
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FastAPI Backend                                             │
│                                                                                                  │
│  [Security Layer] ──► RequestIDMiddleware ──► RateLimitMiddleware ──► ErrorHandlerMiddleware     │
│                                                                                                  │
│  [API Routers]                                                                                   │
│   ├── /api/v1/workspaces ─────── Workspace CRUD & Multi-Tenancy                                  │
│   ├── /api/v1/documents ──────── Ingestion, Raw Preview (/raw), and Char Offset Locator           │
│   ├── /api/v1/search ─────────── Semantic, Keyword & Hybrid Search                               │
│   ├── /api/v1/chat/stream ────── Real-time SSE Token Streaming with Grounded Citations            │
│   ├── /api/v1/citations/{id} ─── Citation Inspector Context (+/- 3 lines)                        │
│   ├── /api/v1/diff ───────────── Multi-Version Drift & Breaking Change Comparison                 │
│   ├── /api/v1/settings ───────── Dynamic LLM / Embedding Config & API Key Redaction             │
│   └── /api/v1/maintenance ────── Vector Sync, Cleanup & Re-indexing                              │
│                                                                                                  │
│  [Core Services]                                                                                 │
│   ├── Markdown & OpenAPI Parsers ─── Section Header Hierarchy & Exact Line Offset Tracking      │
│   ├── Embedding Service ───────────── Google Gemini / OpenAI / Deterministic Cosine Fallback     │
│   ├── Query Intent Analyzer ──────── Target Version Extraction & Drift Detection                 │
│   ├── Citation Faithfulness Verifier ── Claim vs Source Faithfulness Scoring (0–100%)            │
│   └── Text-Offset Locator ────────── Fuzzy String Matching for Citation Highlighting            │
└─────────────────────────────────────────┬───────────────────────────────┬────────────────────────┘
                                          │                               │
                                          ▼                               ▼
                       ┌────────────────────────────┐  ┌────────────────────────────┐
                       │  PostgreSQL / SQLite DB    │  │     ChromaDB Vector Store  │
                       │  (Workspaces, Docs, Chunks)│  │     (HNSW Cosine Index)    │
                       └────────────────────────────┘  └────────────────────────────┘
```

---

## ⚙️ Core Features & How Each Functionality Works

### 1. Multi-Format Ingestion & Semantic Chunking
- **Markdown Parser (`MarkdownParser`)**: Scans document AST headers (`#` to `######`), preserving parent hierarchy tags (`['API Reference', 'Charges', 'Parameters']`), starting line numbers, and ending line numbers.
- **OpenAPI / Swagger Parser (`OpenAPIParser`)**: Deconstructs OpenAPI 3.0/3.1 JSON/YAML files into granular endpoints, HTTP methods, required parameters, and response schemas.
- **Metadata Tagging**: Each chunk is tagged with `doc_id`, `version_tag`, `doc_type`, `start_line`, `end_line`, and `section_header` for instant traceability.

### 2. Version-Strict Vector Retrieval & Metadata Filtering
When a user asks a query:
1. The **Query Intent Analyzer** determines the requested software version (e.g., `2024-04-15` or `v0.110.0`).
2. The query is converted into an embedding vector.
3. A composite ChromaDB `$where` filter is constructed:
   ```json
   {
     "$and": [
       {"version": "2024-04-15"},
       {"is_deprecated": false}
     ]
   }
   ```
4. Only chunks belonging strictly to that version are retrieved, eliminating cross-version pollution.

### 3. Server-Sent Events (SSE) Streaming RAG Engine
- **Endpoint**: `POST /api/v1/chat/stream`
- Yields SSE events formatted as:
  ```
  data: {"event": "token", "content": "To charge a card in version 2024-04-15..."}
  data: {"event": "token", "content": " use the PaymentIntents API[^chunk_123]."}
  data: {"event": "citation", "citation": {"chunk_id": "chunk_123", "doc_title": "...", "confidence": 0.95}}
  data: {"event": "done"}
  ```
- Frontends receive tokens with zero perceived latency while preserving structured metadata.

### 4. Inline Citation Tagging & Faithfulness Verifier
- The LLM is instructed by the core RAG prompt to tag every technical assertion with `[^<chunk_id>]`.
- The **Citation Faithfulness Verifier** takes the generated sentence and the source chunk content, evaluating:
  - Keyword overlap & semantic alignment
  - Numerical parameter matches (e.g., amount, timeout)
  - Negative assertion / deprecation alignment
- Returns a confidence score from **0% to 100%** with a clear verdict (`VERIFIED`, `PARTIALLY_SUPPORTED`, or `UNSUPPORTED`).

### 5. Raw Document Preview & Fuzzy Offset Locator
- **`GET /api/v1/documents/{id}/raw`**: Streams the original source document line-by-line with 1-based line numbers and section headers.
- **`POST /api/v1/documents/{id}/locate-excerpt`**: Employs difflib fuzzy matching to locate exact character start/end offsets (`start_char_offset`, `end_char_offset`) within the raw document for UI highlighting.

### 6. Version Drift & Breaking Change Diff Engine
- **Endpoint**: `POST /api/v1/diff`
- Takes two versions (e.g., `v1.0` vs `v2.0`) and a topic/endpoint.
- Concurrently retrieves relevant chunks from both versions.
- Feeds both sets of documentation to the `VERSION_DRIFT_SYSTEM_PROMPT`.
- Generates a structured JSON comparison:
  - `breaking_changes`: Removed endpoints, parameter type changes, renamed methods.
  - `deprecations`: Features planned for removal.
  - `new_features`: Additions in the newer version.
  - `migration_steps`: Direct actionable migration code snippets.

### 7. Dynamic LLM & Workspace Settings Management
- **Endpoints**: `GET/PUT /api/v1/settings` and `/api/v1/settings/workspaces/{id}`
- Allows per-workspace configuration of:
  - LLM Provider: `gemini` vs `openai`
  - Embedding Provider & Custom Dimensions
  - Chunk Size & Overlap tuning
  - Default Version Tag
  - Workspace Member Access Roles (`admin`, `editor`, `viewer`)
- **Security**: Stored API keys are automatically redacted (e.g., `sk-proj-••••••••abcd`) in all API responses.

### 8. Production Security & Rate Limiting
- **`RateLimitMiddleware`**: In-memory sliding-window rate limiter per client IP (default 120 req/min). Bypasses `/health` and `/docs`.
- **`RequestIDMiddleware`**: Automatically injects a unique `X-Request-ID` UUID on every request and response for logging and debugging.
- **`ErrorHandlerMiddleware`**: Traps unhandled exceptions and returns standardized JSON error payloads, preventing stack trace leaks.

---

## 📡 API Endpoint Catalog

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status, DB connectivity, Vector store status |
| `POST` | `/api/v1/workspaces` | Create new documentation workspace |
| `GET` | `/api/v1/workspaces` | List all workspaces |
| `GET` | `/api/v1/workspaces/{id}` | Get workspace details, documents, and versions |
| `POST` | `/api/v1/documents` | Upload and trigger background ingestion pipeline |
| `GET` | `/api/v1/documents` | List documents with workspace and version filters |
| `GET` | `/api/v1/documents/{id}/raw` | Stream raw document content with line numbers |
| `POST` | `/api/v1/documents/{id}/locate-excerpt` | Locate character start/end offsets of a chunk excerpt |
| `GET` | `/api/v1/citations/{chunk_id}` | Fetch chunk context with surrounding lines (+/- 3 lines) |
| `POST` | `/api/v1/search` | Semantic vector search with version and type filters |
| `POST` | `/api/v1/chat/stream` | SSE streaming endpoint for real-time RAG responses |
| `POST` | `/api/v1/diff` | Multi-version drift and breaking change comparison |
| `GET` | `/api/v1/settings` | Retrieve global application settings |
| `PUT` | `/api/v1/settings` | Update global settings |
| `GET` | `/api/v1/settings/workspaces/{id}` | Get workspace LLM provider and chunking config |
| `PUT` | `/api/v1/settings/workspaces/{id}` | Update workspace settings |
| `POST` | `/api/v1/maintenance/sync-vectors` | Re-index modified documents and delete obsolete vectors |

---

## 📦 Pre-Loaded Multi-Version Datasets & Seeding Script

DocDrift includes pre-loaded datasets for immediate demo readiness:

### 1. Stripe Payments API (`stripe-api`)
- **Version `2020-08-27`**: Legacy Charges API (`stripe.Charge.create`), token card sources (`tok_visa`), synchronous charging.
- **Version `2024-04-15`**: Modern PaymentIntents API (`stripe.PaymentIntent.create`), automatic payment methods, 3D Secure 2 (SCA), OpenAPI 3.0 schema.

### 2. FastAPI Framework (`fastapi-docs`)
- **Version `v0.90.0`**: Pydantic v1 validation (`@validator`), `.dict()`, `@app.on_event("startup")` lifecycle hooks.
- **Version `v0.110.0`**: Pydantic v2 validation (`@field_validator`, `.model_dump()`), async context manager `lifespan(app: FastAPI)`, `Annotated[..., Depends(...)]`.

### 3. OpenAI Python SDK (`openai-sdk`)
- **Version `v0.28.1`**: Global module configuration `openai.api_key`, `openai.ChatCompletion.create`, `openai.error` hierarchy.
- **Version `v1.0.0`**: Instantiated client `client = OpenAI()`, `client.chat.completions.create`, typed response objects, streaming iteration.

### Running the Seeding Script:
```bash
python backend/scripts/seed_demo_data.py
```

#### Seeding Output Report:
```text
================================================================================
🚀 DOCDRIFT: MULTI-VERSION DEMO DATASET SEEDING & INDEXING
================================================================================
📁 [WORKSPACE] Verified: Stripe Payments API (slug: 'stripe-api')
  📄 [INDEXED] [2020-08-27] Stripe Charges API Reference (Legacy) (8 chunks)
  📄 [INDEXED] [2024-04-15] Stripe PaymentIntents API Reference (Modern) (8 chunks)
  📄 [INDEXED] [2024-04-15] Stripe REST OpenAPI Specification v2024 (2 chunks)

📁 [WORKSPACE] Verified: FastAPI Framework Documentation (slug: 'fastapi-docs')
  📄 [INDEXED] [v0.90.0] FastAPI v0.90 Guide (Pydantic v1 & on_event) (5 chunks)
  📄 [INDEXED] [v0.110.0] FastAPI v0.110 Guide (Pydantic v2 & Lifespan) (5 chunks)

📁 [WORKSPACE] Verified: OpenAI Python SDK (slug: 'openai-sdk')
  📄 [INDEXED] [v0.28.1] OpenAI Python SDK v0.28 Reference (5 chunks)
  📄 [INDEXED] [v1.0.0] OpenAI Python SDK v1.0+ Reference (7 chunks)

⚡ Upserted 40 chunks to vector index.

================================================================================
🧪 VERIFYING MULTI-VERSION ISOLATION & SEMANTIC SEARCH
================================================================================
✅ PASS [Stripe | Version 2024-04-15] - PaymentIntent retrieved
✅ PASS [Stripe | Version 2020-08-27] - Legacy Charge retrieved
✅ PASS [FastAPI | Version v0.110.0]  - Lifespan context manager retrieved
✅ PASS [FastAPI | Version v0.90.0]   - @app.on_event handler retrieved
✅ PASS [OpenAI  | Version v1.0.0]    - OpenAI() client retrieved
✅ PASS [OpenAI  | Version v0.28.1]   - ChatCompletion.create retrieved

================================================================================
📊 DOCDRIFT DEMO SEEDING COMPLETE
================================================================================
Total Workspaces : 3
Total Documents  : 7
Total Chunks     : 40
Database Engine  : SQLite + ChromaDB Indexing
Multi-Version QA : 100% Verified
================================================================================
```

---

## 🚀 Getting Started & Local Execution

### 1. Clone Repository & Setup Environment
```bash
git clone https://github.com/kalviumcommunity/S72-RAG-DocDrift.git
cd S72-RAG-DocDrift/backend
cp .env.example .env
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Seed Demo Data
```bash
python scripts/seed_demo_data.py
```

### 4. Start the Backend Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://localhost:8000/docs`** for the interactive Swagger UI.

### 5. Run the Automated RAG Benchmark
```bash
python ai-rag/benchmark/rag_benchmark.py --host http://localhost:8000
```
Evaluates **Version Strictness**, **Citation Accuracy**, and **Hallucination Rate** across 20 test cases.
