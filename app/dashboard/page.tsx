/* eslint-disable @typescript-eslint/no-explicit-any */
"use client"
import { useState } from "react"
import { useSession, signOut } from "next-auth/react"

export default function Dashboard() {
  const { data: session } = useSession()
  const [folderInput, setFolderInput] = useState("")
  const [query, setQuery] = useState("")
  const [syncStatus, setSyncStatus] = useState("")
  const [aiResponse, setAiResponse] = useState("")
  const [wasCached, setWasCached] = useState(false)

  // One chat "session" per browser tab load. Sent to the backend so multi-turn
  // conversation memory in Redis is scoped to this session_id (and, server-side,
  // to the signed-in user's email) instead of being shared across every tab/device.
  const [sessionId] = useState<string>(() => crypto.randomUUID())

  // Extracts the 33-character or similar Google Drive folder ID from a full URL or returns the raw input if it's already an ID
  const extractFolderId = (input: string): string => {
    const trimmed = input.trim()
    // Matches patterns like drive.google.com/drive/folders/FOLDER_ID or drive.google.com/drive/u/0/folders/FOLDER_ID
    const urlRegex = /\/folders\/([a-zA-Z0-9-_]{25,50})/
    const match = trimmed.match(urlRegex)

    return match ? match[1] : trimmed
  }

  const triggerSyncPipeline = async () => {
    if (!session?.user?.email) {
      setSyncStatus("Session not ready. Refresh the page and try again.")
      return
    }
    const accessToken = (session as any)?.accessToken
    if (!accessToken) {
      setSyncStatus("No Google access token. Sign out and sign back in, then retry.")
      return
    }
    if (!folderInput.trim()) {
      setSyncStatus("Paste a Google Drive folder URL or ID first.")
      return
    }

    const folderId = extractFolderId(folderInput)

    // Quick validation on extracted ID format to catch obvious garbage inputs before hitting backend
    if (!/^[a-zA-Z0-9-_]{25,50}$/.test(folderId)) {
      setSyncStatus("Invalid Google Drive folder URL or ID format.")
      return
    }

    setSyncStatus("Starting sync...")
    try {
      const res = await fetch("http://localhost:8000/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: session.user.email,
          folder_id: folderId,
          access_token: accessToken,
          refresh_token: (session as any)?.refreshToken ?? null,
        }),
      })
      const data = await res.json()
      setSyncStatus(data.status === "error" ? data.message : data.message)
    } catch {
      setSyncStatus("Failed connecting to Python backend.")
    }
  }

  const dispatchRAGQuery = async () => {
    setAiResponse("Querying index matrices...")
    setWasCached(false)
    try {
      const res = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: session?.user?.email,
          query: query,
          session_id: sessionId,
        }),
      })

      console.log("/query response status:", res.status)

      const text = await res.text()
      let data: any = null
      try {
        data = JSON.parse(text)
      } catch (e) {
        console.warn("/query: response not JSON, using raw text", e)
      }

      console.log("/query raw response:", text)

      const answer = data?.answer ?? text ?? "(no answer returned)"
      setAiResponse(answer)
      setWasCached(Boolean(data?.cached))
    } catch {
      setAiResponse("Pipeline query failure.")
    }
  }

  const startNewChat = async () => {
    if (!session?.user?.email) return
    try {
      await fetch("http://localhost:8000/session/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: session.user.email, session_id: sessionId }),
      })
    } catch {
      // Non-fatal - if this fails, worst case is the old memory sticks around until its TTL expires.
    }
    setAiResponse("")
    setQuery("")
    setWasCached(false)
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="flex justify-between items-center border-b border-neutral-800 pb-4">
          <div>
            <h1 className="text-2xl font-bold">Workspace Portal</h1>
            <p className="text-sm text-neutral-400">Authenticated as: {session?.user?.email}</p>
          </div>
          <button onClick={() => signOut({ callbackUrl: "/" })} className="text-sm bg-neutral-800 px-4 py-2 rounded">
            Sign Out
          </button>
        </header>

        {/* Sync Operations Card */}
        <section className="bg-neutral-900 border border-neutral-800 p-6 rounded-xl">
          <h2 className="text-lg font-semibold mb-3">Sync Source Context</h2>
          <div className="flex gap-4">
            <input
              type="text"
              placeholder="Paste Google Drive Folder URL or ID"
              value={folderInput}
              onChange={(e) => setFolderInput(e.target.value)}
              className="flex-1 bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white placeholder-neutral-500 text-sm focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button onClick={triggerSyncPipeline} className="bg-blue-600 hover:bg-blue-700 px-5 py-2 rounded-lg font-medium transition-colors text-sm">
              Initialize Sync
            </button>
          </div>
          {syncStatus && <p className="text-sm text-blue-400 mt-3">{syncStatus}</p>}
        </section>

        {/* Semantic Search RAG Card */}
        <section className="bg-neutral-900 border border-neutral-800 p-6 rounded-xl">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-lg font-semibold">Interactive Knowledge Interface</h2>
            <button onClick={startNewChat} className="text-xs text-neutral-400 hover:text-neutral-200 underline underline-offset-2">
              New chat
            </button>
          </div>
          <textarea
            rows={3}
            placeholder="Ask anything about your synced infrastructure context..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-4 text-white resize-none text-sm focus:outline-none focus:border-emerald-500 transition-colors"
          />
          <button onClick={dispatchRAGQuery} className="mt-3 bg-emerald-600 hover:bg-emerald-700 px-5 py-2 rounded-lg font-medium transition-colors text-sm">
            Execute Query
          </button>
          {aiResponse && (
            <div className="mt-4 p-4 bg-neutral-950 border border-neutral-800 rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Engine Output</h3>
                {wasCached && (
                  <span className="text-[10px] font-medium text-amber-400 uppercase tracking-wider">
                    ⚡ from cache
                  </span>
                )}
              </div>
              <p className="text-neutral-200 text-sm whitespace-pre-wrap">{aiResponse}</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}