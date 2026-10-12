<div align="center">

# Bible Verse Finder AI

An intelligent Bible verse search engine built on hybrid semantic and keyword retrieval, with AI summarization, adaptive query classification, and support for more than one LLM.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [UI Walkthrough](#ui-walkthrough)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Contributing](#contributing)

## Overview

Bible Verse Finder AI is a search tool that goes past simple keyword matching. You can search the Bible by meaning in natural language, and a hybrid retrieval system combines FAISS vector similarity with BM25 keyword scoring through an adaptive Weighted Reciprocal Rank Fusion (RRF) algorithm.

Each query is classified by a weighted blend of feature signals (named entity, exact phrase, single or multi-concept, general topic, comparative, verse reference), which produces a continuous alpha that tunes the FAISS-versus-BM25 balance. Exact references like `John 3:16` or `1 Cor 13:4-7` short-circuit retrieval entirely and return the verse directly. Results can be summarized by an LLM that gives cited key points, thematic connections, and a confidence score, all grounded strictly in the retrieved verses.

## Features

- Hybrid retrieval: FAISS semantic search and BM25 keyword search, fused via canonical Reciprocal Rank Fusion
- Signal-blending query classification: a weighted blend over exact phrase, named entity, single or multi-concept, general topic, and comparative signals, producing a continuous RRF weight rather than forcing each query into one bucket
- Verse-reference short-circuit: `John 3:16`, `1 Cor 13:4-7`, `Rom 8.28` skip FAISS and BM25 and return the exact verse directly, with no embedding call, in about 5ms. Old Testament references get a clear "not indexed" notice instead of unrelated results
- Exact phrases: wrapping words in quotes (`"born again"`) restricts results to verses containing that wording
- Graceful degradation: if OpenAI embeddings are unavailable, hybrid search falls back to keyword matches and says so
- Support for more than one LLM: OpenAI (GPT-4o-mini), Google Gemini, and Grok (xAI), with automatic fallback for summarization
- AI summarization with citations: every claim carries an inline `[verse_id]` citation grounded in the retrieved verses; citations of verses the model wasn't given are removed
- Adjustable analysis depth: Quick (7 verses), Balanced (12 verses), or Comprehensive (20 verses)
- Full chapter reading with verse highlighting
- Adaptive thresholds: FAISS cosine threshold, dynamic BM25 cutoff relative to the top hit, and an RRF threshold on a normalized 0 to 1 scale
- Persistent caching: a SQLite embedding cache (90-day TTL by default) avoids repeat OpenAI calls, and a summary cache (7-day TTL) survives restarts
- Explore mode: infinite scroll with a per-result scoring breakdown (FAISS score, BM25 score, fusion score, ranks)
- Pre-built search indices: FAISS and BM25 indices ship with the repo, so no re-embedding is required
- Search history: recent searches persisted for quick access
- React and FastAPI stack: a responsive frontend with a production-ready API backend

## UI Walkthrough

### 1. Home Page

[![Home Page](https://github.com/richie-rk/Bible-VerseFinder-AI/raw/main/docs/screenshots/01-home.png)](docs/screenshots/01-home.png)

The landing screen is the main entry point.

- Hero search bar: type a topic, a verse reference, or a natural language question ("What does the Bible say about grace?") and press Enter or click Search.
- Verse of the Day: a curated verse in serif type with a gold accent border. Click Read Chapter to open the full chapter with that verse highlighted.
- Topic pills: eight quick-access buttons (grace, forgiveness, love, fear, hope, faith, wisdom, prayer) that run a search on click.
- Recent searches: your last 3 queries with timestamps, persisted across sessions via localStorage.

### 2. Search Results

[![Search Results](https://github.com/richie-rk/Bible-VerseFinder-AI/raw/main/docs/screenshots/02-search-results.png)](docs/screenshots/02-search-results.png)

Ranked verses matching your query, with filtering controls.

- Left sidebar (desktop): a Search Mode toggle (Semantic, Keyword, or Hybrid, with Hybrid as the default), a Search Depth control (Quick, Balanced, or Comprehensive), and a Summarize with AI button.
- Results header: total verse count and the active query.
- Verse cards: reference, full text, a relevance score bar with percentage match, a book category tag, and hover actions (bookmark, copy, share).
- Infinite scroll: more results load as you scroll. Click any card to open the full chapter with that verse highlighted.

### 3. AI Summary

[![AI Summary View](https://github.com/richie-rk/Bible-VerseFinder-AI/raw/main/docs/screenshots/03-ai-summary.png)](docs/screenshots/03-ai-summary.png)

An AI-generated analysis that pulls insights from the matching verses.

- AI Summary card: the main summary with a confidence badge, inline clickable verse citations, and model metadata (model name, token count, response time).
- Key Insights: bullet-point takeaways, each with supporting verse references.
- Related Themes: cards showing thematic connections (Salvation, Forgiveness, Faith), each listing connected verses as clickable pills with a short explanation.
- Cited Verses: every referenced verse with a relevance badge (Primary, Supporting, or Contextual) and full text. Click a reference to read it in context.
- Footer actions: Regenerate re-runs the analysis, Copy Summary copies the text.

### 4. Bible Reader

[![Bible Reader](https://github.com/richie-rk/Bible-VerseFinder-AI/raw/main/docs/screenshots/04-bible-reader.png)](docs/screenshots/04-bible-reader.png)

A full-page, distraction-free reading experience rather than a modal overlay.

- Compact header: back button, book and chapter display, and previous/next chapter arrows.
- Reading area: a centered column (max 720px) with serif type, generous line height, gold superscript verse numbers, and a warm gold highlight on the verse you navigated from.
- Verse actions: hover any verse to reveal a bookmark button.
- Font controls: adjust font size (14px to 28px) from the bottom bar, with verse count and chapter navigation. The reader bypasses the main nav shell for a Kindle-like feel.

### 5. Collections

[![Collections Page](https://github.com/richie-rk/Bible-VerseFinder-AI/raw/main/docs/screenshots/05-collections.png)](docs/screenshots/05-collections.png)

Organize your saved verses into personal collections.

- Favorites: the default collection, populated by tapping the bookmark icon on any verse.
- Custom collections: create named collections ("Study Notes", "Sermon Prep") with the New Collection button. Each card shows the name, verse count, and a preview of saved references.
- Empty state: new users see a prompt with an Explore Verses button.
- Collection data is persisted to localStorage via Zustand's persist middleware.

### Navigation

| Platform | Navigation |
| --- | --- |
| Desktop | Top nav bar with logo, search, bookmarks, settings, and a dark mode toggle |
| Mobile | Bottom tab bar with Home, Search, Library, and Settings |

Dark mode toggles via the sun/moon icon in the header and persists across sessions.

## Architecture

The system is built in a few clear layers.

**Data processing and storage.** OpenAI `text-embedding-3-small` produces 1536-dimensional embeddings for semantic search. Those vectors live in a FAISS store for cosine similarity, a BM25 index (with PyStemmer stemming) handles keyword search, and a verse metadata store holds the complete Bible text with book and chapter metadata.

**Hybrid retrieval.** Canonical RRF lets each retriever contribute only when it actually returned the document:

```
rrf = alpha       * 1/(faiss_rank + k)   if doc in FAISS, else 0
    + (1 - alpha) * 1/(bm25_rank + k)    if doc in BM25,  else 0
```

The score is normalized to [0, 1] before the RRF threshold is applied. A signal-blending classifier takes the weighted mean of per-signal target alphas, anchored by a baseline at `alpha_default`, and reports the dominant signal for observability while retrieval uses the blended alpha. The continuous alpha lands roughly in [0.22, 0.75]: exact-phrase-heavy queries pull toward keyword, general-topic queries pull toward semantic, and mixed queries sit in between. Adaptive thresholds cover the FAISS cosine minimum (0.20 default), a dynamic BM25 cutoff (`max(bm25_min_score, top * bm25_relative_threshold)`) to handle term-rarity scale, and a normalized RRF minimum (0.15 default). The verse-reference short-circuit parses `Book Chapter:Verse` (with common abbreviations and ranges), bypasses FAISS and BM25, and returns via an O(1) lookup.

**LLM integration.** OpenAI GPT-4o-mini is the default summarizer, with Google Gemini (the current Flash model, via Google's `gemini-flash-latest` alias) and Grok (xAI, `grok-4.20-non-reasoning`) as alternatives. Fallback runs the requested provider, then the configured default, then OpenAI, then Gemini, then Grok, then an error. Verse text sent to the model always comes from the server's own corpus, never from the API caller.

**API and interface.** A FastAPI backend serves the endpoints with a health check, Swagger docs, CORS limited to configured origins, and per-IP rate limits on the endpoints that cost money (`/search`, `/summarize`). The frontend is React and TypeScript (Vite, shadcn/ui, TailwindCSS, Zustand, TanStack Query). SQLite-backed caches at `backend/vector_store/cache.db` hold the embedding cache (90-day TTL by default, or disabled) and the summary cache (7-day TTL), both capped by LRU size limits. Verse and chapter lookups (`/verses/{id}`, `/chapters/{book}/{chapter}`) use pre-built dicts rather than linear scans.

## Installation

### Prerequisites

- Python 3.13+
- Node.js 18+ and npm
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key (required for embeddings and search)
- Optional: a Gemini API key and a Grok API key for the alternative summarizers

### Setup

Clone the repository:

```bash
git clone https://github.com/richie-rk/Bible-VerseFinder-AI.git
cd Bible-VerseFinder-AI
```

Set up the backend:

```bash
cd backend
uv sync
```

Set up the frontend:

```bash
cd frontend
npm install
```

Create `backend/.env`:

```bash
OPENAI_API_KEY=sk-your-openai-api-key
# GEMINI_API_KEY=your-gemini-api-key
# GROK_API_KEY=your-grok-api-key
# LLM_PROVIDER=openai
```

The FAISS and BM25 indices are pre-built and included in `backend/vector_store/`, so there's no extra data setup. `OPENAI_API_KEY` is required for semantic and hybrid search (the query is embedded at call time). Pure keyword search (`mode=keyword`) and verse-reference lookups (`John 3:16`) work with no API key at all; without a key, hybrid search falls back to keyword matches and semantic mode returns 503. Summarization needs a key for whichever provider is active.

## Usage

Start the FastAPI backend:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

In a separate terminal, start the React frontend:

```bash
cd frontend
npm run dev
```

Then open:

- React UI: <http://localhost:8080>
- FastAPI docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

### API endpoints

- `GET /search` searches for verses (semantic, keyword, or hybrid)
- `POST /summarize` generates an AI summary with citations from the results
- `GET /verses/{verse_id}` gets a verse by ID (for example `John_3:16`; case and abbreviations like `jn_3:16` are accepted)
- `GET /chapters/{book}/{chapter}` gets all verses from a chapter, plus the book's chapter count (book names are case-insensitive and accept abbreviations)
- `GET /providers` lists available LLM providers
- `GET /health` checks system status, index state, and verse count

## Configuration

The backend is configurable through environment variables or a `.env` file in `backend/`.

```bash
# LLM
OPENAI_API_KEY=sk-your-key              # Required for semantic + hybrid search (query embeddings)
GEMINI_API_KEY=your-key                 # Optional: Gemini summarization
GROK_API_KEY=your-key                   # Optional: Grok summarization
LLM_PROVIDER=openai                     # Default provider: openai | gemini | grok

# Models
OPENAI_SUMMARIZATION_MODEL=gpt-4o-mini
GEMINI_SUMMARIZATION_MODEL=gemini-flash-latest   # Alias for the current Flash model; pin a version for reproducibility
GEMINI_THINKING_LEVEL=low               # Gemini 3 thinking level; set empty for models without thinking levels
GROK_SUMMARIZATION_MODEL=grok-4.20-non-reasoning

# Timeouts and retries
OPENAI_TIMEOUT_SECONDS=15               # Embedding calls (on the search path)
OPENAI_MAX_RETRIES=2
LLM_TIMEOUT_SECONDS=60                  # Summarization calls, per provider
LLM_MAX_RETRIES=1

# API protection
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080   # Comma-separated browser origins allowed to call the API
RATE_LIMIT_SEARCH_PER_MINUTE=120        # Per client IP; 0 disables
RATE_LIMIT_SUMMARIZE_PER_MINUTE=10      # Per client IP; 0 disables
MAX_QUERY_LENGTH=500

# Retrieval
SEARCH_K=200                            # Candidates per retriever before RRF fusion

# Thresholds
FAISS_THRESHOLD=0.20                    # Semantic cosine minimum
BM25_MIN_SCORE=0.1                      # Absolute BM25 floor (noise rejection)
BM25_RELATIVE_THRESHOLD=0.05            # Keep BM25 results >= 5% of top score
RRF_THRESHOLD=0.15                      # Normalized [0-1] RRF minimum
RRF_K=60                                # RRF smoothing constant

# Caching (SQLite, backend/vector_store/cache.db unless CACHE_DB_PATH is set)
EMBEDDING_CACHE_TTL_DAYS=90             # 0 = never expire
EMBEDDING_CACHE_MAX_ENTRIES=10000       # LRU cap (~6 KB per entry); 0 = no cap
SUMMARY_CACHE_TTL_DAYS=7
SUMMARY_CACHE_MAX_ENTRIES=1000

# Logging
LOG_LEVEL=INFO

# Pagination
DEFAULT_PAGE_SIZE=50
MAX_PAGE_SIZE=100

# Alpha targets for the signal-blending classifier
ALPHA_NAMED_ENTITY=0.38                 # Named-entity signal (e.g. "Jesus", "Paul")
ALPHA_EXACT_PHRASE=0.25                 # Canonical phrases (e.g. "born again")
ALPHA_SINGLE_CONCEPT=0.65               # Single concept (e.g. "grace")
ALPHA_MULTI_CONCEPT=0.60                # Multiple concepts (e.g. "grace and faith")
ALPHA_GENERAL_TOPIC=0.70                # Question form (e.g. "What about suffering?")
ALPHA_COMPARATIVE=0.65                  # Comparative form (e.g. "grace vs mercy")
ALPHA_DEFAULT=0.50                      # Baseline anchor when no strong signal fires
```

Mixed queries like "What does Jesus say about grace?" fire several signals at once, so the final alpha is a weighted blend of these targets rather than any single one.

Rate limits are kept in memory per worker process. Behind a reverse proxy, start uvicorn with `--proxy-headers` (and `--forwarded-allow-ips`) so limits apply to the real client IP rather than the proxy.

### Frontend scripts

```bash
npm run dev          # Dev server (port 8080)
npm run typecheck    # TypeScript (strict) type check
npm run build        # Type check, then production build
npm run preview      # Preview the production build
npm run lint         # ESLint
npm run test         # Vitest
```

### Backend scripts

```bash
uv run uvicorn app.main:app --reload    # Dev server (port 8000)
uv run pytest                            # Tests
```

### Rebuild search indices (optional)

The indices are pre-built in `backend/vector_store/`. Only run these if you need to regenerate them. Both scripts write straight into `backend/vector_store/`; the FAISS script stops without writing anything if any batch fails to embed, and the API refuses to load indices whose verse counts don't match.

```bash
cd scripts
uv run python create_faiss_index.py    # Requires OPENAI_API_KEY
uv run python create_bm25_index.py
```

## Contributing

Contributions are welcome, whether it's a bug fix, a new feature, or a better retrieval idea. Here's the flow I'd like you to follow.

1. Fork the repository and clone your fork locally.
2. Before you write any code, open an issue. If it's a bug, describe how to reproduce it. If it's a feature, explain what you want to add and why. This gives us a place to agree on the approach before any work happens.
3. Create a branch for your change off `main`.
4. Make your change, and update or add tests where it makes sense (`npm run test` for the frontend, `uv run pytest` for the backend).
5. Open a pull request and link it to the issue (for example, "Closes #12"), so the work and the issue stay tied together.

If you're not sure whether something fits, open an issue and ask first. I'd rather talk it through early than have you spend time on something that's hard to merge.

## License

Distributed under the MIT License. See `LICENSE` for details.

---

Built for searching verses via AI, not just by words.
