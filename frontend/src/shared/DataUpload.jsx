import React, { useState } from 'react'
import { uploadFiles } from '../services/apiService'

export default function DataUpload({ email, onComplete }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState({}) // { fileIndex: { status, message } }
  const [error, setError] = useState(null)

  function onFiles(e) {
    const next = Array.from(e.target.files || [])
    setFiles((prev) => [...prev, ...next])
    setError(null)
    setUploadStatus({})
  }

  async function handleProcess() {
    if (files.length === 0) return

    setUploading(true)
    setError(null)
    setUploadStatus({})

    try {
      const results = await uploadFiles(files, email, (fileIndex, result) => {
        setUploadStatus(prev => ({
          ...prev,
          [fileIndex]: {
            status: result.success ? 'success' : 'error',
            message: result.success 
              ? `Processed: ${result.data.type === 'csv' ? `${result.data.row_count} rows` : 'Text extracted'}`
              : result.error
          }
        }))
      })

      // Check if all uploads succeeded
      const allSuccess = results.every(r => r.success)
      const successCount = results.filter(r => r.success).length

      if (allSuccess) {
        const fileNames = files.map(f => f.name).join(', ')
        if (onComplete) {
          onComplete(fileNames, results)
        }
        // Clear files after successful upload
        setFiles([])
        setUploadStatus({})
      } else {
        setError(`${successCount}/${files.length} files processed successfully. Some files failed.`)
      }
    } catch (err) {
      setError(err.message || 'Failed to upload files. Please try again.')
      console.error('Upload error:', err)
    } finally {
      setUploading(false)
    }
  }

  function removeFile(index) {
    setFiles(prev => prev.filter((_, i) => i !== index))
    setUploadStatus(prev => {
      const next = { ...prev }
      delete next[index]
      return next
    })
  }

  return (
    <div>
      <div style={{ display: 'grid', gap: 10, gridTemplateColumns: '1fr auto' }}>
        <input 
          type="file" 
          multiple 
          onChange={onFiles}
          disabled={uploading}
          accept=".csv,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.tiff"
        />
        <button 
          className="btn" 
          onClick={handleProcess} 
          disabled={files.length === 0 || uploading}
        >
          {uploading ? 'Processing...' : 'Process'}
        </button>
      </div>

      {error && (
        <div style={{ 
          marginTop: 10, 
          padding: 10, 
          backgroundColor: '#fee', 
          color: '#c33',
          borderRadius: 4,
          fontSize: 13
        }}>
          {error}
        </div>
      )}

      {files.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="muted" style={{ marginBottom: 8, fontSize: 13 }}>
            {files.length} file(s) ready. Supported: CSV, PDF, Images (OCR)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {files.map((file, index) => (
              <div 
                key={index}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  backgroundColor: '#f5f5f5',
                  borderRadius: 4,
                  fontSize: 12
                }}
              >
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {file.name} ({(file.size / 1024).toFixed(1)} KB)
                </span>
                {uploadStatus[index] && (
                  <span style={{
                    marginLeft: 10,
                    color: uploadStatus[index].status === 'success' ? '#3c3' : '#c33',
                    fontSize: 11
                  }}>
                    {uploadStatus[index].status === 'success' ? '✓' : '✗'} {uploadStatus[index].message}
                  </span>
                )}
                {!uploading && (
                  <button
                    onClick={() => removeFile(index)}
                    style={{
                      marginLeft: 8,
                      padding: '2px 6px',
                      fontSize: 11,
                      border: 'none',
                      background: 'transparent',
                      color: '#999',
                      cursor: 'pointer'
                    }}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

