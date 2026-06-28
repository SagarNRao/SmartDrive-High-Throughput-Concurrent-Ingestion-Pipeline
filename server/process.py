import io
import os
import queue
import chromadb
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Always resolve to project-root/chroma_db regardless of process cwd
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(os.path.dirname(_SERVER_DIR), "chroma_db")
COLLECTION_NAME = "smart_drive_collection"

def get_chroma_collection():
    """Initializes a persistent Chroma client and fetches/creates the collection."""
    # Using PersistentClient to ensure the database saves automatically to disk
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    # Automatically handles fetching if exists, or creating if it's the first run
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return collection

def extract_text_from_bytes(file_bytes: bytes, mime_type: str) -> str:
    """Parses raw document bytes based on MIME type and extracts pure text string."""
    text = ""
    try:
        if mime_type == "application/pdf":
            # Read PDF directly out of the memory buffer without saving to disk
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                extracted_page = page.extract_text()
                if extracted_page:
                    text += extracted_page + "\n"
                    
        elif mime_type == "text/plain":
            text = file_bytes.decode("utf-8", errors="ignore")
            
        else:
            # Add additional parsers (docx, csv, etc.) here if needed later
            print(f"[Process] Unsupported MIME type: {mime_type}")
            
    except Exception as e:
        print(f"[Process Error] Extraction failed: {str(e)}")
        
    return text.strip()

def chunk_text(text: str) -> list:
    """Splits text using a recursive character approach keeping structural context intact."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=200,
        length_function=len
    )
    return splitter.split_text(text)

def embed_and_store(file_payload: dict) -> None:
    """Core pipeline step: Extracts, chunks, and commits raw file data to ChromaDB."""
    file_id = file_payload["id"]
    file_name = file_payload["name"]
    mime_type = file_payload["mime_type"]
    file_bytes = file_payload["bytes"]
    
    print(f"[Process] Extracting text from: {file_name}")
    raw_text = extract_text_from_bytes(file_bytes, mime_type)
    
    if not raw_text:
        print(f"[Process] No textual data extracted from {file_name}. Skipping storage.")
        return
        
    chunks = chunk_text(raw_text)
    print(f"[Process] Generated {len(chunks)} chunks for: {file_name}")
    
    collection = get_chroma_collection()
    
    # Construct distinct arrays for ChromaDB batch addition
    documents = []
    metadatas = []
    ids = []
    
    user_owner = file_payload.get("user_owner")
    if not user_owner:
        print(f"[Process] Missing user_owner for {file_name}. Skipping storage.")
        return

    for idx, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({
            "source_id": file_id,
            "file_name": file_name,
            "chunk_index": idx,
            "user_owner": user_owner,
        })
        # Unique ID combining file ID and its structural slice sequence
        ids.append(f"{file_id}_chunk_{idx}")
        
    # Upsert so re-syncs refresh metadata (e.g. user_owner) for existing chunk IDs
    if documents:
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[Process] Successfully stored {len(documents)} vectors for: {file_name}")

def processing_worker(download_queue, stop_event) -> None:
    """Worker loop running inside its own execution context, polling the queue for data."""
    print("[Process Pool] Worker started. Monitoring queue...")
    
    while True:
        try:
            # Poll queue. Timeout ensures it doesn't hang indefinitely if ingest terminates early
            file_payload = download_queue.get(timeout=3)
            
            # Execute processing logic
            embed_and_store(file_payload)
            
            # Signal back that item processing completed
            download_queue.task_done()
            
        except Exception as e:
            if not (stop_event.is_set() and download_queue.empty()):
                if not isinstance(e, queue.Empty):
                    print(f"[Process Pool Error] {e}")
                continue
            print("[Process Pool] Queue drained and ingest finished. Worker spinning down.")
            break