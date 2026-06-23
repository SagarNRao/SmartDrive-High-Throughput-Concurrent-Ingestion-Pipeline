import os
from groq import Groq
from process import get_chroma_collection
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

def query_smart_drive(user_query: str, active_user_email: str, num_results: int = 4):
    """Retrieves context from ChromaDB isolated by user owner metadata."""
    collection = get_chroma_collection()
    
    print(f"\n[RAG] Searching vector database for user {active_user_email}...")
    
    # query ChromaDB with a strict where clause mapping to the owner's email context
    results = collection.query(
        query_texts=[user_query],
        where={"user_owner": active_user_email}, 
        n_results=num_results
    )
    
    # ... keep the rest of your original rag.py logic exactly the same, 
    # but make sure the function returns 'answer' at the very end instead of just printing it.
    # return answer.strip()


if __name__ == "__main__":
    
    # Interactive query loop
    while True:
        query = input("Ask a question about your files (or type 'exit'): ").strip()
        if query.lower() in ['exit', 'quit']:
            break
        if not query:
            continue
        query_smart_drive(query)