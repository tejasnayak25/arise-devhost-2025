// Mock data and connectors to simulate ingestion and KPIs

let connectors = [
  { key: 'erp', name: 'ERP (Invoices)', description: 'Fetch invoices for Scope 1/2/3 extraction', connected: false },
  { key: 'utility', name: 'Utility API', description: 'Electricity/gas consumption from grid provider', connected: true },
  { key: 'bms', name: 'Building Meters', description: 'On-site energy meters via gateway', connected: false },
]

let dbConnection = {
  type: 'postgres',
  host: '',
  port: '5432',
  database: '',
  user: '',
  password: '',
  connected: false,
  lastTest: ''
}

export function listConnectors() {
  return connectors
}

export function connectSource(key) {
  connectors = connectors.map(c => c.key === key ? { ...c, connected: true } : c)
}

export function disconnectSource(key) {
  connectors = connectors.map(c => c.key === key ? { ...c, connected: false } : c)
}

export function getDbConnection() {
  return dbConnection
}

export function updateDbConnection(next) {
  dbConnection = { ...dbConnection, ...next }
  return dbConnection
}

export function connectDb() {
  // naive validation
  const valid = dbConnection.host && dbConnection.database && dbConnection.user
  dbConnection = { ...dbConnection, connected: !!valid }
  return dbConnection.connected
}

export function disconnectDb() {
  dbConnection = { ...dbConnection, connected: false }
}

export function testDbConnection() {
  const ok = !!(dbConnection.host && dbConnection.port && dbConnection.user)
  const timestamp = new Date().toLocaleString()
  dbConnection = { ...dbConnection, lastTest: `${ok ? 'OK' : 'Failed'} @ ${timestamp}` }
  return ok
}

export function getLatestEmissionsTimeSeries() {
  // Synthetic monthly tCO2e trend
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const base = 120
  return months.map((m, i) => ({ month: m, tco2e: Math.round((base + Math.sin(i/2)*12 - i*1.4) * 10)/10 }))
}

export function getAggregatedKPIs() {
  return [
    { label: 'YTD Emissions', value: '1,042 tCO₂e', delta: '▼ 6.2% vs LY' },
    { label: 'Renewables Share', value: '38%', delta: '▲ +8 pts vs LY' },
    { label: 'Data Completeness', value: '72%', delta: '▲ +12 pts MoM' },
  ]
}

