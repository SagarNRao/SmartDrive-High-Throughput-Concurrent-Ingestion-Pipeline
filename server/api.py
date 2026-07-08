# api.py
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import queue
import threading
from dotenv import load_dotenv

# Import your existing pipeline functions
from ingest import get_drive_service, fetch_all_file_ids, start_parallel_downloads
from process import processing_worker
from rag import query_smart_drive
from redis_client import ping_redis, close_redis_client, clear_session

from google.oauth2.credentials import Credentials

load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("AUTH_GOOGLE_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("AUTH_GOOGLE_SECRET")
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def build_google_credentials(access_token: str, refresh_token: str | None = None) -> Credentials:
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=DRIVE_SCOPES,
    )

app = FastAPI()

# Allow your Next.js frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default local server port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # Just a friendly heads-up in the logs if Redis isn't reachable - the app
    # still works fine without it (caching/session memory are best-effort).
    await ping_redis()


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis_client()


# FIXED: Ensure all properties have strict type annotations (: str)
class SyncRequest(BaseModel):
    email: str
    folder_id: str
    access_token: str
    refresh_token: str | None = None

class QueryRequest(BaseModel):
    email: str
    query: str
    session_id: str | None = None  # groups multi-turn chat memory in Redis; defaults to "default"

class ClearSessionRequest(BaseModel):
    email: str
    session_id: str | None = None

def execution_pipeline(email: str, folder_id: str, access_token: str, refresh_token: str | None = None):
    """Your multi-tenant multi-threaded pipeline execution logic"""
    print(f"\n[Sync] Spawning data ingestion pipeline background task for {email}...")
    
    creds = build_google_credentials(access_token, refresh_token)
    
    try:
        drive_service = get_drive_service(creds)
        files_to_download = fetch_all_file_ids(drive_service, folder_id)
        
        if not files_to_download:
            print(f"[Sync] Zero processing candidates found inside folder: {folder_id}")
            return
            
        print(f"[Sync] Extraction worker found {len(files_to_download)} files to parse.")
    except Exception as e:
        print(f"[Sync Error] Failed tracking cloud infrastructure constraints for {email}: {e}")
        return

    # Initialize thread-safe shared system queues
    download_queue = queue.Queue(maxsize=15)
    stop_event = threading.Event()

    # Spin up consumer background worker thread
    consumer_thread = threading.Thread(
        target=processing_worker, 
        args=(download_queue, stop_event),
        name="ProcessWorker"
    )
    consumer_thread.start()

    try:
        # Launch producer worker thread pool handling parallel downloads
        start_parallel_downloads(files_to_download, creds, download_queue, email, max_workers=5)
    except Exception as e:
        print(f"[Sync Error] Error executing parallel stream workflows for {email}: {e}")
    finally:
        # Gracefully teardown and join thread boundaries
        stop_event.set()
        consumer_thread.join()
        print(f"[Sync] Ingestion pipeline execution successfully terminated for {email}.")


@app.post("/sync")
def sync_folder(data: SyncRequest, background_tasks: BackgroundTasks):
    if not data.access_token:
        return {
            "status": "error",
            "message": "Missing Google access token. Sign out and sign back in, then retry.",
        }

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return {
            "status": "error",
            "message": "Server missing AUTH_GOOGLE_ID / AUTH_GOOGLE_SECRET in .env.",
        }

    try:
        creds = build_google_credentials(data.access_token, data.refresh_token)
        get_drive_service(creds).files().list(pageSize=1, fields="files(id)").execute()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Google Drive authentication failed: {e}",
        }

    background_tasks.add_task(
        execution_pipeline,
        data.email,
        data.folder_id,
        data.access_token,
        data.refresh_token,
    )
    return {"status": "processing", "message": f"Sync started for {data.email}. This may take a minute."}

@app.post("/query")
async def query_drive(data: QueryRequest):
    # Pass user query to your rag.py search engine matrices.
    # session_id groups multi-turn chat memory in Redis; falls back to "default"
    # if the client doesn't send one (still works, just one shared thread per user).
    session_id = data.session_id or "default"
    answer, was_cached = await query_smart_drive(
        data.query,
        active_user_email=data.email,
        session_id=session_id,
    )
    return {"answer": answer, "cached": was_cached}


@app.post("/session/clear")
async def clear_chat_session(data: ClearSessionRequest):
    """Optional helper endpoint for a 'New Chat' button on the frontend."""
    session_id = data.session_id or "default"
    await clear_session(data.email, session_id)
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)