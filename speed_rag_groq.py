import asyncio
import os
import aiohttp
import json
from google.oauth2 import service_account
import google.auth.transport.requests

GROQ_API_KEY = "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"
FOLDER_ID = "1RuMyvED0_eEny30GEqKuZfbeNGlApLWn"
SERVICE_ACCOUNT_FILE = "service_account.json"

MAX_CONCURRENT_WORKERS = 3 
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, 
    scopes=["https://www.googleapis.com/auth/drive.readonly"]
)

async def get_token() -> str:
    if not creds.valid:
        await asyncio.to_thread(creds.refresh, google.auth.transport.requests.Request())
    return creds.token

async def fetch_folder_files(session: aiohttp.ClientSession) -> list:
    token = await get_token()
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "q": f"'{FOLDER_ID}' in parents and trashed = false",
        "fields": "files(id, name)"
    }
    
    print("🛰️  Scanning Google Drive folder...")
    async with session.get(url, headers=headers, params=params) as resp:
        if resp.status != 200:
            raise Exception(f"Drive API Error: {resp.status}")
        data = await resp.json()
        return data.get("files", [])

async def worker_download(session: aiohttp.ClientSession, file_id: str, file_name: str, semaphore: asyncio.Semaphore) -> str:
    async with semaphore:
        token = await get_token()
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {token}"}
        
        print(f"📥 [Worker Pool] Starting download: {file_name}")
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    raw_text = await resp.text(errors='ignore')
                    print(f"✅ [Worker Pool] Finished: {file_name}")
                    return f"--- START OF FILE: {file_name} ---\n{raw_text}\n--- END OF FILE ---\n\n"
                else:
                    print(f"❌ [Worker Pool] Failed downloading {file_name}. HTTP {resp.status}")
                    return ""
        except Exception as e:
            print(f"💥 [Worker Pool] Error downloading {file_name}: {e}")
            return ""

async def query_groq(session: aiohttp.ClientSession, prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    
    async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
        if resp.status == 200:
            result = await resp.json()
            return result["choices"][0]["message"]["content"]
        else:
            err_body = await resp.text()
            return f"Groq Error {resp.status}: {err_body}"

async def main():
    async with aiohttp.ClientSession() as session:
        try:
            files = await fetch_folder_files(session)
        except Exception as e:
            print(e)
            return

        if not files:
            print("⚠️ No files found in that folder.")
            return

        print(f"🚀 Initializing pool. Processing {len(files)} files with {MAX_CONCURRENT_WORKERS} parallel workers...")
        
        sem = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
        tasks = [worker_download(session, f['id'], f['name'], sem) for f in files]
        results = await asyncio.gather(*tasks)
        
        knowledge_base_context = "".join(results)
        print("\n📦 Context fully compiled in memory.")

        print("\n⚡ Groq Llama-3.3 Chat Active! (Type 'exit' to quit).")
        while True:
            user_query = input("\n👤 You: ")
            if user_query.strip().lower() == 'exit':
                break
            if not user_query.strip():
                continue

            full_prompt = (
                f"You are a smart assistant. Answer the user's question using ONLY the following source documents:\n\n"
                f"{knowledge_base_context}\n\n"
                f"User Question: {user_query}"
            )
            
            print("Thinking... ⚡")
            response_text = await query_groq(session, full_prompt)
            print(f"\n🤖 Llama-3.3: {response_text}")

if __name__ == "__main__":
    asyncio.run(main())