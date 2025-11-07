import React, { useState, useEffect } from 'react'
import DataUpload from '../shared/DataUpload'
import DatabaseLink from '../shared/DatabaseLink'
import ConfirmModal from '../shared/ConfirmModal'
import { useAuth } from '../contexts/AuthContext'
import { getFilesFromStorage, getSensors } from '../services/apiService'
import { getUserCompany } from '../services/companyService'
import SensorLink from '../shared/SensorLink'

export default function DataSources() {
  const [showAddSource, setShowAddSource] = useState(false)
  const [selectedSourceType, setSelectedSourceType] = useState(null) // 'file' | 'database' | null

  const { user } = useAuth()
  const [company, setCompany] = useState(undefined); // undefined = loading, null = not in company
  const [connectedSources, setConnectedSources] = useState([])
  const [dbConn, setDbConn] = useState(null)
  const [sensorConn, setSensorConn] = useState(null)

  useEffect(() => {
    async function fetchCompanyAndFiles() {
      if (user?.email) {
        try {
          const companyInfo = await getUserCompany(user.email);
          setCompany(companyInfo);
          const files = await getFilesFromStorage(companyInfo.id);
          let fileSources = files.map((file) => ({
            id: `file-${file.id}`,
            type: 'file',
            name: file.name,
            status: 'Ready',
            addedAt: new Date(file.created_at).toISOString().split('T')[0],
            size: file.size,
            data: file
          }));
          fileSources = fileSources.filter(i => i.size !== 0);
          // also fetch any persisted sensors
          let sensorSources = []
          try {
            const sensors = await getSensors(companyInfo.id);
            if (Array.isArray(sensors)) {
              sensorSources = sensors.map(s => ({
                id: `sensor-${s.id || s.device_id}`,
                type: 'sensor',
                name: s.device_id || `Sensor ${s.id}`,
                status: 'Connected',
                addedAt: s.created_at ? s.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
                data: s
              }))
            }
          } catch (e) {
            // ignore sensors fetch errors
            console.error('Error fetching sensors:', e)
          }

          setConnectedSources((prev) => [...sensorSources, ...fileSources])
        } catch (error) {
          setCompany(null);
          console.error('Error fetching company or files:', error)
        }
      }
    }
    fetchCompanyAndFiles();
  }, [user])

  function handleAddSource(type) {
    setSelectedSourceType(type)
    setShowAddSource(false)
  }

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmTarget, setConfirmTarget] = useState(null)

  function requestRemoveSource(id, data, name, type) {
    setConfirmTarget({ id, data, name, type })
    setConfirmOpen(true)
  }

  function confirmRemoval() {
    if (!confirmTarget) return
    const { id, data, name, type } = confirmTarget
    if(type === 'file') {
      fetch(`/api/files/remove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: company?.id, invoice_path: `${company?.id}/${data.name}` })
      })
      .then(r => {
        if (!r.ok) {
          throw new Error('Failed to remove sensor')
        }
      })
      .catch(err => {
        console.error('Error removing sensor:', err)
        alert('Failed to remove sensor. Please try again.')
      });
    } else if(type === "sensor") {
      fetch(`/api/sensors/remove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: data.device_id, company_id: company?.id})
      })
      .then(r => {
        if (!r.ok) {
          throw new Error('Failed to remove sensor')
        }
      })
      .catch(err => {
        console.error('Error removing sensor:', err)
        alert('Failed to remove sensor. Please try again.')
      });
    }
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

  function handleFileUploadComplete(fileName, results) {
    // When file upload is complete, add uploaded files to connected sources
    if (results && results.length > 0) {
      results.forEach((result, index) => {
        if (result.success) {
          const newId = `file-${Date.now()}-${index}`
          const data = result.data;
          const status = data.type === 'csv' 
            ? `Ready (${data.row_count} rows)`
            : data.type === 'ocr'
            ? 'Ready (OCR processed)'
            : 'Ready'
          
          const newSource = {
            id: newId,
            type: 'file',
            name: result.file.name,
            status: status,
            addedAt: new Date().toISOString().split('T')[0],
            data: data // Store processed data for later use
          }
          setConnectedSources(prev => [newSource, ...prev])
        }
      })
    } else {
      // Fallback for backward compatibility
      const newId = `file-${Date.now()}`
      const newSource = {
        id: newId,
        type: 'file',
        name: fileName || 'New File Upload',
        status: 'Ready',
        addedAt: new Date().toISOString().split('T')[0]
      }
      setConnectedSources(prev => [newSource, ...prev])
    }
    setSelectedSourceType(null)
  }

  function handleDatabaseConnect() {
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

  function handleSensorConnect(payload) {
    const newId = `sensor-${Date.now()}`
    const newSource = {
      id: newId,
      type: 'sensor',
      name: payload.device_id || `Sensor ${newId}`,
      status: 'Connected',
      addedAt: new Date().toISOString().split('T')[0],
      data: payload
    }
    setConnectedSources(prev => [newSource, ...prev])
    setSensorConn(payload)
    setSelectedSourceType(null)
  }

  return (
    <div className="stack">
      <h1 style={{ margin: '0 0 20px', fontSize: 28, fontWeight: 700, color: "black" }}>Data Sources</h1>

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
          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: '1fr 1fr 1fr', marginTop: 12 }}>
            <button
              type="button"
              className="panel panel-option"
              onClick={() => handleAddSource('file')}
              aria-label="Add file upload source"
            >
              <div className="panel-option-title">File Upload</div>
              <div className="muted panel-option-desc">Upload invoices, meter readings, and Scope 3 data files (CSV, XLSX, PDF)</div>
              <span className="btn panel-cta">Select File Upload</span>
            </button>

            <button
              type="button"
              className="panel panel-option"
              onClick={() => handleAddSource('database')}
              aria-label="Add database connection"
            >
              <div className="panel-option-title">Database Connection</div>
              <div className="muted panel-option-desc">Connect to your database to import ESG data automatically</div>
              <span className="btn panel-cta">Select Connection</span>
            </button>

            <button
              type="button"
              className="panel panel-option"
              onClick={() => handleAddSource('sensor')}
              aria-label="Add database connection"
            >
              <div className="panel-option-title">Sensor Input</div>
              <div className="muted panel-option-desc">Connect your hardware devices to read ESG data automatically</div>
              <span className="btn panel-cta">Select Sensor</span>
            </button>
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
            <DataUpload email={user.email} company_id={company?.id} onComplete={handleFileUploadComplete} />
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
              onChange={(next) => setDbConn(next)}
              onConnect={handleDatabaseConnect}
              onDisconnect={() => { setDbConn(null) }} // Adjusted to remove DB connection
              onTest={() => { /* No longer testing DB connection */ }}
            />
          </div>
        )}

        {selectedSourceType === 'sensor' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h4 style={{ margin: 0 }}>Connect Sensor</h4>
              <button className="btn secondary" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => setSelectedSourceType(null)}>
                Cancel
              </button>
            </div>
            <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
              Connect your sensor to read ESG data
            </p>
            <SensorLink value={sensorConn} company_id={company?.id} onConnect={handleSensorConnect} onDisconnect={() => { setSensorConn(null) }} />
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
                  <td>{source.type === 'file' ? 'File Upload' : source.type === 'database' ? 'Connection' : source.type === 'sensor' ? 'Sensor' : 'Source'}</td>
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
                      onClick={() => requestRemoveSource(source.id, source.data, source.name, source.type)}
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

