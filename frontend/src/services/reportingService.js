// Mock report preview aligned to typical CSRD structure

export function generateESGReportPreview() {
  return [
    { section: 'E1 Climate Change', metric: 'Scope 1 (tCO₂e)', value: '312', notes: 'Stationary + mobile combustion' },
    { section: 'E1 Climate Change', metric: 'Scope 2 (location-based)', value: '418', notes: 'Grid electricity' },
    { section: 'E1 Climate Change', metric: 'Scope 3 (selected categories)', value: '1,842', notes: 'Purchased goods, transport, waste' },
    { section: 'E2 Energy', metric: 'Total energy consumption (MWh)', value: '9,420', notes: 'Electricity + heat' },
    { section: 'E2 Energy', metric: 'Renewable share (%)', value: '38%', notes: 'PPAs + GoOs' },
    { section: 'E5 Resource Use', metric: 'Waste diverted from disposal (%)', value: '61%', notes: 'Process improvements' },
    { section: 'G Governance', metric: 'Policy coverage', value: 'Yes', notes: 'Climate policy approved by Board' },
  ]
}

