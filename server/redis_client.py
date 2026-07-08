"""
Redis integration for SmartDrive.

What this gives you:
- One shared ASYNC Redis connection (redis.asyncio) so Redis calls never block
  FastAPI's event loop.
- Response caching: same user + same exact question -> instant answer, no
  ChromaDB / Groq call. 24h TTL.
- Conversation memory: per user + per chat session, so multi-turn chat has
  context. 2h *sliding* TTL (every new message resets the clock).
- Strict multi-tenant key namespacing so one user can never read another
  user's cache or chat history.
- Graceful degradation: every function below is wrapped in try/except. If
  Redis is down/unreachable, we log it and return a safe fallback (None / []
  / do nothing) so the app just runs the normal ChromaDB + Groq pipeline as if
  Redis didn't exist.

You don't need to know much about Redis to use this file - just call the
functions below from rag.py / api.py.
"""

import os
import json
import hashlib
import logging

import redis.asyncio as redis

logger = logging.getLogger("smartdrive.redis")
logging.basicConfig(level=logging.INFO)

# Point this at your Redis instance, e.g. "redis://localhost:6379/0"
# or a managed Redis URL in production.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# --- Safe defaults, per your spec ---
CACHE_TTL_SECONDS = 86400    # 24 hours - response cache
SESSION_TTL_SECONDS = 7200   # 2 hours  - conversation memory (sliding window)

# Keep the stored chat history small/light - only remember the last N turns
# (a "turn" here = one message, so 12 = ~6 user/assistant exchanges).
MAX_SESSION_TURNS = 12

_redis_client: "redis.Redis | None" = None


def get_redis_client() -> redis.Redis:
    """Lazily creates a single shared async Redis connection pool for the app."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def ping_redis() -> bool:
    """Optional health check you can call on FastAPI startup. Never raises."""
    try:
        r = get_redis_client()
        await r.ping()
        logger.info("[Redis] Connected OK.")
        return True
    except Exception as e:
        logger.error(f"[Redis] Not reachable at startup ({REDIS_URL}): {e}. "
                      f"App will run without caching/session memory until Redis is back.")
        return False


async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception as e:
            logger.error(f"[Redis] Error closing client: {e}")
        _redis_client = None


def _normalize_query(query: str) -> str:
    return query.strip().lower()


def _cache_key(user_email: str, query: str) -> str:
    # Hash the query so keys stay short and never leak raw question text into key names/logs.
    query_hash = hashlib.sha256(_normalize_query(query).encode("utf-8")).hexdigest()
    return f"cache:{user_email}:{query_hash}"


def _session_key(user_email: str, session_id: str) -> str:
    return f"session:{user_email}:{session_id}"


# ---------------------------------------------------------------------------
# 1. Response cache
# ---------------------------------------------------------------------------

async def get_cached_answer(user_email: str, query: str) -> str | None:
    """Returns a cached answer for this exact user+query, or None on miss/error."""
    try:
        r = get_redis_client()
        return await r.get(_cache_key(user_email, query))
    except Exception as e:
        logger.error(f"[Redis] Cache GET failed, falling back to live pipeline: {e}")
        return None


async def set_cached_answer(user_email: str, query: str, answer: str) -> None:
    """Stores the answer with a 24h expiration. Failures are logged and swallowed."""
    try:
        r = get_redis_client()
        await r.set(_cache_key(user_email, query), answer, ex=CACHE_TTL_SECONDS)
    except Exception as e:
        logger.error(f"[Redis] Cache SET failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# 2. Conversation session memory
# ---------------------------------------------------------------------------

async def get_session_history(user_email: str, session_id: str) -> list[dict]:
    """Returns stored [{role, content}, ...] turns for this user+session, or [] on miss/error."""
    try:
        r = get_redis_client()
        raw = await r.get(_session_key(user_email, session_id))
        if not raw:
            return []
        return json.loads(raw)
    except Exception as e:
        logger.error(f"[Redis] Session GET failed, treating as empty history: {e}")
        return []


async def append_session_turns(user_email: str, session_id: str, new_turns: list[dict]) -> None:
    """
    Appends turns (e.g. the user's question + the assistant's answer) to the session
    history, trims to the most recent MAX_SESSION_TURNS, and refreshes the 2h TTL
    (this is what makes it a *sliding* window - active chats never expire mid-conversation).
    Failures are logged and swallowed so chat keeps working, just without memory.
    """
    try:
        r = get_redis_client()
        key = _session_key(user_email, session_id)
        raw = await r.get(key)
        history = json.loads(raw) if raw else []
        history.extend(new_turns)
        history = history[-MAX_SESSION_TURNS:]
        await r.set(key, json.dumps(history), ex=SESSION_TTL_SECONDS)
    except Exception as e:
        logger.error(f"[Redis] Session write failed (non-fatal): {e}")


async def clear_session(user_email: str, session_id: str) -> None:
    """Deletes a user's session history - handy for a 'New Chat' button."""
    try:
        r = get_redis_client()
        await r.delete(_session_key(user_email, session_id))
    except Exception as e:
        logger.error(f"[Redis] Session DELETE failed (non-fatal): {e}")
