import io
import os
import concurrent.futures
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Define required API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = 'service_account.json'

def get_drive_service():
    """Authenticates using the service account and returns the Drive client."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

def fetch_all_file_ids(folder_id: str) -> list:
    """Lists all files inside a specific Google Drive folder."""
    service = get_drive_service()
    query = f"'{folder_id}' in parents and trashed = false"
    
    files = []
    page_token = None
    
    while True:
        response = service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name, mimeType)',
            pageToken=page_token
        ).execute()
        
        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if not page_token:
            break
            
    return files

def download_single_file(file_info: dict, download_queue) -> None:
    """Worker function: Downloads a single file's bytes and pushes to the queue."""
    file_id = file_info['id']
    file_name = file_info['name']
    mime_type = file_info['mimeType']
    
    # Google Docs/Sheets/Slides need to be exported, not downloaded directly.
    # We skip or handle them depending on your document types.
    if 'google-apps' in mime_type:
        print(f"[Ingest] Skipping Google Doc format: {file_name} (Needs export logic)")
        return

    try:
        service = get_drive_service()
        request = service.files().get_media(fileId=file_id)
        
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()
            
        file_bytes = file_buffer.getvalue()
        
        # Payload construction for the queue
        payload = {
            "id": file_id,
            "name": file_name,
            "mime_type": mime_type,
            "bytes": file_bytes
        }
        
        # Pushes payload to the queue. Blocks if main.py sets a maxsize and queue is full
        download_queue.put(payload)
        print(f"[Ingest] Successfully downloaded and queued: {file_name}")
        
    except Exception as e:
        print(f"[Ingest Error] Failed downloading {file_name}: {str(e)}")

def start_parallel_downloads(file_list: list, download_queue, max_workers: int = 5):
    """Orchestrates concurrent I/O downloads via ThreadPoolExecutor."""
    print(f"[Ingest] Starting concurrent download pool with {max_workers} workers.")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Pushes all downloading tasks into threads
        executor.map(lambda file: download_single_file(file, download_queue), file_list)
        
    print("[Ingest] All download threads have finished execution.")