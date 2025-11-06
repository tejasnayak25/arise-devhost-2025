import React, { useEffect } from 'react'
import { NavLink, Route, Routes, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Dashboard from './pages/Dashboard'
import DataSources from './pages/DataSources'
import Reports from './pages/Reports'
import Compliance from './pages/Compliance'
import Login from './pages/Login'
import Signup from './pages/Signup'
import { supabase } from './services/supabaseClient'

function AppContent() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Handle OAuth callback
  useEffect(() => {
    const handleAuthCallback = async () => {
      const code = searchParams.get('code')
      if (code) {
        // Exchange code for session
        const { error } = await supabase.auth.exchangeCodeForSession(code)
        if (error) {
          console.error('Error exchanging code for session:', error)
        } else {
          // Remove code from URL
          navigate('/', { replace: true })
        }
      }
    }

    handleAuthCallback()
  }, [searchParams, navigate])

  async function handleSignOut() {
    await signOut()
    navigate('/login')
  }

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
        <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid #ffffff0f' }}>
          {user && (
            <div style={{ marginBottom: 12, fontSize: 12, color: '#666' }}>
              <div style={{ marginBottom: 4 }}>{user.email}</div>
              <button
                onClick={handleSignOut}
                style={{
                  width: '100%',
                  padding: '6px 12px',
                  fontSize: 12,
                  border: '1px solid #ffffff0f',
                  borderRadius: 4,
                  backgroundColor: 'transparent',
                  cursor: 'pointer',
                  color: '#666'
                }}
              >
                Sign Out
              </button>
            </div>
          )}
          <div className="muted" style={{ fontSize: 12 }}>v0.1.0</div>
        </div>
      </aside>
      <div className="app-content">
        <main className="app-main">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/sources"
              element={
                <ProtectedRoute>
                  <DataSources />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <Reports />
                </ProtectedRoute>
              }
            />
            <Route
              path="/compliance"
              element={
                <ProtectedRoute>
                  <Compliance />
                </ProtectedRoute>
              }
            />
          </Routes>
        </main>
        <footer className="app-footer">© {new Date().getFullYear()} ESG Automation</footer>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

