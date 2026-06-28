import os
from groq import Groq
from process import get_chroma_collection
from dotenv import load_dotenv

load_dotenv()

# Fallback hardcoded key from your snippet, though pulling from environment variables is preferred
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

def query_smart_drive(user_query: str, active_user_email: str, num_results: int = 4) -> str:
    """
    Retrieves relevant document fragments from ChromaDB and passes them to Groq 
    to generate a clean, accurate context-aware response.
    """
    collection = get_chroma_collection()
    
    print(f"\n[RAG] Searching vector database for user {active_user_email}...")
    
    # Query ChromaDB with metadata isolation for multi-tenancy
    results = collection.query(
        query_texts=[user_query],
        where={"user_owner": active_user_email}, 
        n_results=num_results
    )

    # Robust document extraction
    docs = []
    try:
        docs = results.get("documents", [[]])[0]
    except Exception:
        try:
            docs = getattr(results, "documents", [[]])[0]
        except Exception:
            docs = []

    print(f"[RAG] Retrieved {len(docs)} candidate passages for user {active_user_email}.")

    if not docs:
        if collection.count() == 0:
            return "No documents indexed yet. Sync a Google Drive folder first, then try your question again."
        return "No relevant documents found for your account. Re-run Sync on your folder so files are tagged to your email."

    # Format the pulled vector contexts cleanly for the LLM injection
    formatted_context = "\n\n".join([f"[Context Fragment {i+1}]: {doc}" for i, doc in enumerate(docs)])

    # Construct system instructions forcing the model to rely on your data
    system_prompt = (
        "You are an intelligent document assistant. Your task is to have a helpful conversation "
        "with the user regarding their synced Google Drive documents.\n"
        "Use the provided Document Context fragments below to formulate your response. "
        "Be direct, accurate, and concise. Do not guess or make up facts. If the information "
        "is not present in the context, state that clearly.\n\n"
        f"--- DOCUMENT CONTEXT ---\n{formatted_context}\n------------------------"
    )

    try:
        # Call the Groq SDK inference endpoint
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.3, # Lower temperature for more factual anchoring to the context
            max_tokens=1024,
        )
        
        answer = completion.choices[0].message.content
        return answer.strip()

    except Exception as e:
        print(f"[RAG Error] Failed Groq API inference call: {str(e)}")
        return f"Error communicating with Groq Engine: {str(e)}"


if __name__ == "__main__":
    # Interactive local debugging loop
    test_email = "test@example.com"  # Replace with your actual email if testing locally via terminal
    print(f"--- Local RAG Console Interface Mode (Scoping: {test_email}) ---")
    while True:
        query = input("\nAsk a question about your files (or type 'exit'): ").strip()
        if query.lower() in ['exit', 'quit']:
            break
        if not query:
            continue
        response = query_smart_drive(query, active_user_email=test_email)
        print(f"\nGroq Response:\n{response}")