import io
import os
import concurrent.futures
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Define required API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service(creds: Credentials):
    """Authenticates dynamically using the passed user credentials object."""
    return build('drive', 'v3', credentials=creds)

def fetch_all_file_ids(service, folder_id: str) -> list:
    """Lists all files inside a specific Google Drive folder using the active service instance."""
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

def download_single_file(file_info: dict, creds: Credentials, download_queue, user_email: str) -> None:
    """Worker function: Downloads a single file's bytes using user credentials."""
    file_id = file_info['id']
    file_name = file_info['name']
    mime_type = file_info['mimeType']
    
    if 'google-apps' in mime_type:
        print(f"[Ingest] Skipping Google Doc format: {file_name}")
        return

    try:
        # Spin up a localized authenticated service instance inside the thread boundary
        service = get_drive_service(creds)
        request = service.files().get_media(fileId=file_id)
        
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()
            
        file_bytes = file_buffer.getvalue()
        
        payload = {
            "id": file_id,
            "name": file_name,
            "mime_type": mime_type,
            "bytes": file_bytes,
            "user_owner": user_email,
        }
        
        download_queue.put(payload)
        print(f"[Ingest] Successfully downloaded and queued: {file_name}")
        
    except Exception as e:
        print(f"[Ingest Error] Failed downloading {file_name}: {str(e)}")

def start_parallel_downloads(file_list: list, creds: Credentials, download_queue, user_email: str, max_workers: int = 5):
    """Orchestrates concurrent I/O downloads passing user credentials down the pool."""
    print(f"[Ingest] Starting concurrent download pool with {max_workers} workers.")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Use lambda to inject the active user credentials into the download workers cleanly
        executor.map(
            lambda file: download_single_file(file, creds, download_queue, user_email),
            file_list,
        )
        
    print("[Ingest] All download threads have finished execution.")