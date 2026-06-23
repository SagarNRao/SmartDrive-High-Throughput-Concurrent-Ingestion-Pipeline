Markdown
# SmartDrive-Context-Engine

An asynchronous, high-throughput document ingestion pipeline built in Python to concurrently stream data from the Google Drive API directly into the Groq LLM inference context window.

This engine bypasses the infrastructure overhead, indexing latency, and chunking fragmentation of traditional vector database setups by leveraging concurrent network I/O and large LLM context lengths (`llama-3.3-70b-versatile`) to deliver near-zero latency data retrieval.

## System Architecture

The pipeline is optimized for high-performance network I/O and strict resource management:

[Google Drive Folder]
│
▼ (Scan Metadata)
[fetch_folder_files]
│
▼ (Distribute to Tasks via Semaphore)
[worker_download Pool] ──► (Concurrent In-Memory Streams)
│
▼ (Compile Aggregated Context Buffer)
[Memory]
│
▼ (Direct Injection via HTTPS Post)
[Groq API]


* **Asynchronous Concurrency:** Built entirely on Python's `asyncio` event loop and `aiohttp` client sessions to eliminate blocking I/O operations during simultaneous network calls.
* **Bounded Resource Pool:** Enforces thread-safe rate-limiting using an `asyncio.Semaphore` primitive to optimize parallel download throughput without triggering remote API rate limits (HTTP 429).
* **Automated Session Lifecycle:** Integrates `google-auth` service account flows to handle on-demand token rotation, ensuring cryptographic validity across long-running ingestion batches.

## Core Prerequisites

* Python 3.10+
* A Groq API Key
* A Google Cloud Platform Service Account JSON key file (`service_account.json`) with the **Google Drive API** enabled.

## Environment Configuration

Create a `.env` file in the root directory to store your credentials securely:

```env
GROQ_API_KEY=your_groq_api_key_here
Setup & Deployment
Share Target Folder: Share your target Google Drive folder with the client_email listed inside your service_account.json file as a Viewer.

Install Dependencies:

Bash
pip install aiohttp python-dotenv google-auth
Configure Target Constants: Update the following strings inside the script initialization block:

Python
FOLDER_ID = "your_google_drive_folder_id"
SERVICE_ACCOUNT_FILE = "service_account.json"
MAX_CONCURRENT_WORKERS = 3
Execute Ingestion Loop:

Bash
python speed_rag_groq.py
Performance & Scaling Notes
In-Memory Optimization: Files are streamed directly into volatile memory buffers (io bytes text decoding) rather than being persisted to disk, maximizing processing speed and maintaining absolute isolation from host machine storage.

Context Budget: The pipeline is tuned for llama-3.3-70b-versatile with an effective 128k context window. For multi-gigabyte document corpora, scaling to an asynchronous database storage adapter (psycopg3 + pgvector) is recommended.
