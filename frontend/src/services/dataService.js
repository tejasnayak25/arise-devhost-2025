
// All data is now fetched from backend API. No DB logic in frontend.


// Fetch last month's invoice data for a company (including carbon emissions)
export async function getLastMonthInvoiceData(company_id) {
  const res = await fetch(`/api/company-invoices-current-month?company_id=${encodeURIComponent(company_id)}`);
  if (!res.ok) throw new Error('Failed to fetch invoice data');
  return await res.json();
}


// These now take invoiceData as input (from getLastMonthInvoiceData)
// Focus on carbon emissions for dashboard
export function getLatestEmissionsTimeSeries(invoiceData) {
  // Use invoiceData.time_series (object: {YYYY-MM-DD: emissions})
  if (!invoiceData || !invoiceData.time_series) return [];
  // Convert to array sorted by date
  return Object.entries(invoiceData.time_series)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, value]) => ({ date, kgco2: value }));
}

export function getAggregatedKPIs(invoiceData) {
  if (!invoiceData) return [];
  // If backend provides total_emissions, use it. Otherwise, fallback to spend.
  return [
    { label: 'Invoices', value: invoiceData.raw ? invoiceData.raw.length : 0, delta: '' },
    { label: 'Spend', value: invoiceData.total_spend ? `${invoiceData.total_spend} €` : '-', delta: '' },
  ];
}


// Default emission factors (kg CO2e per unit). These are defaults and should be adjusted per region/company.
const DEFAULT_EMISSION_FACTORS = {
  
}

function normalizeUnit(u) {
  if (!u) return ''
  return String(u).toLowerCase().trim().replace(/\s+/g, '').replace(/\./g, '')
}

export async function computeItemLevelEmissions(invoiceData) {
  if (!invoiceData || !Array.isArray(invoiceData.raw)) return []
  const rows = invoiceData.raw
  // Try to fetch cached official factors from backend
  let cached = {}
  try {
    const res = await fetch('/api/emission-factors')
    if (res.ok) {
      const j = await res.json()
      if (j && j.factors) cached = j.factors
    }
  } catch (e) {
    // ignore and fall back to defaults
  }
  return rows.map((r) => {
    const quantity = (typeof r.quantity === 'number') ? r.quantity : Number(r.quantity) || null
    const unitRaw = r.unit || ''
    const unit = normalizeUnit(unitRaw)
    const type = r.type || ''

    // prefer cached official factor, then defaults
    let factor = null
    if (unit && cached[unit]) {
      factor = Number(cached[unit])
    } else if (unit && DEFAULT_EMISSION_FACTORS[unit]) {
      factor = DEFAULT_EMISSION_FACTORS[unit]
    }

    let emissions = null
    let formula = ''

    // If unit indicates tonnes, convert quantity to kg for calculation
    let qtyForCalc = quantity
    if (unit && (unit === 'tonne' || unit === 't')) {
      qtyForCalc = quantity !== null ? quantity * 1000 : null
    }

    if (factor !== null && qtyForCalc !== null) {
      emissions = qtyForCalc * factor
      formula = `${qtyForCalc} × ${factor} kg CO₂e/${unitRaw} = ${emissions.toFixed(4)} kg CO₂e`
    } else if (unit && (unit === 'tco2e' || unit === 'tco2')) {
      // quantity reported in tonnes of CO2 — convert to kg
      emissions = quantity * 1000
      formula = `Quantity reported as tonnes CO₂e: ${quantity} tCO₂e → ${emissions} kg CO₂e`
    } else if (quantity !== null && !unit) {
      // No unit - heuristic: treat quantity as kg CO2e when unit missing
      emissions = quantity
      formula = `No unit provided — treating ${quantity} as kg CO₂e (fallback)`
    } else {
      formula = `No emission factor found for unit '${unitRaw}'. Please map to a factor.`
    }

    return {
      name: r.name || '(unnamed)',
      quantity,
      unit: unitRaw || '',
      type,
      factor: factor,
      emissions: emissions !== null ? Number(emissions.toFixed(4)) : null,
      formula,
    }
  })
}

