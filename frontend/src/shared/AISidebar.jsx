
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
  const [showQuickPrompts, setShowQuickPrompts] = useState(true);
  const [quickPromptsDismissed, setQuickPromptsDismissed] = useState(false);

  const quickPrompts = [
    'Summarize my current month emissions and top contributors.',
    'How can I reduce electricity emissions by 20%?',
    'List missing data for CSRD compliance.',
    'Explain how invoice items map to Scope 1/2/3.'
  ]

  // Handler for sending a message
  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim()) return;
  // hide quick prompts permanently once the user sends a message
  setShowQuickPrompts(false);
  setQuickPromptsDismissed(true);
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

  // Send a quick prompt from the suggested list
  async function sendQuickPrompt(text) {
    if (!text) return;
    setInput(text);
  // hide quick prompts permanently as soon as a quick prompt is used
  setShowQuickPrompts(false);
  setQuickPromptsDismissed(true);
    // re-use handleSend by calling it artificially with a synthetic event
    // but easiest is to call the same logic here to avoid DOM event construction
    setMessages(msgs => [...msgs, { role: 'user', text }]);
    setLoading(true);
    try {
      let aiReply = '';
      if (/analy[sz]e|csrd|invoice|report|emission|carbon|footprint|summary|insight/i.test(text)) {
        const res = await fetch(`/api/analyze-current-month-report?company_id=${encodeURIComponent(company?.id)}`, {
          method: 'POST',
          body: text
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
      {showQuickPrompts && (
        <div style={{ marginTop: 8 }}>
          <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>Try a quick question:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {quickPrompts.map((q, i) => (
              <button key={i} className="btn small" style={{fontWeight: "normal", textAlign: "left"}} onClick={() => sendQuickPrompt(q)} disabled={loading}>{q}</button>
            ))}
          </div>
        </div>
      )}
      <form onSubmit={handleSend} className='chat-form' style={{ display: 'flex', gap: 4, marginTop: 8 }}>
        <input
          className="input"
          style={{ flex: 1 }}
          value={input}
          onChange={e => {
            const v = e.target.value || ''
            setInput(v)
            setShowQuickPrompts(!quickPromptsDismissed && v.trim().length === 0)
          }}
          placeholder="Ask about your carbon report..."
          disabled={loading}
        />
        <button
          className="btn"
          type="submit"
          disabled={loading || !input.trim()}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
        >
          {loading ? (
            <>
              <svg width="16" height="16" viewBox="0 0 38 38" xmlns="http://www.w3.org/2000/svg" stroke="#000">
                <g fill="none" fillRule="evenodd">
                  <g transform="translate(1 1)" strokeWidth="2">
                    <circle strokeOpacity="0.5" cx="18" cy="18" r="18" />
                    <path d="M36 18c0-9.94-8.06-18-18-18">
                      <animateTransform
                        attributeName="transform"
                        type="rotate"
                        from="0 18 18"
                        to="360 18 18"
                        dur="0.9s"
                        repeatCount="indefinite" />
                    </path>
                  </g>
                </g>
              </svg>
              {/* <span>Sending...</span> */}
            </>
          ) : (
            'Send'
          )}
        </button>
      </form>
    </aside>
  )
}

