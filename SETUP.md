# VerseFinder AI - Setup & Commands

## Prerequisites

| Tool       | Version  | Notes                        |
|------------|----------|------------------------------|
| Python     | 3.13+    | Required for backend         |
| uv         | latest   | Python package manager       |
| Node.js    | 18+      | Required for frontend        |
| npm or bun | latest   | Either works for frontend    |

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
# OR
bun install

# Start the dev server
npm run dev
# OR
bun run dev
```

### Frontend Scripts

| Command            | Description                |
|--------------------|----------------------------|
| `npm run dev`      | Start dev server (port 8080) |
| `npm run build`    | Production build to dist/  |
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

These are only needed if you want to rebuild the search indices from scratch. The pre-built indices are already included in `backend/vector_store/`.

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

*Search works without API keys. Keys are needed for the AI summarization feature.
