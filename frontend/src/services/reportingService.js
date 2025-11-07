// Mock report preview aligned to typical CSRD structure

export function generateESGReportPreview() {
  return [
  { section: 'E1 Climate Change', metric: 'Scope 1 (kg CO₂e)', value: '312000', notes: 'Stationary + mobile combustion (converted to kg)' },
  { section: 'E1 Climate Change', metric: 'Scope 2 (location-based, kg CO₂e)', value: '418000', notes: 'Grid electricity (converted to kg)' },
  { section: 'E1 Climate Change', metric: 'Scope 3 (selected categories, kg CO₂e)', value: '1842000', notes: 'Purchased goods, transport, waste (converted to kg)' },
    { section: 'E2 Energy', metric: 'Total energy consumption (MWh)', value: '9,420', notes: 'Electricity + heat' },
    { section: 'E2 Energy', metric: 'Renewable share (%)', value: '38%', notes: 'PPAs + GoOs' },
    { section: 'E5 Resource Use', metric: 'Waste diverted from disposal (%)', value: '61%', notes: 'Process improvements' },
    { section: 'G Governance', metric: 'Policy coverage', value: 'Yes', notes: 'Climate policy approved by Board' },
  ]
}

