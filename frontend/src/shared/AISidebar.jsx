
import React, { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { getAiInsights } from '../services/aiService'


export default function AISidebar({ user, company }) {
  const insights = useMemo(() => getAiInsights(), [])
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Hi! I can analyze your carbon reports and answer sustainability questions.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  // Handler for sending a message
  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim()) return;
    setMessages(msgs => [...msgs, { role: 'user', text: input }]);
    setLoading(true);
    try {
      // If user asks for report analysis, call backend
      let aiReply = '';
      if (/analy[sz]e|report|emission|carbon|footprint|summary|insight/i.test(input)) {
        // Call backend Gemini endpoint
        const res = await fetch(`/api/analyze-current-month-report?company_id=${encodeURIComponent(company?.id)}`, {
          method: 'POST',
          body: input
        });
        const data = await res.json();
        aiReply = data.analysis || 'Sorry, I could not analyze the report.';
      } else {
        aiReply = "I'm here to help with carbon analytics. Ask me to analyze your current month report or provide sustainability advice.";
      }
      setMessages(msgs => [...msgs, { role: 'ai', text: aiReply }]);
    } catch (err) {
      setMessages(msgs => [...msgs, { role: 'ai', text: 'Sorry, there was an error contacting the AI service.' }]);
    } finally {
      setLoading(false);
      setInput('');
    }
  }

  return (
    <aside className="panel ai-sidebar">
      <h3>AI Assistant</h3>
      <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
        Automated analysis of your latest activity and gaps.
      </div>
      <ul className="chat-list">
        {messages.map((m, idx) => (
          <li key={idx} className={m.role === 'ai' ? 'msg-left' : 'msg-right'}>
            <div className={`chat-bubble ${m.role === 'ai' ? 'ai' : 'user'}`}>
              {m.role === 'ai' ? <ReactMarkdown>{m.text}</ReactMarkdown> : m.text}
            </div>
          </li>
        ))}
      </ul>
      <form onSubmit={handleSend} className='chat-form' style={{ display: 'flex', gap: 4, marginTop: 8 }}>
        <input
          className="input"
          style={{ flex: 1 }}
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about your carbon report..."
          disabled={loading}
        />
        <button className="btn" type="submit" disabled={loading || !input.trim()}>Send</button>
      </form>
    </aside>
  )
}

