import React from 'react'

export default function ConfirmModal({ open, title, description, confirmText = 'Confirm', cancelText = 'Cancel', onConfirm, onCancel }) {
  if (!open) return null
  return (
    <div className="modal-overlay">
      <div className="modal">
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        {description ? (
          <p className="muted" style={{ marginTop: 6 }}>{description}</p>
        ) : null}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <button className="btn secondary" onClick={onCancel}>{cancelText}</button>
          <button className="btn danger" onClick={onConfirm}>{confirmText}</button>
        </div>
      </div>
    </div>
  )
}


