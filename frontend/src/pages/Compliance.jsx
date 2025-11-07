import React, { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

export default function Compliance() {
  const { user } = useAuth()
  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(false)
  const [regulations, setRegulations] = useState([])
  const [findings, setFindings] = useState([])

  useEffect(() => {
    if (!user?.email) return
    fetch(`/api/user-company?email=${encodeURIComponent(user.email)}`)
      .then(r => r.json())
      .then(c => setCompany(c))
      .catch(() => setCompany(null))
  }, [user?.email])

  async function runCompare() {
    if (!company?.id) return alert('Please join or create a company first')
    setLoading(true)
    try {
      const res = await fetch('/api/compliance/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: company.id, prompt: 'Compare monthly invoice data against regulations' })
      })
      const data = await res.json()
      setRegulations(data.regulations || [])
      setFindings(data.findings || [])
    } catch (e) {
      console.error('Compare error', e)
      alert('Failed to run compliance compare')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <h3>Compliance Checklist & Analysis</h3>
      <p className="muted">Compare latest monthly invoices against applicable regulations (CSRD, EU Taxonomy).</p>
      <div style={{ marginBottom: 12 }}>
        <button className="btn" onClick={runCompare} disabled={!company || loading}>{loading ? 'Running…' : 'Compare with Regulations'}</button>
      </div>

      {regulations.length > 0 && (
        <div>
          <h4>Regulations referenced</h4>
          <ul>
            {regulations.map(r => (
              <li key={r.id}><strong>{r.id}</strong>: {r.title} — {r.requirement}</li>
            ))}
          </ul>
        </div>
      )}

      {findings.length > 0 && (
        <div>
          <h4>Compliance Findings</h4>
          <table>
            <thead>
              <tr>
                <th>Regulation</th>
                <th>Status</th>
                <th>Explanation</th>
                <th>Recommended</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, idx) => (
                <tr key={idx}>
                  <td>{f.regulation_id || f.regulation_title}</td>
                  <td>{f.compliance_status}</td>
                  <td style={{ maxWidth: 400 }}>{f.explanation}</td>
                  <td style={{ maxWidth: 400 }}>{f.recommended_actions || f.recommendedActions || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

