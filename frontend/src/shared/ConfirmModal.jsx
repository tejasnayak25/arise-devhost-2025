import React, { useEffect, useRef } from 'react'

export default function ConfirmModal({ open, title, description, confirmText = 'Confirm', cancelText = 'Cancel', onConfirm = () => {}, onCancel = () => {} }) {
  const confirmRef = useRef(null)

  useEffect(() => {
    if (open && confirmRef.current) {
      try { confirmRef.current.focus() } catch (e) {}
    }
  }, [open])

  if (!open) return null

  const overlayStyle = {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0,0,0,0.75)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2000,
    padding: 16,
    backdropFilter: 'blur(2px)'
  }

  const modalStyle = {
    background: '#0f1724',
    borderRadius: 8,
    maxWidth: 520,
    width: '100%',
    boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
    padding: 20,
    boxSizing: 'border-box',
    border: '1px solid var(--border-color)'
  }

  const titleStyle = { margin: 0, marginBottom: 8, fontSize: 18 }
  const descStyle = { marginTop: 6, marginBottom: 0, color: '#a3a3a3ff', lineHeight: 1.4 }
  const actionsStyle = { display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }
  const btnStyle = { padding: '8px 14px', borderRadius: 6, border: '1px solid #9c9c9c71', cursor: 'pointer', background: '#fff' }
  const cancelBtnStyle = { ...btnStyle, background: '#0b1220' }
  const confirmBtnStyle = { ...btnStyle, background: '#d9534f', color: '#fff', border: '1px solid #d43f3a' }

  return (
    <div style={overlayStyle} role="dialog" aria-modal="true" aria-label={title || 'Confirmation dialog'}>
      <div style={modalStyle} className="modal">
        <h3 style={titleStyle}>{title}</h3>
        {description ? (
          <p className="muted" style={descStyle}>{description}</p>
        ) : null}

        <div style={actionsStyle}>
          <button
            type="button"
            className="btn secondary"
            onClick={onCancel}
            style={cancelBtnStyle}
          >
            {cancelText}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className="btn danger"
            onClick={onConfirm}
            style={confirmBtnStyle}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}


