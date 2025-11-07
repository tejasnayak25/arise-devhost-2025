import React, { useState, useRef } from 'react'
import { uploadFiles } from '../services/apiService'

export default function DataUpload({ email, company_id, onComplete }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState({}) // { fileIndex: { status, message } }
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  function onFiles(e) {
    const next = Array.from(e.target.files || [])
    setFiles((prev) => [...prev, ...next])
    setError(null)
    setUploadStatus({})
    // Clear the native file input so selecting the same file again will fire onChange
    try {
      e.target.value = ''
    } catch (err) {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleProcess() {
    if (files.length === 0) return

    setUploading(true)
    setError(null)
    setUploadStatus({})

    try {
      const results = await uploadFiles(files, company_id, (fileIndex, result) => {
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
        // Reset native input so user can re-upload the same files if desired
        if (fileInputRef.current) fileInputRef.current.value = ''
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
    // Remove the file and remap uploadStatus keys so statuses stay aligned with file indices
    setFiles(prevFiles => {
      const newFiles = prevFiles.filter((_, i) => i !== index)
      setUploadStatus(prevStatus => {
        const next = {}
        newFiles.forEach((_, i) => {
          // old index maps to new index; if removed index <= i then oldIndex = i+1 else oldIndex = i
          const oldIndex = i >= index ? i + 1 : i
          if (prevStatus && prevStatus[oldIndex]) next[i] = prevStatus[oldIndex]
        })
        return next
      })
      // Clear native input to allow re-selecting same file
      if (fileInputRef.current) fileInputRef.current.value = ''
      return newFiles
    })
  }

  return (
    <div style={{ width: '100%', paddingRight: "15px" }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* cloud upload icon */}
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7 18h10a4 4 0 0 0 .8-7.96A5 5 0 0 0 7 6.1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M12 11v6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M9 14l3-3 3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <div style={{ fontWeight: 600 }}>Upload files</div>
            <div className="muted" style={{ fontSize: 13 }}>CSV, PDF, Images (OCR). Max 10MB per file.</div>
          </div>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={onFiles}
            disabled={uploading}
            accept=".csv,.xlsx,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.tiff"
            style={{ position: 'absolute', left: -9999, width: 1, height: 1, overflow: 'hidden' }}
            aria-hidden="true"
          />
          <button
            type="button"
            className="btn"
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
            disabled={uploading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <span style={{ fontSize: 14 }}>Select files</span>
          </button>
          <button
            className="btn primary"
            onClick={handleProcess}
            disabled={files.length === 0 || uploading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            {uploading ? (
              <>
                <svg width="16" height="16" viewBox="0 0 38 38" xmlns="http://www.w3.org/2000/svg" stroke="#fff">
                  <g fill="none" fillRule="evenodd">
                    <g transform="translate(1 1)" strokeWidth="2">
                      <circle strokeOpacity="0.5" cx="18" cy="18" r="18" />
                      <path d="M36 18c0-9.94-8.06-18-18-18">
                        <animateTransform
                          attributeName="transform"
                          type="rotate"
                          from="0 18 18"
                          to="360 18 18"
                          dur="0.9s"
                          repeatCount="indefinite" />
                      </path>
                    </g>
                  </g>
                </svg>
                <span>Uploading</span>
              </>
            ) : (
              'Process'
            )}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ marginTop: 10, padding: '10px 12px', backgroundColor: 'rgba(255,200,200,0.08)', color: '#c33', borderRadius: 8 }}>
          {error}
        </div>
      )}

      {uploading && (
        <div style={{ height: 6, background: 'linear-gradient(90deg,#ccc,#eee)', borderRadius: 6, overflow: 'hidden', marginBottom: 10 }}>
          <div style={{ width: '40%', height: '100%', background: 'linear-gradient(90deg,#4caf50,#81c784)', animation: 'indeterminate 1.2s linear infinite' }} />
        </div>
      )}

      {files.length > 0 && (
        <div style={{ marginTop: 6, display: 'grid', gap: 8 }}>
          {files.map((file, index) => {
            const status = uploadStatus[index]
            return (
              <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 10, borderRadius: 8, background: 'var(--bg-900)', boxShadow: 'inset 0 -1px 0 rgba(255,255,255,0.02)' }}>
                <div style={{ flex: '0 0 auto' }}>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M8 13h8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M8 17h8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{(file.size / 1024).toFixed(1)} KB</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {status ? (
                    <div style={{ fontSize: 12, padding: '4px 8px', borderRadius: 999, background: status.status === 'success' ? 'rgba(72,187,120,0.12)' : 'rgba(222,85,85,0.08)', color: status.status === 'success' ? '#48bb78' : '#de5555' }}>
                      {status.status === 'success' ? '✓' : '✗'} {status.message}
                    </div>
                  ) : (
                    <div className="muted" style={{ fontSize: 12 }}>Ready</div>
                  )}
                  {!uploading && (
                    <button onClick={() => removeFile(index)} className="btn" style={{ padding: '6px 8px', backgroundColor: "white" }}>Remove</button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <style>{`@keyframes indeterminate { 0% { transform: translateX(-20%);} 100% { transform: translateX(120%);} }`}</style>
    </div>
  )
}

