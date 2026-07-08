# Smart Google Drive Engine (Better Drive)

An asynchronous Retrieval-Augmented Generation (RAG) system that maps, indexes, and queries Google Drive folders in real-time. Built with a **Next.js** frontend and a specialized **FastAPI** backend featuring optimized local I/O thread pooling, isolated vector spaces, and multi-tenant Redis sliding-window memory caching.

https://github.com/user-attachments/assets/2627c57d-f99a-4a7b-89b8-0d327c0b9996

## 🏗️ Architecture & System Design

The system decouples intensive document ingestion from the user interaction lifecycle using a producer-consumer thread-safe processing model within FastAPI background execution contexts.

```
Next.js Frontend ──(HTTP Query / Sync)──> FastAPI Router
    │
    └─ Triggers Background Task
       │
       ├─ Thread-Safe Queue
       │
       ├─ Producer Thread Pool (5 Workers) ─> Google Drive API Downloads
       │
       └─ Consumer Thread ─────────────────> PDF Parsing & ChromaDB Upsert
```

### Technical Stack Detail

* **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, NextAuth.js (Google Provider)
* **Backend Gateway:** FastAPI, Uvicorn, Pydantic data validation
* **Vector Storage:** ChromaDB (Persistent local deployment utilizing metadata partition filtering)
* **Language Model & Processing Engine:** Groq Cloud API (`llama-3.3-70b-versatile`), `pypdf`, and LangChain text splitters
* **Caching & State Management:** Redis managed via Docker container for localized Q&A caching and multi-turn chat tracking

---

## 🚀 Core Features

* **Dynamic OAuth Ingestion:** Authenticates on the fly using individual user session Google tokens to pull down protected drive folders
* **Concurrent Ingestion Pipeline:** Uses a thread-safe `Queue` architecture. A pool of parallel producer threads downloads document streams entirely in-memory while a decoupled background consumer extracts text and commits vectors
* **Strict Multi-Tenant Query Isolation:** Vector queries utilize specific metadata filters (`where={"user_owner": user_email}`) ensuring zero cross-tenant data leakage
* **Sliding-Window Redis Chat History:** Multi-turn conversational memory handles complex relational follow-up queries. Active chats maintain a 2-hour sliding window TTL while identical query patterns trigger a 24-hour global Redis cache layer for sub-millisecond execution

---

## 📂 Repository Structure

```
.
├── web/                      # Next.js frontend application
│   └── app/
│       └── dashboard/
│           └── page.tsx      # Next.js workspace portal client UI
└── backend/                  # Python FastAPI backend service
    ├── main.py               # Local pipeline debugging entrypoint
    ├── api.py                # Main FastAPI entry point & BackgroundTask worker routing
    ├── redis_client.py       # Asynchronous Redis multi-tenant session & cache architecture
    ├── ingest.py             # Concurrent Google Drive API byte-stream download pool
    ├── process.py            # Local document parsing & ChromaDB persistence layer
    └── rag.py                # Retrieval engine context matching & Groq inference pipeline
```

---

## 🛠️ Local Setup & Execution

### Prerequisites

* Docker installed on your machine
* Google Cloud Console Credentials (with Drive API and OAuth2 consent screen configured)
* Groq API Key

### 1. Environment Variables Configuration

Create a `.env` file inside your backend root directory:

```env
AUTH_GOOGLE_ID=your_google_client_id
AUTH_GOOGLE_SECRET=your_google_client_secret
GROQ_API_KEY=your_groq_api_key
REDIS_URL=redis://localhost:6379/0
```

### 2. Run the Application Infrastructure

Open three distinct terminal sessions to launch the ecosystem:

**Step 1: Start Redis Server (via Docker)**

Spin up the official isolated container for cache and state management:

```bash
docker run -p 6379:6379 redis
```

**Step 2: Initialize FastAPI Backend Engine**

Install project dependencies (`fastapi`, `redis`, `chromadb`, `groq`, `pypdf`, `langchain-text-splitters`) and run the core pipeline:

```bash
python api.py
```

**Step 3: Launch Next.js Interface**

```bash
cd web
npm install
npm run dev
```

Navigate to `http://localhost:3000` to link folders and test queries.