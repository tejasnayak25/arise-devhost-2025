import React from 'react'
import { getComplianceChecklist } from '../services/complianceService'

export default function Compliance() {
  const items = getComplianceChecklist()
  return (
    <div className="panel">
      <h3>Compliance Checklist (CSRD • EU Taxonomy)</h3>
      <table>
        <thead>
          <tr>
            <th>Area</th>
            <th>Requirement</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i, idx) => (
            <tr key={idx}>
              <td>{i.area}</td>
              <td>{i.requirement}</td>
              <td>{i.status}</td>
              <td className="muted">{i.nextAction}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

