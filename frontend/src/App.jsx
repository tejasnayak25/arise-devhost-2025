import React from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import DataSources from './pages/DataSources'
import Reports from './pages/Reports'
import Compliance from './pages/Compliance'

export default function App() {
  return (
    <div className="app-root">
      <aside className="app-sidebar">
        <div className="brand" style={{ marginBottom: 16 }}>ESG Automation</div>
        <nav className="nav vertical">
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/sources">Data Sources</NavLink>
          <NavLink to="/reports">Reports</NavLink>
          <NavLink to="/compliance">Compliance</NavLink>
        </nav>
        <div className="muted" style={{ marginTop: 'auto', fontSize: 12 }}>v0.1.0</div>
      </aside>
      <div className="app-content">
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sources" element={<DataSources />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/compliance" element={<Compliance />} />
          </Routes>
        </main>
        <footer className="app-footer">© {new Date().getFullYear()} ESG Automation</footer>
      </div>
    </div>
  )
}

