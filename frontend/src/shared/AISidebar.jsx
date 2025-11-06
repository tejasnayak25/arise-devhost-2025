import React, { useMemo } from 'react'
import { getAiInsights } from '../services/aiService'

export default function AISidebar() {
  const insights = useMemo(() => getAiInsights(), [])
  return (
    <aside className="panel" style={{ height: '100%', position: 'sticky', top: 20 }}>
      <h3>AI Assistant</h3>
      <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
        Automated analysis of your latest activity and gaps.
      </div>
      <ul style={{ display: 'grid', gap: 10, paddingLeft: 18 }}>
        {insights.map((i, idx) => (
          <li key={idx}>
            <div style={{ fontWeight: 600 }}>{i.title}</div>
            <div className="muted" style={{ fontSize: 13 }}>{i.detail}</div>
          </li>
        ))}
      </ul>
      <div style={{ marginTop: 12 }}>
        <button className="btn">Suggest reduction roadmap</button>
      </div>
    </aside>
  )
}

