# Bible Verse Finder AI
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent Bible verse search engine powered by hybrid semantic + keyword retrieval with AI-powered summarization, featuring adaptive query classification and multiple LLM support.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [UI Walkthrough](#ui-walkthrough)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)

## Overview

Bible Verse Finder AI is an advanced Bible search tool that goes beyond simple keyword matching. It allows users to search the Bible by meaning using natural language, leveraging a hybrid retrieval system that combines FAISS vector similarity search with BM25 keyword scoring through an adaptive Weighted Reciprocal Rank Fusion (RRF) algorithm.

The system automatically classifies queries by type (named entity, exact phrase, concept, comparative) and dynamically adjusts ranking weights for optimal results. Search results can be summarized by an LLM that provides cited key points, thematic connections, and confidence scoring — all grounded strictly in the retrieved verses.

## Features

- **Hybrid Retrieval System**: Combines FAISS semantic search with BM25 keyword search via adaptive Reciprocal Rank Fusion
- **Adaptive Query Classification**: Automatically detects query types (named entity, exact phrase, concept, comparative) and adjusts ranking weights
- **Multi-LLM Support**: Choose between OpenAI (GPT-4o-mini), Google Gemini, and Grok (xAI) with automatic fallback
- **AI Summarization with Citations**: Every claim includes inline `[verse_id]` citations grounded in retrieved verses
- **Adjustable Analysis Depth**: Quick (7 verses), Balanced (12 verses), or Comprehensive (20 verses) summarization tiers
- **Full Chapter Reading**: View complete chapters with verse highlighting for contextual understanding
- **3-Layer Filtering**: Individual FAISS and BM25 thresholds plus RRF fusion threshold for precision
- **Explore Mode**: Infinite scroll with detailed scoring breakdowns (FAISS score, BM25 score, ranks)
- **Pre-built Search Indices**: FAISS and BM25 indices included — search works immediately without setup
- **Search History**: Persists recent searches for quick access
- **React + FastAPI Stack**: Modern, responsive frontend with a production-ready API backend

## UI Walkthrough

### 1. Home Page

<p align="center">
  <img src="docs/screenshots/01-home.png" alt="Home Page" width="600" />
</p>

The landing screen provides the primary entry point into Bible Verse Finder AI.

- **Hero search bar** — Type a topic, verse reference, or natural language question (e.g., "What does the Bible say about grace?") and press Enter or click Search to navigate to results.
- **Verse of the Day** — A curated verse displayed in serif typography with a gold accent border. Click **Read Chapter** to open the full chapter in the Bible Reader with that verse highlighted.
- **Topic pills** — Eight quick-access topic buttons (grace, forgiveness, love, fear, hope, faith, wisdom, prayer). Clicking any pill immediately runs a search for that topic.
- **Recent searches** — Shows your last 3 search queries with timestamps. Click any card to re-run that search. History is persisted across sessions via localStorage.

### 2. Search Results

<p align="center">
  <img src="docs/screenshots/02-search-results.png" alt="Search Results" width="600" />
</p>

Displays ranked Bible verses matching your query with filtering controls.

- **Left sidebar (desktop)** — Contains three control groups:
  - **Search Mode** toggle — Switch between *Semantic* (AI meaning-based), *Keyword* (exact text match), or *Hybrid* (combined scoring). Hybrid is the default.
  - **Search Depth** — Choose *Quick* (top 10), *Balanced* (top 25), or *Comprehensive* (top 50) to control how many verses are analyzed.
  - **Summarize with AI** button — Navigates to the AI Summary view for the current query.
- **Results header** — Shows total verse count and the active query.
- **Verse cards** — Each result displays the verse reference, full text, relevance score bar with percentage match, book category tag, and hover actions (bookmark, copy, share).
- **Infinite scroll** — More results load automatically as you scroll down.
- **Click any verse card** to open the full chapter in the Bible Reader with that verse highlighted.

### 3. AI Summary

<p align="center">
  <img src="docs/screenshots/03-ai-summary.png" alt="AI Summary View" width="600" />
</p>

An AI-generated analysis that synthesizes insights from matching verses.

- **AI Summary card** — The primary summary paragraph with a confidence score badge, inline clickable verse citations, and model metadata (LLM name, token count, response time).
- **Key Insights** — Bullet-pointed takeaways extracted from the verses, each with supporting verse references.
- **Related Themes** — Cards showing thematic connections (e.g., Salvation, Forgiveness, Faith). Each card lists connected verses as clickable pills and a brief explanation.
- **Cited Verses** — All referenced verses with relevance badges (*Primary*, *Supporting*, or *Contextual*) and full text. Click any reference to read in context.
- **Footer actions** — *Regenerate* re-runs the AI analysis; *Copy Summary* copies the text to clipboard.

### 4. Bible Reader

<p align="center">
  <img src="docs/screenshots/04-bible-reader.png" alt="Bible Reader" width="600" />
</p>

A full-page, distraction-free reading experience (not a modal overlay).

- **Compact header** — Back button, book/chapter display, and previous/next chapter arrows.
- **Reading area** — Centered column (max 720px) with serif typography, generous line-height (1.9), gold superscript verse numbers, and warm gold highlighting on the navigated-from verse.
- **Verse actions** — Hover over any verse to reveal a bookmark button.
- **Font controls (bottom bar)** — Increase/decrease font size (14px–28px), verse count, and chapter navigation.
- The reader bypasses the main navigation shell for an immersive, Kindle-like experience.

### 5. Collections

<p align="center">
  <img src="docs/screenshots/05-collections.png" alt="Collections Page" width="600" />
</p>

Organize and manage your saved verses in personal collections.

- **Favorites** — Default collection at the top. Verses are added by tapping the bookmark icon on any verse across the app.
- **Custom collections** — Create named collections (e.g., "Study Notes", "Sermon Prep") using the **+ New Collection** button. Each card shows name, verse count, and a preview of saved references.
- **Empty state** — New users see an instructional prompt with an "Explore Verses" button.
- All collection data is persisted to localStorage via Zustand's persist middleware.

### Navigation

| Platform | Navigation |
|----------|-----------|
| Desktop | Top nav bar with logo, search, bookmarks, settings, and dark mode toggle |
| Mobile | Bottom tab bar with Home, Search, Library, and Settings tabs |

Dark mode is toggled via the sun/moon icon in the header and persists across sessions.

## Architecture

The system features a sophisticated multi-component architecture:

### **Data Processing & Storage**
- **OpenAI text-embedding-3-small**: 1536-dimensional embeddings for semantic understanding
- **FAISS Vector Store**: High-performance cosine similarity search
- **BM25 Index**: Traditional keyword-based search with stemming via PyStemmer
- **Verse Metadata Store**: Complete Bible text with book and chapter metadata

### **Hybrid Retrieval System**
- **Adaptive Weighted RRF**: `RRF_Score = α × (1/(faiss_rank + 60)) + (1-α) × (1/(bm25_rank + 60))`
- **Query Classifier**: Regex-based detection of named entities, exact phrases, comparatives, and concepts
- **Dynamic Alpha Weighting**: α ranges from 0.25 (exact phrases) to 0.70 (general topics)
- **3-Layer Threshold Filtering**: FAISS (0.20), BM25 (0.5), and RRF (0.003) minimums

### **LLM Integration**
- **OpenAI**: GPT-4o-mini for summarization (default)
- **Google Gemini**: Gemini 1.5 Flash as alternative provider
- **Grok (xAI)**: Grok Beta as alternative provider
- **Automatic Fallback**: Primary → OpenAI → Gemini → Grok → Error

### **API & Interface**
- **FastAPI Backend**: Production-ready API with health checks, interactive Swagger docs, and CORS support
- **React + TypeScript Frontend**: Built with Vite, shadcn/ui, TailwindCSS, and Zustand state management
- **React Query**: Server state management with @tanstack/react-query
- **Canonical Query Caching**: 7-day in-memory cache for common searches (grace, faith, love, etc.)

## Installation

### Prerequisites
- Python 3.13+
- Node.js 18+ and npm
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- OpenAI API key (required for embeddings and search)
- Optional: Gemini API key, Grok API key (for alternative summarization providers)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/richie-rk/VerseFinder-AI.git
   cd VerseFinder-AI
   ```

2. **Backend setup**:
   ```bash
   cd backend
   uv sync
   ```

3. **Frontend setup**:
   ```bash
   cd frontend
   npm install
   ```

4. **Environment configuration**:

   Create `backend/.env`:
   ```env
   OPENAI_API_KEY=sk-your-openai-api-key
   # GEMINI_API_KEY=your-gemini-api-key
   # GROK_API_KEY=your-grok-api-key
   # LLM_PROVIDER=openai
   ```

   > **Note**: The FAISS and BM25 search indices are pre-built and included in `backend/vector_store/`. No additional data setup is needed. Search works without API keys — keys are only required for the AI summarization feature.

## Usage

### **Quick Start**

1. **Start the FastAPI backend**:
   ```bash
   cd backend
   uv run uvicorn app.main:app --reload
   ```

2. **In a separate terminal, start the React frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the application**:
   - **React UI**: http://localhost:8080
   - **FastAPI docs**: http://localhost:8000/docs
   - **Health check**: http://localhost:8000/health

### **API Endpoints**

- `GET /search` - Search for Bible verses (semantic, keyword, or hybrid mode)
- `POST /summarize` - Generate AI summary with citations from search results
- `GET /verses/{verse_id}` - Get a specific verse by ID (e.g., `John_3:16`)
- `GET /chapters/{book}/{chapter}` - Get all verses from a specific chapter
- `GET /providers` - List available LLM providers
- `GET /health` - Check system status, index state, and verse count

## Configuration

The backend is fully configurable through environment variables or a `.env` file in the `backend/` directory:

### **Environment Variables**

```bash
# LLM Configuration
OPENAI_API_KEY=sk-your-key              # Required for embeddings + summarization
GEMINI_API_KEY=your-key                  # Optional: Gemini summarization
GROK_API_KEY=your-key                    # Optional: Grok summarization
LLM_PROVIDER=openai                      # Default provider: openai | gemini | grok

# Model Configuration
OPENAI_SUMMARIZATION_MODEL=gpt-4o-mini
GEMINI_SUMMARIZATION_MODEL=gemini-1.5-flash
GROK_SUMMARIZATION_MODEL=grok-beta

# Search Thresholds
FAISS_THRESHOLD=0.20                     # Semantic similarity minimum
BM25_THRESHOLD=0.5                       # Keyword score minimum
RRF_THRESHOLD=0.003                      # Fusion score minimum
RRF_K=60                                 # RRF constant

# Pagination
DEFAULT_PAGE_SIZE=50
MAX_PAGE_SIZE=100

# Alpha Weights (query type → semantic vs keyword balance)
ALPHA_NAMED_ENTITY=0.38                  # "Jesus teaches" → favor keywords
ALPHA_EXACT_PHRASE=0.25                  # "born again" → strongly favor keywords
ALPHA_SINGLE_CONCEPT=0.65               # "grace" → favor semantics
ALPHA_MULTI_CONCEPT=0.60                # "grace and faith"
ALPHA_GENERAL_TOPIC=0.70                # "What about suffering?" → favor semantics
ALPHA_COMPARATIVE=0.65                   # "grace vs mercy"
ALPHA_DEFAULT=0.50                       # Fallback
```

### **Example .env File**

```env
# Required
OPENAI_API_KEY=sk-your-key

# Optional: Choose your summarization provider
LLM_PROVIDER=openai
# GEMINI_API_KEY=your-key
# GROK_API_KEY=your-key

# Optional: Override default models
# OPENAI_SUMMARIZATION_MODEL=gpt-4o-mini
# GEMINI_SUMMARIZATION_MODEL=gemini-1.5-flash
# GROK_SUMMARIZATION_MODEL=grok-beta
```

### **Frontend Scripts**

```bash
npm run dev          # Start development server (port 8080)
npm run build        # Production build
npm run build:dev    # Development build
npm run preview      # Preview production build
npm run lint         # Run ESLint
npm run test         # Run tests (Vitest)
npm run test:watch   # Tests in watch mode
```

### **Backend Scripts**

```bash
uv run uvicorn app.main:app --reload    # Start dev server (port 8000)
uv run pytest                            # Run tests
```

### **Rebuild Search Indices (Optional)**

Pre-built indices are included in `backend/vector_store/`. Only run these if you need to regenerate them:

```bash
cd scripts
uv run python create_faiss_index.py    # Requires OPENAI_API_KEY
uv run python create_bm25_index.py
```

---

Built with ❤️ for Bible study and exploration

---
