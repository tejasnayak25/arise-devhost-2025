import React, { useEffect, useState, useMemo, useCallback } from 'react'
import KPIs from '../shared/KPIs'
import EmissionsChart from '../shared/EmissionsChart'
import EmissionsBreakdown from '../shared/EmissionsBreakdown'
import AISidebar from '../shared/AISidebar'
import EmissionsComparison from '../shared/EmissionsComparison'
import { getLatestEmissionsTimeSeries, getAggregatedKPIs, getLastMonthInvoiceData, computeItemLevelEmissions } from '../services/dataService'
import { useAuth } from '../contexts/AuthContext';
import CompanyRequired from '../shared/CompanyRequired';
import { getUserCompany } from '../services/companyService';


export default function Dashboard() {
  const { user } = useAuth();
  const [company, setCompany] = useState(undefined); // undefined = loading, null = not in company
  const [invoiceData, setInvoiceData] = useState(null);
  const [itemEmissions, setItemEmissions] = useState(null);
  const [fallbackItemEmissions, setFallbackItemEmissions] = useState(null);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  // Memoize derived KPIs and series to avoid recalculation on every render
  const kpis = useMemo(() => getAggregatedKPIs(invoiceData), [invoiceData]);
  const series = useMemo(() => getLatestEmissionsTimeSeries(invoiceData), [invoiceData]);

  // combined emissions including sensors
  const combinedEmissions = useMemo(() => {
    const inv = invoiceData?.total_emissions || 0
    const sensors = invoiceData?.sensor_emissions || 0
    return +(inv + sensors).toFixed(6)
  }, [invoiceData])

  // Build a comparison series of daily positive (removal) vs negative (emitted) emissions
  const comparisonSeries = useMemo(() => {
    const rows = invoiceData?.raw || []
    const map = {}
    for (const r of rows) {
      const d = (r.date || '').slice(0,10) || null
      if (!d) continue
      let qty = r.quantity
      if (typeof qty !== 'number') continue
      const isPos = !!r.is_positive
      console.log(r)
      if (!map[d]) map[d] = { date: d, positive: 0, negative: 0 }
      if (isPos) map[d].positive += qty
      else map[d].negative += qty
    }
    return Object.values(map).sort((a,b) => a.date.localeCompare(b.date))
  }, [invoiceData])

  const handleCompanySuccess = useCallback(() => {
    // Refresh company info after join/create
    if (user?.email) {
      getUserCompany(user.email).then(setCompany).catch(() => setCompany(null));
    }
  }, [user?.email]);

  useEffect(() => {
    if (user?.email) {
      getUserCompany(user.email)
        .then(setCompany)
        .catch(() => setCompany(null));
    }
    // Only run when user.email changes
  }, [user?.email]);

  useEffect(() => {
    if (company && company.id) {
      setLoading(true);
      // Fetch invoice data then concurrently request item-level emissions (LLM) and fallback computation
      getLastMonthInvoiceData(company.id)
        .then((res) => {
          setInvoiceData(res);
          setItemsLoading(true);

          const llmFetch = fetch(`/api/company-item-emissions?company_id=${encodeURIComponent(company.id)}`)
            .then(r => r.json()).then(d => d.items || null).catch(() => null);

          const fallbackCalc = computeItemLevelEmissions(res).catch(() => null);

          Promise.allSettled([llmFetch, fallbackCalc]).then((results) => {
            // results[0] = llm, results[1] = fallback
            if (results[0].status === 'fulfilled') setItemEmissions(results[0].value);
            else setItemEmissions(null);

            if (results[1].status === 'fulfilled') setFallbackItemEmissions(results[1].value);
            else setFallbackItemEmissions(null);

            setItemsLoading(false);
          });
        })
        .catch(() => setInvoiceData(null))
        .finally(() => setLoading(false));
    }
    // Only run when company.id changes
  }, [company?.id]);

  // Only return after all hooks
  if (company === undefined) {
    return <div className="panel">Checking organization membership...</div>;
  }
  if (!company) {
    return <CompanyRequired user={user} onSuccess={handleCompanySuccess} />;
  }
  if (loading) {
    return <div className="panel">Loading carbon footprint report...</div>;
  }

  return (
    <div className="layout-two">
      <div className="stack">
        <div className="grid cols-3">
          {/* Combined emissions KPI (invoices + sensors) */}
          <KPIs key="combined-emissions" label="Total Emissions" value={`${combinedEmissions} kg`} />
          {kpis.map((k) => (
            <KPIs key={k.label} label={k.label} value={k.value} delta={k.delta} />
          ))}
        </div>
        <div className="panel">
          <h3>Carbon Footprint Report (Current Month)</h3>
          {invoiceData && invoiceData.total_emissions !== undefined ? (
            <>
              <p><b>Invoice-derived Emissions:</b> {invoiceData.total_emissions} kg CO₂e</p>
              <p><b>Sensor-derived Emissions:</b> {invoiceData.sensor_emissions ?? 0} kg CO₂e</p>
              <p><b>Combined Emissions (invoices + sensors):</b> {combinedEmissions} kg CO₂e</p>
              <p><b>Total Spend:</b> {invoiceData.total_spend} €</p>
              <p><b>Invoices Processed:</b> {invoiceData.raw ? invoiceData.raw.length : 0}</p>
              <p><b>No. of sensors:</b> {invoiceData.sensor_count ?? 0}</p>
              <p><b>Breakdown by Type:</b> {Object.entries(invoiceData.item_counts || {}).map(([type, count]) => `${type}: ${count}`).join(', ')}</p>
            </>
          ) : (
            <p>No invoice data found for current month.</p>
          )}
        </div>
        <div className="panel">
          <h3>Emissions Trend (kg CO₂e)</h3>
          <EmissionsChart data={series} />
        </div>
        <div className="panel">
          <h3>Emission Comparison: Removals vs Emitted</h3>
          <EmissionsComparison data={comparisonSeries} />
        </div>
        <div className="panel">
          <h3>Emissions Breakdown</h3>
          <EmissionsBreakdown invoiceKg={invoiceData?.total_emissions || 0} sensorKg={invoiceData?.sensor_emissions || 0} />
        </div>
        <div className="panel">
          <h3>Emissions Items (invoices + sensors)</h3>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            <input
              aria-label="Search items"
              placeholder="Search items, unit or type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: 1, padding: '6px 8px' }}
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} style={{ padding: '6px 8px' }}>Clear</button>
            )}
          </div>
          {/* Build a unified list from LLM/fallback item emissions and sensor summaries */}
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Quantity</th>
                <th>Unit</th>
                <th>Factor (kg CO₂e/unit)</th>
                <th>Emissions (kg CO₂e)</th>
                {/* <th>Calculation</th> */}
              </tr>
            </thead>
            <tbody>
              {(() => {
                // Normalize invoice items list
                // While itemsLoading is true, show placeholder rows instead of mapping real data
                if (itemsLoading) {
                  return (
                    <>
                      {[0,1,2,3,4].map((i) => (
                        <tr key={`placeholder-${i}`} style={{ opacity: 0.9 }}>
                          <td><span className="skeleton skeleton-line skeleton-full" /></td>
                          <td><span className="skeleton skeleton-small" /></td>
                          <td><span className="skeleton skeleton-mid" /></td>
                          <td><span className="skeleton skeleton-small" /></td>
                          <td><span className="skeleton skeleton-small" /></td>
                        </tr>
                      ))}
                    </>
                  )
                }

                const invoiceList = (itemEmissions && Array.isArray(itemEmissions) ? itemEmissions : (fallbackItemEmissions || []))
                  .map(it => ({
                    source: 'invoice',
                    name: it.name || '(invoice item)',
                    quantity: it.quantity ?? null,
                    unit: it.unit || 'item',
                    factor: it.factor ?? null,
                    emissions: it.emissions ?? null,
                    is_positive: !!it.is_positive,
                    // formula: it.formula || ''
                  }));

                // Normalize sensor summaries into the same shape
                const sensorList = (invoiceData?.sensor_summaries || []).map(s => {
                  const energy = s.energy_kwh ?? 0
                  const emissions = s.emissions_kg ?? 0
                  const factor = energy ? +(emissions / energy).toFixed(6) : (s.meta && s.meta.emission_factor) || null
                  return {
                    source: 'sensor',
                    name: `Sensor: ${s.device_id ?? s.sensor_id ?? (s.meta && s.meta.device_id) ?? 'unknown'}`,
                    quantity: energy,
                    unit: 'kWh',
                    factor: factor,
                    emissions: emissions,
                    // formula: factor ? `${energy} * ${factor} = ${emissions}` : `emissions: ${emissions} kg CO₂e`
                  }
                })

                const combined = [...invoiceList, ...sensorList]
                const q = (searchQuery || '').trim().toLowerCase();
                const filtered = q
                  ? combined.filter((it) => {
                      const name = (it.name || '').toString().toLowerCase();
                      const unit = (it.unit || '').toString().toLowerCase();
                      return name.includes(q) || unit.includes(q) || (it.source || '').toString().toLowerCase().includes(q)
                    })
                  : combined;

                if (filtered.length === 0) {
                  return (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', color: '#666' }}>No items match your search.</td>
                    </tr>
                  );
                }

                console.log('rendering items', filtered);

                return filtered.map((it, i) => (
                  <tr key={`${it.source}-${i}`}>
                    <td>
                      {it.name}
                      {it.source === 'invoice' && it.is_positive && (
                        <span style={{ marginLeft: 8, color: '#34d399', fontWeight: 700 }}>↗ removal</span>
                      )}
                    </td>
                    <td>{it.quantity ?? '-'}</td>
                    <td>{it.unit || '-'}</td>
                    <td>{it.factor ?? '-'}</td>
                    <td style={{ color: (it.is_positive ? '#34d399' : undefined) }}>{it.emissions ?? '-'}</td>
                    {/* <td style={{ maxWidth: 400, whiteSpace: 'normal' }}>{it.formula}</td> */}
                  </tr>
                ))
              })()}
            </tbody>
          </table>
        </div>
        {invoiceData?.sensor_summaries && invoiceData.sensor_summaries.length > 0 && (
          <div className="panel">
            <h3>Sensor Summaries</h3>
            <table>
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Energy (kWh)</th>
                  <th>Emissions (kg CO₂e)</th>
                  <th>On Hours</th>
                  <th>Cycles</th>
                </tr>
              </thead>
              <tbody>
                {invoiceData.sensor_summaries.map((s, i) => (
                  <tr key={i}>
                    <td>{s.device_id ?? s.sensor_id ?? (s.meta && s.meta.device_id) ?? 'unknown'}</td>
                    <td>{s.energy_kwh}</td>
                    <td>{s.emissions_kg}</td>
                    <td>{s.on_hours}</td>
                    <td>{s.cycles}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="panel">
          <h3>Tasks & Actions</h3>
          <ul className="muted">
            <li>Connect electricity invoices via Data Sources</li>
            <li>Upload Scope 3 supplier data (CSV)</li>
            <li>Review CSRD datapoints completeness</li>
          </ul>
        </div>
      </div>
      <AISidebar user={user} company={company} />
    </div>
  );
}

