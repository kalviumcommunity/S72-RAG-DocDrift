# DocDrift Backend

FastAPI asynchronous backend with PostgreSQL and ChromaDB for version-aware API documentation assistant.

## Features Included
- **FastAPI** with async lifespan and structured logging.
- **Pydantic v2 & Pydantic-Settings** configuration management.
- **SQLAlchemy 2.0 Async** engine & session lifecycle (`asyncpg`).
- **ChromaDB Vector Store** client connector.
- **CORS Middleware** configured for frontend integration.
- **Health Check endpoints**:
  - `GET /api/v1/health` (Deep check testing PostgreSQL & ChromaDB connectivity and latencies)
  - `GET /api/v1/health/live` (Simple liveness probe)
  - `GET /api/v1/docs` (Swagger UI documentation)
- **Docker Compose** with persistent PostgreSQL 16 and ChromaDB containers.

---

## 🚀 Running with Docker Compose

Run all services (API + PostgreSQL + ChromaDB) with a single command:

```bash
docker compose up --build
```

- API Docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- ChromaDB: [http://localhost:8001](http://localhost:8001)

---

## 💻 Running Locally (Virtual Environment)

### 1. Create and Activate Virtual Environment
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run with Uvicorn
```bash
uvicorn app.main:app --reload --port 8000
```
