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
        <div className="sidebar-footer">
          {user && (
              <div className="sidebar-user">
              <div className="user-email">{user.email}</div>
              <button
                type="button"
                className="btn secondary small signout-btn"
                onClick={handleSignOut}
                aria-label="Sign out of your account"
                title="Sign out"
              >
                <svg
                  className="signout-icon"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  aria-hidden="true"
                  focusable="false"
                >
                  <path fill="currentColor" d="M16 13v-2H7V8l-5 4 5 4v-3zM20 3H10a2 2 0 0 0-2 2v3h2V5h10v14H10v-3H8v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z" />
                </svg>
                Sign Out
              </button>
            </div>
          )}
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

