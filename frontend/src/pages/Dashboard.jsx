import React from 'react'
import KPIs from '../shared/KPIs'
import EmissionsChart from '../shared/EmissionsChart'
import AISidebar from '../shared/AISidebar'
import { getLatestEmissionsTimeSeries, getAggregatedKPIs } from '../services/dataService'
import { useAuth } from '../contexts/AuthContext';

export default function Dashboard() {
  const { user } = useAuth();
  const series = getLatestEmissionsTimeSeries()
  const kpis = getAggregatedKPIs()

  return (
    <div className="layout-two">
      <div className="stack">
        <div className="grid cols-3">
          {kpis.map((k) => (
            <KPIs key={k.label} label={k.label} value={k.value} delta={k.delta} />
          ))}
        </div>
        <div className="panel">
          <h3>Emissions Trend (tCO₂e)</h3>
          <EmissionsChart data={series} />
        </div>
        <div className="panel">
          <h3>Tasks & Actions</h3>
          <ul className="muted">
            <li>Connect electricity invoices via Data Sources</li>
            <li>Upload Scope 3 supplier data (CSV)</li>
            <li>Review CSRD datapoints completeness</li>
          </ul>
        </div>
      </div>
      <AISidebar user={user} />
    </div>
  )
}

