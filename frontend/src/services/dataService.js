
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
    .map(([date, value]) => ({ date, tco2e: value }));
}

export function getAggregatedKPIs(invoiceData) {
  if (!invoiceData) return [];
  // If backend provides total_emissions, use it. Otherwise, fallback to spend.
  return [
    { label: 'Last Month Emissions', value: invoiceData.total_emissions ? `${invoiceData.total_emissions} tCO₂e` : '-', delta: '' },
    { label: 'Invoices', value: invoiceData.raw ? invoiceData.raw.length : 0, delta: '' },
    { label: 'Spend', value: invoiceData.total_spend ? `${invoiceData.total_spend} $` : '-', delta: '' },
  ];
}

