import React, { useState } from 'react'
import DataUpload from '../shared/DataUpload'
import DatabaseLink from '../shared/DatabaseLink'
import ConfirmModal from '../shared/ConfirmModal'
import { getDbConnection, updateDbConnection, connectDb, disconnectDb, testDbConnection } from '../services/dataService'

export default function DataSources() {
  const [showAddSource, setShowAddSource] = useState(false)
  const [selectedSourceType, setSelectedSourceType] = useState(null) // 'file' | 'database' | null
  const [dbConn, setDbConn] = useState(getDbConnection())
  
  // Dummy sources - in real app, these would come from a service/API
  const [connectedSources, setConnectedSources] = useState([
    { id: 'file-1', type: 'file', name: 'Invoices CSV (September 2024)', status: 'Ready', addedAt: '2024-09-15' },
    { id: 'db-1', type: 'database', name: 'PostgreSQL - ESG Production', status: 'Connected', addedAt: '2024-09-10' },
  ])

  function handleAddSource(type) {
    setSelectedSourceType(type)
    setShowAddSource(false)
  }

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmTarget, setConfirmTarget] = useState(null)

  function requestRemoveSource(id, name) {
    setConfirmTarget({ id, name })
    setConfirmOpen(true)
  }

  function confirmRemoval() {
    if (!confirmTarget) return
    const { id } = confirmTarget
    setConnectedSources(prev => prev.filter(s => s.id !== id))
    if (selectedSourceType && connectedSources.find(s => s.id === id)?.type === selectedSourceType) {
      setSelectedSourceType(null)
    }
    setConfirmOpen(false)
    setConfirmTarget(null)
  }

  function cancelRemoval() {
    setConfirmOpen(false)
    setConfirmTarget(null)
  }

  function handleFileUploadComplete(fileName) {
    // When file upload is complete, add it to connected sources
    const newId = `file-${Date.now()}`
    const newSource = {
      id: newId,
      type: 'file',
      name: fileName || 'New File Upload',
      status: 'Ready',
      addedAt: new Date().toISOString().split('T')[0]
    }
    setConnectedSources(prev => [newSource, ...prev])
    setSelectedSourceType(null)
  }

  function handleDatabaseConnect() {
    connectDb()
    setDbConn(getDbConnection())
    // Add to connected sources
    const newId = `db-${Date.now()}`
    const newSource = {
      id: newId,
      type: 'database',
      name: `${dbConn.type} - ${dbConn.database || 'New Connection'}`,
      status: 'Connected',
      addedAt: new Date().toISOString().split('T')[0]
    }
    setConnectedSources(prev => [newSource, ...prev])
    setSelectedSourceType(null)
  }

  return (
    <div className="stack">
      <h1 style={{ margin: '0 0 20px', fontSize: 28, fontWeight: 700 }}>Data Sources</h1>

      <div className="panel">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: showAddSource || selectedSourceType ? 16 : 0 }}>
          <h3 style={{ margin: 0 }}>Add sources</h3>
          {!selectedSourceType && (
            <button className="btn" onClick={() => setShowAddSource(!showAddSource)}>
              {showAddSource ? 'Cancel' : 'Add source'}
            </button>
          )}
        </div>

        {showAddSource && !selectedSourceType && (
          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: '1fr 1fr', marginTop: 12 }}>
            <div className="panel" style={{ padding: 16, cursor: 'pointer', border: '2px solid rgba(96,165,250,.2)' }} onClick={() => handleAddSource('file')}>
              <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 16 }}>File Upload</div>
              <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
                Upload invoices, meter readings, and Scope 3 data files (CSV, XLSX, PDF)
              </div>
              <button className="btn" style={{ width: '100%' }}>Select File Upload</button>
            </div>
            <div className="panel" style={{ padding: 16, cursor: 'pointer', border: '2px solid rgba(96,165,250,.2)' }} onClick={() => handleAddSource('database')}>
              <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 16 }}>Database Connection</div>
              <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
                Connect to your database to import ESG data automatically
              </div>
              <button className="btn" style={{ width: '100%' }}>Select Connection</button>
            </div>
          </div>
        )}

        {selectedSourceType === 'file' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h4 style={{ margin: 0 }}>File Upload</h4>
              <button className="btn secondary" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => setSelectedSourceType(null)}>
                Cancel
              </button>
            </div>
            <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
              Upload invoices, meter readings, and Scope 3 data files
            </p>
            <DataUpload onComplete={handleFileUploadComplete} />
          </div>
        )}

        {selectedSourceType === 'database' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h4 style={{ margin: 0 }}>Database Connection</h4>
              <button className="btn secondary" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => setSelectedSourceType(null)}>
                Cancel
              </button>
            </div>
            <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
              Connect to your database to import ESG data
            </p>
            <DatabaseLink
              value={dbConn}
              onChange={(next) => setDbConn(updateDbConnection(next))}
              onConnect={handleDatabaseConnect}
              onDisconnect={() => { disconnectDb(); setDbConn(getDbConnection()) }}
              onTest={() => { testDbConnection(); setDbConn(getDbConnection()) }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Connected</h3>
        {connectedSources.length === 0 ? (
          <div className="muted" style={{ padding: '20px 0' }}>No connected sources yet. Click "Add source" to get started.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Name</th>
                <th>Status</th>
                <th>Added</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {connectedSources.map((source) => (
                <tr key={source.id}>
                  <td>{source.type === 'file' ? 'File Upload' : 'Connection'}</td>
                  <td>{source.name}</td>
                  <td>
                    <span style={{ 
                      color: source.status === 'Connected' || source.status === 'Ready' ? 'var(--brand)' : 'var(--muted)',
                      fontSize: 12
                    }}>
                      {source.status}
                    </span>
                  </td>
                  <td className="muted" style={{ fontSize: 12 }}>{source.addedAt}</td>
                  <td>
                    <button 
                      className="btn danger" 
                      style={{ padding: '6px 12px', fontSize: 12 }} 
                      onClick={() => requestRemoveSource(source.id, source.name)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <ConfirmModal
        open={confirmOpen}
        title="Remove source?"
        description={confirmTarget ? `Are you sure you want to remove "${confirmTarget.name}"? This cannot be undone.` : ''}
        confirmText="Remove"
        cancelText="Cancel"
        onConfirm={confirmRemoval}
        onCancel={cancelRemoval}
      />
    </div>
  )
}

