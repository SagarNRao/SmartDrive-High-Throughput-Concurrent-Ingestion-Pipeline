"use client"
import { useState } from "react"
import { useSession, signOut } from "next-auth/react"

export default function Dashboard() {
  const { data: session } = useSession()
  const [folderId, setFolderId] = useState("")
  const [query, setQuery] = useState("")
  const [syncStatus, setSyncStatus] = useState("")
  const [aiResponse, setAiResponse] = useState("")

  const triggerSyncPipeline = async () => {
    setSyncStatus("Invoking thread execution runtime...")
    try {
      const res = await fetch("http://localhost:8000/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: session?.user?.email, // Active login context forwarded
          folder_id: folderId,
        }),
      })
      const data = await res.json()
      setSyncStatus(data.message)
    } catch {
      setSyncStatus("Failed connecting to Python backend.")
    }
  }

  const dispatchRAGQuery = async () => {
    setAiResponse("Querying index matrices...")
    try {
      const res = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: session?.user?.email,
          query: query,
        }),
      })
      const data = await res.json()
      setAiResponse(data.answer)
    } catch {
      setAiResponse("Pipeline query failure.")
    }
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
              placeholder="Paste Google Drive Folder ID"
              value={folderId}
              onChange={(e) => setFolderId(e.target.value)}
              className="flex-1 bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white"
            />
            <button onClick={triggerSyncPipeline} className="bg-blue-600 hover:bg-blue-700 px-5 py-2 rounded-lg font-medium">
              Initialize Sync
            </button>
          </div>
          {syncStatus && <p className="text-sm text-blue-400 mt-3">{syncStatus}</p>}
        </section>

        {/* Semantic Search RAG Card */}
        <section className="bg-neutral-900 border border-neutral-800 p-6 rounded-xl">
          <h2 className="text-lg font-semibold mb-3">Interactive Knowledge Interface</h2>
          <textarea
            rows={3}
            placeholder="Ask anything about your synced infrastructure context..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-4 text-white resize-none"
          />
          <button onClick={dispatchRAGQuery} className="mt-3 bg-emerald-600 hover:bg-emerald-700 px-5 py-2 rounded-lg font-medium">
            Execute Query
          </button>
          {aiResponse && (
            <div className="mt-4 p-4 bg-neutral-950 border border-neutral-800 rounded-lg">
              <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Engine Output</h3>
              <p className="text-neutral-200 text-sm whitespace-pre-wrap">{aiResponse}</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}