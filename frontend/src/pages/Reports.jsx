import React from 'react'
import { generateESGReportPreview } from '../services/reportingService'

export default function Reports() {
  const preview = generateESGReportPreview()
  return (
    <div className="panel">
      <h3>ESG Report Preview (CSRD-aligned)</h3>
      <p className="muted">This is a synthetic example. Replace with real data once connected.</p>
      <table>
        <thead>
          <tr>
            <th>Section</th>
            <th>Metric</th>
            <th>Value</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {preview.map((row, i) => (
            <tr key={i}>
              <td>{row.section}</td>
              <td>{row.metric}</td>
              <td>{row.value}</td>
              <td className="muted">{row.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn">Export PDF</button>
        <button className="btn secondary">Export XLSX</button>
      </div>
    </div>
  )
}

