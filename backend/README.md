# Academic QA Backend

FastAPI API for authentication, academic subjects, PDF processing, conversations, and source-grounded hybrid RAG. MySQL is the relational source of truth; FAISS and BM25 indexes are stored separately on disk.

## Local setup

Requires Python 3.11+ and MySQL 8+.

```sh
cd backend
cp .env.example .env
# Set DATABASE_URL and a 32+ byte JWT_SECRET_KEY in .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Set `DATABASE_URL` to `mysql+pymysql://USER:PASSWORD@HOST:3306/academic_rag`. The database must exist before running migrations. Swagger docs are at `/docs`, ReDoc at `/redoc`, and health at `/api/health`.

### Docker MySQL

```sh
cd backend
docker compose up --build -d mysql
# after MySQL is healthy:
docker compose run --rm api alembic upgrade head
docker compose up api
```

Docker Compose exposes MySQL on port 3306, persists its data, and mounts `backend/data` for uploaded PDFs and search indexes. Configure API credentials in the root `.env` or environment.

## Database and RAG storage

Alembic owns schema changes. The first migration creates the users, subjects, knowledge bases, documents, document chunks, conversations, messages, citations, feedback, processing jobs, and search query tables. Run `alembic upgrade head` after each migration deployment. Tests use an isolated SQLite database; production uses MySQL.

Uploads are saved below `UPLOAD_DIR`. Each knowledge base has a FAISS index at `FAISS_DIR/<knowledge_base_id>/index.faiss` and ID map, plus its persisted BM25 data at `BM25_DIR/<knowledge_base_id>/index.pkl`. MySQL stores chunk text and metadata, including document ID, page, chunk index, document name, and subject ID. Retrieval verifies the authenticated user's ownership before searching and loading chunks. `SEMANTIC_WEIGHT` and `KEYWORD_WEIGHT` configure hybrid score fusion (defaults 0.7 and 0.3).

Scanned PDF pages use local Tesseract OCR, with OpenAI vision OCR as a fallback. Set `OPENAI_API_KEY` for embeddings and the default answer model, or configure `LLM_PROVIDER=groq` and `GROQ_API_KEY`. When retrieval produces no relevant chunks, chat returns `Information not found in the provided documents.` without calling an LLM.

## Document processing and deployment

When `CELERY_BROKER_URL` is configured, uploads and reprocessing are dispatched
to the Celery worker. Without a broker, the API schedules processing as an
in-process background task so single-instance deployments can still index
documents without a local Redis service. In-process tasks can be interrupted by
restarts and are not a durable production queue. Multi-instance deployments need
a reachable broker, a running worker, and shared persistent document and index
storage; a separate worker cannot use the API instance's local filesystem.

## Vercel deployment

Keep the two-project monorepo arrangement: set the frontend Vercel project root to `frontend` and the API project root to `backend`. Configure `VITE_API_BASE_URL` on the frontend and `DATABASE_URL`, `JWT_SECRET_KEY`, AI provider credentials, and `CORS_ORIGINS` on the API project. Run Alembic migrations against the hosted MySQL database as a deployment step before serving traffic.

**Storage limitation:** Vercel Functions have an ephemeral filesystem. The current backend follows the requested filesystem layout, which works for local/Docker deployments, but Vercel `/tmp` does not provide durable storage for uploaded PDFs or FAISS/BM25 indexes between function instances. A production Vercel deployment therefore needs persistent shared storage (for example, an object-storage adapter for the uploads and index artifacts) before relying on document ingestion. MySQL alone cannot persist these binary indexes under the attached specification.

Vercel Functions also limit request payload size; keep `MAX_FILE_SIZE_MB` below the platform's request limit or add direct-to-object-storage uploads for larger PDFs.
