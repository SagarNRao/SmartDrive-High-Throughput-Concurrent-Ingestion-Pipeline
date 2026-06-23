import queue
import threading
import time
from ingest import fetch_all_file_ids, start_parallel_downloads
from process import processing_worker

# Change this to your actual target folder ID from Google Drive
TARGET_FOLDER_ID = "1RuMyvED0_eEny30GEqKuZfbeNGlApLWn"

def run_pipeline():
    print("[Main] Initializing Smart Google Drive Sync...")
    
    # 1. Fetch file meta-information from Drive API
    try:
        files_to_download = fetch_all_file_ids(TARGET_FOLDER_ID)
        if not files_to_download:
            print("[Main] No files found in the specified folder or folder is empty.")
            return
        print(f"[Main] Found {len(files_to_download)} files to process.")
    except Exception as e:
        print(f"[Main Error] Failed to read folder contents: {str(e)}")
        return

    # 2. Setup Thread-Safe Queue and Worker Event Controls
    download_queue = queue.Queue(maxsize=15)
    stop_event = threading.Event()

    # 3. Spin up the Consumer (Processing Worker) in a background thread
    consumer_thread = threading.Thread(
        target=processing_worker, 
        args=(download_queue, stop_event),
        name="ProcessWorker"
    )
    consumer_thread.start()

    # 4. Run the Producer (Download Workers) in the main thread execution context
    # This will block until all downloads are completed and pushed to the queue
    start_parallel_downloads(files_to_download, download_queue, max_workers=5)

    # 5. Signal to the consumer that no more downloads are coming
    print("[Main] Ingestion complete. Waiting for processing queue to drain...")
    stop_event.set()

    # 6. Wait for the processing thread to finish clearing out the remaining items
    consumer_thread.join()
    print("[Main] Pipeline executed successfully. Data is indexed and ready.")

if __name__ == "__main__":
    start_time = time.time()
    run_pipeline()
    print(f"[Main] Finished execution in {round(time.time() - start_time, 2)} seconds.")