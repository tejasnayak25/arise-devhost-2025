import React, { useState, useEffect } from 'react'

export default function DatabaseLink({ value, onChange, onConnect, onDisconnect, onTest }) {
  const [local, setLocal] = useState(value || {})
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { setLocal(value || {}) }, [value])

  function update(field, v) {
    const next = { ...local, [field]: v }
    setLocal(next)
    if (onChange) onChange(next)
  }

  function _validateConfig(cfg) {
    // simple required fields: host, port, database, user
    if (!cfg.host) return 'Host is required'
    if (!cfg.port) return 'Port is required'
    if (!cfg.database) return 'Database name is required'
    if (!cfg.user) return 'User is required'
    return null
  }

  async function handleConnect() {
    setError(null)
    const validation = _validateConfig(local)
    if (validation) {
      setError(validation)
      return
    }
    if (!onConnect) return
    try {
      setLoading(true)
      const res = onConnect(local)
      // support promise-returning handlers
      const result = res && res.then ? await res : res
      // allow handler to return updated status
      if (result && result.error) setError(result.error)
    } catch (e) {
      setError(e?.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleDisconnect() {
    setError(null)
    if (!onDisconnect) return
    try {
      setLoading(true)
      const res = onDisconnect(local)
      if (res && res.then) await res
    } catch (e) {
      setError(e?.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleTest() {
    setError(null)
    if (!onTest) return
    const validation = _validateConfig(local)
    if (validation) {
      setError(validation)
      return
    }
    try {
      setTesting(true)
      const res = onTest(local)
      const result = res && res.then ? await res : res
      if (result && result.error) setError(result.error)
    } catch (e) {
      setError(e?.message || String(e))
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="panel">
      <h3>Database Connection</h3>
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div>
          <label>Host</label>
          <input placeholder="db.example.com" value={local.host || ''} onChange={(e) => update('host', e.target.value)} />
        </div>
        <div>
          <label>Port</label>
          <input placeholder="5432" value={local.port || ''} onChange={(e) => update('port', e.target.value)} />
        </div>
        <div>
          <label>Database</label>
          <input placeholder="esg" value={local.database || ''} onChange={(e) => update('database', e.target.value)} />
        </div>
        <div>
          <label>User</label>
          <input placeholder="esg_user" value={local.user || ''} onChange={(e) => update('user', e.target.value)} />
        </div>
        <div>
          <label>Password</label>
          <input type="password" placeholder="••••••••" value={local.password || ''} onChange={(e) => update('password', e.target.value)} />
        </div>
        <div>
          <label>Type</label>
          <select value={local.type || 'postgres'} onChange={(e) => update('type', e.target.value)}>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL</option>
            <option value="mssql">MS SQL Server</option>
          </select>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        {local.connected ? (
          <button className="btn danger" onClick={handleDisconnect} disabled={loading}>{loading ? 'Disconnecting...' : 'Disconnect'}</button>
        ) : (
          <button className="btn" onClick={handleConnect} disabled={loading}>{loading ? 'Connecting...' : 'Connect'}</button>
        )}
        <button className="btn secondary" onClick={handleTest} disabled={testing}>{testing ? 'Testing...' : 'Test connection'}</button>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Status: {local.connected ? 'Connected' : 'Not connected'}{local.lastTest ? ` • Last test: ${local.lastTest}` : ''}
      </div>
      {error && (
        <div style={{ marginTop: 8, color: '#de5555', fontSize: 13 }}>{error}</div>
      )}
    </div>
  )
}

