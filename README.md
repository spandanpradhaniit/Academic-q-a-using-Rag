# 🎓 Scholar AI: Academic Question Answering System Using Hybrid RAG

[![CI Pipeline](https://github.com/spandanpradhaniit/Aaogya_jal/actions/workflows/ci.yml/badge.svg)](https://github.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB.svg)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6.svg)](https://www.typescriptlang.org)
[![Tests: 100% Passing](https://img.shields.io/badge/Tests-73%20Passed-brightgreen.svg)]()
[![Accessibility: WCAG 2.1](https://img.shields.io/badge/Accessibility-WCAG%202.1%20AA-blueviolet.svg)]()

> **Production-grade academic research assistant grounded strictly in verified course materials, lecture notes, and research papers using hybrid sparse-dense retrieval (BM25 + FAISS / Qdrant) with Reciprocal Rank Fusion (RRF), anti-hallucination verification, and exact page citations.**

---

## 🌟 Key Architecture & RAG Pipeline

```mermaid
flowchart TD
    User([User Question]) --> QRewrite[Query Expansion & Rewriter]
    QRewrite --> HybridRetriever{Hybrid Retrieval Engine}
    
    subgraph Storage ["Document Storage & Indexing"]
        PDF[Uploaded PDF Documents] --> OCR[PyMuPDF / Tesseract OCR]
        OCR --> Chunker[Semantic Page-Preserving Chunker]
        Chunker --> BM25[(BM25 Inverted Index)]
        Chunker --> VectorStore[(FAISS / Qdrant Dense Index)]
        Chunker --> DB[(PostgreSQL / Supabase / MySQL)]
    end

    HybridRetriever -->|Sparse Search| BM25
    HybridRetriever -->|Dense Embedding Search| VectorStore
    
    BM25 --> RRF[Weighted Reciprocal Rank Fusion - RRF]
    VectorStore --> RRF
    
    RRF --> RelevanceGate{Relevance Gate & Confidence Filter}
    RelevanceGate -->|Score < Threshold| Fallback["'Information not found in provided documents.'"]
    RelevanceGate -->|Score >= Threshold| Generator[LLM Answer Generator: Groq / OpenAI]
    
    Generator --> CitationVal[Citation Validator & Anti-Hallucination Guardrail]
    CitationVal --> FinalAnswer([Streaming Response with Verified Page Citations])
```

---

## ✨ Features

- **Hybrid Retrieval (BM25 + FAISS/Qdrant):** Combines exact keyword matching with semantic vector embeddings for highest academic precision.
- **Strict Evidence Guardrails:** Guarantees no hallucinated answers. If retrieved context lacks evidence, the system explicitly reports *"Information not found in the provided documents."*
- **Exact Page-Level Citations:** Every claim is backed by `[Source N]` tags referencing document title, page number, and snippet.
- **Enterprise Security Hardening:**
  - Automated security headers middleware (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`, `Strict-Transport-Security`, `Permissions-Policy`).
  - Strict input sanitization against XSS, path traversal, and HTML injection.
  - Redis-backed distributed rate limiting.
  - Zero sensitive secrets in version control.
- **Accessible & Responsive UI (WCAG 2.1 AA):** Complete ARIA labels, semantic landmark regions, keyboard shortcuts, screen reader announcements (`aria-live="polite"`), and dark/light modes.
- **Multi-Database Support:** Seamlessly runs on **Supabase (PostgreSQL)**, **Render PostgreSQL**, **MySQL**, or local **SQLite**.

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- **Node.js**: v20 or higher
- **Python**: v3.11 or higher
- **Package Managers**: `npm` and `pip`

### 2. Backend Setup (FastAPI)

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the backend API server
uvicorn app.main:app --reload --port 8000
```

- **API Base URL:** `http://localhost:8000`
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 3. Frontend Setup (React + Vite)

Open a new terminal tab:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

- **Frontend Application:** [http://localhost:5173](http://localhost:5173)

---

## 🧪 Comprehensive Automated Testing

The codebase includes an extensive automated test suite with **100% passing tests** across both frontend and backend.

```bash
# Run all Backend Pytest tests (65 unit and integration tests)
cd backend
.venv/bin/pytest -v

# Run all Frontend Vitest unit tests (8 component and page tests)
cd frontend
npm test

# Run Frontend Production Build & Typecheck
cd frontend
npm run build
```

---

## 🌐 Production Deployment Guide

### A. Deploy Frontend on Vercel

1. **Import Repository:** Go to [vercel.com](https://vercel.com) and import your GitHub repository.
2. **Project Settings:**
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. **Environment Variables:**
   - `VITE_API_BASE_URL`: `https://your-backend-app.onrender.com/api`
   - `VITE_USE_MOCKS`: `false`
4. **Deploy:** Click **Deploy**. Vercel will build and serve your SPA with automated preview URLs.

---

### B. Deploy Backend on Render

The repository includes a ready-to-deploy [`render.yaml`](render.yaml) blueprint specification:

1. **Sign in to Render:** Go to [render.com](https://render.com).
2. **New Web Service:** Select **New +** → **Web Service** (or use Blueprints and select the repository).
3. **Configuration:**
   - **Root Directory:** `backend`
   - **Runtime:** Python 3.11+
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/health`
4. **Environment Variables on Render:**
   | Variable | Example Value | Description |
   | :--- | :--- | :--- |
   | `DATABASE_URL` | `postgresql://postgres:password@db.xxx.supabase.co:5432/postgres` | Supabase or Render PostgreSQL URL |
   | `JWT_SECRET_KEY` | *(Random 32+ character string)* | Secret for auth tokens |
   | `LLM_PROVIDER` | `groq` or `openai` | Inference provider |
   | `GROQ_API_KEY` | `gsk_...` | Groq API Key |
   | `OPENAI_API_KEY` | `sk-...` | OpenAI API Key (if using OpenAI embeddings) |
   | `CORS_ORIGINS` | `https://your-app.vercel.app` | Your Vercel frontend URL |

---

### C. Connect Supabase (PostgreSQL)

1. Create a free project at [supabase.com](https://supabase.com).
2. In Supabase Dashboard → **Project Settings** → **Database**, copy the **URI Connection String**:
   ```text
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
3. Set this as `DATABASE_URL` in your Render backend settings. The application's `lifespan` automatically creates and validates all relational tables on first boot!

---

## 🔒 Security & Privacy

- **Transport & Frame Protection:** HTTP Strict Transport Security (HSTS) with 2-year duration, clickjacking protection (`X-Frame-Options: DENY`), and MIME-sniffing prevention.
- **Content Security Policy (CSP):** Strict CSP headers restricting scripts and frame ancestors.
- **Tenant Isolation:** Document ingestion, vector indexes, and chat sessions are strictly sandboxed per authenticated user account.
- **Zero Committed Secrets:** All credentials are dynamically loaded via environment variables; `.gitignore` rigorously protects development environments and database files.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
