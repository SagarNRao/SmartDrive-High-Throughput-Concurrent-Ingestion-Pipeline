import os
from groq import Groq
from process import get_chroma_collection

# Configuration
# Best practice: Export this in your shell as `export GROQ_API_KEY="your_key"`
# Or explicitly pass it here: Groq(api_key="your_actual_api_key_here")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "your_actual_api_key_here")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

def query_smart_drive(user_query: str, num_results: int = 4):
    """Retrieves context from ChromaDB and generates an answer using Groq Cloud API."""
    collection = get_chroma_collection()
    
    # 1. Search vector database for closest matching documentation chunks
    print(f"\n[RAG] Searching vector database for: '{user_query}'...")
    results = collection.query(
        query_texts=[user_query],
        n_results=num_results
    )
    
    retrieved_docs = results.get("documents", [[]])[0]
    retrieved_metadata = results.get("metadatas", [[]])[0]
    
    if not retrieved_docs:
        print("[RAG] No relevant context found in your database.")
        return
        
    # 2. Compile structural text chunks into single context block
    context = "\n---\n".join(retrieved_docs)
    
    # Print sources being fed to the model context window
    sources = list(set([m['file_name'] for m in retrieved_metadata]))
    print(f"[RAG] Injecting context from files: {sources}")

    # 3. Construct System Prompt instructing constraints
    system_instruction = (
        "You are an intelligent assistant analyzing the user's Google Drive files.\n"
        "Answer the question using ONLY the provided context extracted from their documents.\n"
        "If you do not know the answer or if it's not explicitly in the context, say exactly:\n"
        "'I cannot find that information in your synced files.' Do not invent facts."
    )
    
    user_message = f"CONTEXT:\n{context}\n\nQUESTION: {user_query}"

    # 4. Dispatch text generation payload to Groq
    print(f"[RAG] Sending context to Groq ({GROQ_MODEL})...")
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ],
            model=GROQ_MODEL,
            temperature=0.0  # Keep it zero to minimize hallucination risks
        )
        
        # 5. Output response
        answer = chat_completion.choices[0].message.content
        print("\n=== ANSWER ===")
        print(answer.strip())
        print("==============\n")
        
    except Exception as e:
        print(f"[RAG Error] Failed to generate response from Groq API: {str(e)}")

if __name__ == "__main__":
    # Interactive query loop
    while True:
        query = input("Ask a question about your files (or type 'exit'): ").strip()
        if query.lower() in ['exit', 'quit']:
            break
        if not query:
            continue
        query_smart_drive(query)