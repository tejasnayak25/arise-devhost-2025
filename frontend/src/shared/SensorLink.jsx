import React, { useState } from 'react'
import { createSensor } from '../services/apiService'

export default function SensorLink({ value, company_id, onConnect }) {
  const [deviceId, setDeviceId] = useState(value?.device_id || '')
  const [powerKw, setPowerKw] = useState(value?.power_kW ?? 0.5) // default 0.5 kW
  const [emissionFactor, setEmissionFactor] = useState(value?.emission_factor ?? 0.233) // kgCO2e per kWh
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState(null)

  function handleConnect() {
    if (!deviceId) return
    setConnecting(true)
    setError(null)
    const payload = {
      device_id: deviceId,
      power_kW: Number(powerKw),
      emission_factor: Number(emissionFactor),
      company_id: company_id || null,
    }
    // call backend to persist sensor
    createSensor(payload).then((record) => {
      onConnect && onConnect(record)
    }).catch((err) => {
      console.error('Failed to create sensor:', err)
      setError(err.message || 'Failed to save sensor')
    }).finally(() => setConnecting(false))
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <label>Device ID</label>
      <input value={deviceId} onChange={(e) => setDeviceId(e.target.value)} placeholder="123" />

      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ flex: 1 }}>
          <label>Nominal power (kW)</label>
          <input type="number" step="0.01" value={powerKw} onChange={(e) => setPowerKw(e.target.value)} />
        </div>
        <div style={{ width: 160 }}>
          <label>Emission factor (kg/kWh)</label>
          <input type="number" step="0.001" value={emissionFactor} onChange={(e) => setEmissionFactor(e.target.value)} />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn" onClick={handleConnect} type="button" disabled={!deviceId || connecting}>{connecting ? 'Connecting...' : 'Connect Sensor'}</button>
      </div>

      {error && (
        <div className="panel" style={{ marginTop: 8 }}>
          <div className="muted">{error}</div>
        </div>
      )}
    </div>
  )
}
