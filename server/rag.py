import os
from groq import Groq
from process import get_chroma_collection
from dotenv import load_dotenv

from redis_client import (
    get_cached_answer,
    set_cached_answer,
    get_session_history,
    append_session_turns,
)

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)


def _retrieve_context(user_query: str, active_user_email: str, num_results: int):
    """Runs the ChromaDB similarity search, scoped to this user's own documents."""
    collection = get_chroma_collection()

    print(f"\n[RAG] Searching vector database for user {active_user_email}...")
    results = collection.query(
        query_texts=[user_query],
        where={"user_owner": active_user_email},
        n_results=num_results,
    )

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
            return "No documents indexed yet. Sync a Google Drive folder first, then try your question again.", docs
        return "No relevant documents found for your account. Re-run Sync on your folder so files are tagged to your email.", docs

    formatted_context = "\n\n".join([f"[Context Fragment {i+1}]: {doc}" for i, doc in enumerate(docs)])
    return formatted_context, docs


async def query_smart_drive(
    user_query: str,
    active_user_email: str,
    session_id: str = "default",
    num_results: int = 4,
) -> tuple[str, bool]:
    """
    Retrieves relevant document fragments from ChromaDB and passes them, together with
    the user's recent chat history, to Groq to generate a clean, context-aware response.

    Returns a (answer, was_cached) tuple so callers/UI can show whether the answer
    came straight from the Redis cache.
    """
    # --- 1. Exact-match response cache: same user + same exact question recently? ---
    cached_answer = await get_cached_answer(active_user_email, user_query)
    if cached_answer is not None:
        print(f"[RAG] Cache hit for {active_user_email}. Skipping ChromaDB + Groq.")
        # Still record the turn so the conversation transcript stays coherent
        await append_session_turns(
            active_user_email,
            session_id,
            [
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": cached_answer},
            ],
        )
        return cached_answer, True

    # --- 2. Vector retrieval (multi-tenant isolated by user_owner metadata) ---
    context_or_message, docs = _retrieve_context(user_query, active_user_email, num_results)
    if not docs:
        # No documents at all / no relevant matches - context_or_message is already
        # a plain user-facing message in this case, not real document context.
        return context_or_message, False
    formatted_context = context_or_message

    # --- 3. Pull recent conversation history for this user+session ---
    history = await get_session_history(active_user_email, session_id)

    system_prompt = (
        "You are an intelligent document assistant. Your task is to have a helpful conversation "
        "with the user regarding their synced Google Drive documents.\n"
        "Use the provided Document Context fragments below to formulate your response. "
        "Be direct, accurate, and concise. Do not guess or make up facts. If the information "
        "is not present in the context, state that clearly.\n\n"
        f"--- DOCUMENT CONTEXT ---\n{formatted_context}\n------------------------"
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)  # prior turns for this user+session, if any
    messages.append({"role": "user", "content": user_query})

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.3,  # Lower temperature for more factual anchoring to the context
            max_tokens=1024,
        )
        answer = completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"[RAG Error] Failed Groq API inference call: {str(e)}")
        return f"Error communicating with Groq Engine: {str(e)}", False

    # --- 4. Update Redis: cache this exact Q&A, and extend conversation memory ---
    await set_cached_answer(active_user_email, user_query, answer)
    await append_session_turns(
        active_user_email,
        session_id,
        [
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": answer},
        ],
    )

    return answer, False


if __name__ == "__main__":
    # Interactive local debugging loop
    import asyncio

    test_email = "test@example.com"  # Replace with your actual email if testing locally via terminal
    test_session = "cli-session"
    print(f"--- Local RAG Console Interface Mode (Scoping: {test_email}) ---")

    async def _repl():
        while True:
            query = input("\nAsk a question about your files (or type 'exit'): ").strip()
            if query.lower() in ["exit", "quit"]:
                break
            if not query:
                continue
            answer, was_cached = await query_smart_drive(query, active_user_email=test_email, session_id=test_session)
            tag = "(from cache)" if was_cached else "(live)"
            print(f"\nGroq Response {tag}:\n{answer}")

    asyncio.run(_repl())