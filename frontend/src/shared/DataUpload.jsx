import React, { useState } from 'react'

export default function DataUpload({ onComplete }) {
  const [files, setFiles] = useState([])

  function onFiles(e) {
    const next = Array.from(e.target.files || [])
    setFiles((prev) => [...prev, ...next])
  }

  function handleProcess() {
    if (files.length > 0 && onComplete) {
      const fileNames = files.map(f => f.name).join(', ')
      onComplete(fileNames || 'Uploaded files')
    }
  }

  return (
    <div>
      <div style={{ display: 'grid', gap: 10, gridTemplateColumns: '1fr auto' }}>
        <input type="file" multiple onChange={onFiles} />
        <button className="btn" onClick={handleProcess} disabled={files.length === 0}>
          Process
        </button>
      </div>
      {!!files.length && (
        <div style={{ marginTop: 10 }} className="muted">
          {files.length} file(s) ready. Supported: CSV, XLSX, PDF (OCR later)
        </div>
      )}
    </div>
  )
}

