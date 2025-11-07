import React, { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

export default function Reports() {
  const { user } = useAuth()
  const [company, setCompany] = useState(null)
  const [reports, setReports] = useState([])

  useEffect(() => {
    if (!user?.email) return
    fetch(`/api/user-company?email=${encodeURIComponent(user.email)}`)
      .then(r => r.json())
      .then(c => {
        setCompany(c)
        return fetch(`/api/reports?company_id=${encodeURIComponent(c.id)}`)
      })
      .then(r => r.json())
      .then(data => setReports(data.files || []))
      .catch(() => setReports([]))
  }, [user?.email])

  function download(path) {
    if (!path) return
    fetch(`/api/reports/download?path=${encodeURIComponent(path)}&&company_id=${encodeURIComponent(company.id)}`)
      .then(r => r.json())
      .then(data => {
        if (data.url) {
          let a = document.createElement('a');
          a.href = data.url+"&&download="+path;
          a.download = path;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
        }
      })
  }

  return (
    <div className="panel">
      <h3>Generated Reports</h3>
      <p className="muted">Monthly reports are generated automatically and stored.</p>
      <ul style={{display: "flex", flexDirection: "column", gap: "10px"}}>
        {reports.length === 0 && <li className="muted">No reports available yet.</li>}
        {reports.map((r, i) => (
          <li key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span>{r.name || r}</span>
            <div>
              <button className="btn" onClick={() => download(r.path || r)}>Download</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

