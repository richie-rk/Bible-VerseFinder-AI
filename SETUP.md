# Bible Verse Finder AI - Setup & Commands

## Prerequisites

| Tool       | Version  | Notes                        |
|------------|----------|------------------------------|
| Python     | 3.13+    | Required for backend         |
| uv         | latest   | Python package manager       |
| Node.js    | 18+      | Required for frontend        |
| npm        | latest   | Frontend package manager (package-lock.json is the lockfile) |

---

## Backend (FastAPI)

**Port:** `http://localhost:8000`

```bash
# Navigate to backend
cd backend

# Install dependencies
uv sync

# (Optional) Create a .env file for LLM features
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=...
# GROK_API_KEY=...
# LLM_PROVIDER=openai

# Start the server
uv run uvicorn app.main:app --reload
```

### Backend URLs

| URL                              | Description            |
|----------------------------------|------------------------|
| `http://localhost:8000/health`   | Health check           |
| `http://localhost:8000/docs`     | Interactive API docs   |
| `http://localhost:8000/search`   | Search endpoint (GET)  |
| `http://localhost:8000/summarize`| Summarize endpoint (POST) |

---

## Frontend (React + Vite)

**Port:** `http://localhost:8080`

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

### Frontend Scripts

| Command            | Description                |
|--------------------|----------------------------|
| `npm run dev`      | Start dev server (port 8080) |
| `npm run typecheck` | Type-check the app and config files |
| `npm run build`    | Type-check, then production build to dist/ |
| `npm run lint`     | Run ESLint                 |
| `npm run test`     | Run tests (Vitest)         |
| `npm run test:watch` | Run tests in watch mode  |

---

## Quick Start (Two Terminals)

**Terminal 1 - Backend:**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:8080` in your browser.

---

## Scripts (Index Rebuilding - Optional)

These are only needed if you want to rebuild the search indices from scratch. The pre-built indices are already included in `backend/vector_store/`, and the scripts write their output there directly.

```bash
cd scripts

# Create FAISS vector index (requires OPENAI_API_KEY)
uv run python create_faiss_index.py

# Create BM25 keyword index
uv run python create_bm25_index.py
```

---

## Environment Variables

| Variable         | Required | Default  | Description                 |
|------------------|----------|----------|-----------------------------|
| `OPENAI_API_KEY` | No*      | —        | OpenAI API key for embeddings & summaries |
| `GEMINI_API_KEY` | No       | —        | Google Gemini API key       |
| `GROK_API_KEY`   | No       | —        | Grok API key                |
| `LLM_PROVIDER`   | No       | `openai` | Which LLM to use (openai/gemini/grok) |
| `CORS_ORIGINS`   | No       | `http://localhost:8080,...` | Comma-separated browser origins allowed to call the API |

*Keyword search and verse lookups work without API keys. Without `OPENAI_API_KEY`, hybrid search falls back to keyword matches and semantic mode is unavailable. Keys are needed for the AI summarization feature. See the README's Configuration section for every setting.
