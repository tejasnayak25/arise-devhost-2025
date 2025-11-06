import React, { useState, useEffect } from 'react'

export default function DatabaseLink({ value, onChange, onConnect, onDisconnect, onTest }) {
  const [local, setLocal] = useState(value)
  useEffect(() => { setLocal(value) }, [value])

  function update(field, v) {
    const next = { ...local, [field]: v }
    setLocal(next)
    onChange(next)
  }

  return (
    <div className="panel">
      <h3>Database Connection</h3>
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div>
          <label>Host</label>
          <input placeholder="db.example.com" value={local.host} onChange={(e) => update('host', e.target.value)} />
        </div>
        <div>
          <label>Port</label>
          <input placeholder="5432" value={local.port} onChange={(e) => update('port', e.target.value)} />
        </div>
        <div>
          <label>Database</label>
          <input placeholder="esg" value={local.database} onChange={(e) => update('database', e.target.value)} />
        </div>
        <div>
          <label>User</label>
          <input placeholder="esg_user" value={local.user} onChange={(e) => update('user', e.target.value)} />
        </div>
        <div>
          <label>Password</label>
          <input type="password" placeholder="••••••••" value={local.password} onChange={(e) => update('password', e.target.value)} />
        </div>
        <div>
          <label>Type</label>
          <select value={local.type} onChange={(e) => update('type', e.target.value)}>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL</option>
            <option value="mssql">MS SQL Server</option>
          </select>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        {local.connected ? (
          <button className="btn danger" onClick={onDisconnect}>Disconnect</button>
        ) : (
          <button className="btn" onClick={onConnect}>Connect</button>
        )}
        <button className="btn secondary" onClick={onTest}>Test connection</button>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Status: {local.connected ? 'Connected' : 'Not connected'}{local.lastTest ? ` • Last test: ${local.lastTest}` : ''}
      </div>
    </div>
  )
}

