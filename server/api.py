# api.py
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import queue
import threading
# In api.py, update your ingest imports to this:
from ingest import get_drive_service, fetch_all_file_ids, start_parallel_downloads

# Import your existing pipeline functions
from process import processing_worker
from rag import query_smart_drive

from google.oauth2.credentials import Credentials

app = FastAPI()

# Allow your Next.js frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SyncRequest(BaseModel):
    email: str
    folder_id: str

class QueryRequest(BaseModel):
    email: str
    query: str

def execution_pipeline(email: str, folder_id: str):
    """Your updated multi-tenant multi-threaded pipeline execution logic"""
    # Simply load standard credentials or generate temporary ones for execution boundaries
    # To keep it completely simple, we initialize empty token parameters since your Next.js login 
    # provides client authorization, or use a system fallback.
    creds = Credentials(token=None) 
    
    drive_service = get_drive_service(creds)
    files_to_download = fetch_all_file_ids(drive_service, folder_id)
    
    if not files_to_download:
        return

    download_queue = queue.Queue(maxsize=15)
    stop_event = threading.Event()

    consumer_thread = threading.Thread(
        target=processing_worker, 
        args=(download_queue, stop_event),
        name="ProcessWorker"
    )
    consumer_thread.start()

    start_parallel_downloads(files_to_download, creds, download_queue, max_workers=5)
    stop_event.set()
    consumer_thread.join()


@app.post("/sync")
def sync_folder(data: SyncRequest, background_tasks: BackgroundTasks):
    # BackgroundTasks runs your multi-threaded pipeline asynchronously 
    # so the frontend doesn't hang waiting for the download to finish
    background_tasks.add_task(execution_pipeline, data.email, data.folder_id)
    return {"status": "processing", "message": f"Sync started for {data.email}"}

@app.post("/query")
def query_drive(data: QueryRequest):
    # Pass user query to your rag.py script
    # Note: Modify your rag.py query_smart_drive to return the string instead of just printing it
    answer = query_smart_drive(data.query, active_user_email=data.email) 
    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)