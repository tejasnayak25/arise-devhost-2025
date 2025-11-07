import React, { useState } from 'react';
import { createCompany, joinCompany } from '../services/companyActions';

export default function CompanyRequired({ user, onSuccess }) {
  const [mode, setMode] = useState(null); // 'join' | 'create' | null
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCreate = async () => {
    setLoading(true); setError('');
    try {
      await createCompany(input, user.email);
      onSuccess && onSuccess();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    setLoading(true); setError('');
    try {
      await joinCompany(input, user.email);
      onSuccess && onSuccess();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (mode === 'create') {
    return (
      <div className="panel warning" style={{ margin: '2rem auto', maxWidth: 480, textAlign: 'center' }}>
        <h2>Create an Organization</h2>
        <input
          className="input"
          placeholder="Organization Name"
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
          style={{ width: '100%', marginBottom: 12 }}
        />
        <button className="btn primary" onClick={handleCreate} disabled={loading || !input}>Create</button>
        <button className="btn" onClick={() => setMode(null)} disabled={loading} style={{ marginLeft: 8 }}>Back</button>
        {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
      </div>
    );
  }

  if (mode === 'join') {
    return (
      <div className="panel warning" style={{ margin: '2rem auto', maxWidth: 480, textAlign: 'center' }}>
        <h2>Join a Organization</h2>
        <input
          className="input"
          placeholder="Organization Code or Name"
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
          style={{ width: '100%', marginBottom: 12 }}
        />
        <button className="btn primary" onClick={handleJoin} disabled={loading || !input}>Join</button>
        <button className="btn" onClick={() => setMode(null)} disabled={loading} style={{ marginLeft: 8 }}>Back</button>
        {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
      </div>
    );
  }

  // Default prompt
  return (
    <div className="panel warning" style={{ margin: '2rem auto', maxWidth: 480, textAlign: 'center' }}>
      <h2>Join or Create an Organization</h2>
      <p className="muted">You must be part of an organization to use dashboard features like adding invoices. Please join an existing company or create a new one.</p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 24 }}>
        <button className="btn primary" onClick={() => setMode('join')}>Join Organization</button>
        <button className="btn" onClick={() => setMode('create')}>Create Organization</button>
      </div>
    </div>
  );
}
