import React from 'react'

export default function SourceConnector({ connector, onConnect, onDisconnect }) {
  return (
    <div className="panel">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontWeight: 700 }}>{connector.name}</div>
          <div className="muted" style={{ fontSize: 13 }}>{connector.description}</div>
        </div>
        {connector.connected ? (
          <button className="btn danger" onClick={onDisconnect}>Disconnect</button>
        ) : (
          <button className="btn" onClick={onConnect}>Connect</button>
        )}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Status: {connector.connected ? 'Connected' : 'Not connected'}
      </div>
    </div>
  )
}

