// app/chat/page.js
'use client';
import { useState } from 'react';
import { useSession } from 'next-auth/react';

export default function ChatPage() {
  const { data: session } = useSession();
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');

  const handleAsk = async () => {
    setAnswer('Searching database and generating response...');
    const response = await fetch('http://localhost:8000/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: session?.user?.email,
        query: query
      }),
    });
    const data = await response.json();
    setAnswer(data.answer);
  };

  return (
    <div className="p-8">
      <h1>Chat with your Drive</h1>
      <textarea 
        value={query} 
        onChange={(e) => setQuery(e.target.value)} 
        placeholder="Ask something about your synced files..."
        className="border w-full p-2 text-black"
      />
      <button onClick={handleAsk} className="bg-green-500 p-2 text-white mt-2">Ask AI</button>
      {answer && <div className="mt-4 p-4 bg-gray-100 border text-black">{answer}</div>}
    </div>
  );
}