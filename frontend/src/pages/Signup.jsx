import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [message, setMessage] = useState('')
  const { signUp, signInWithGoogle } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)

    try {
      const { data, error } = await signUp(email, password)
      if (error) {
        setError(error.message)
      } else {
        setMessage('Account created! Please check your email to verify your account.')
        setTimeout(() => {
          navigate('/login')
        }, 2000)
      }
    } catch (err) {
      setError('An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogleSignIn() {
    setError('')
    setMessage('')
    setGoogleLoading(true)
    try {
      const { error } = await signInWithGoogle()
      if (error) {
        console.error('Google sign-in error:', error)
        setError(error.message || 'Failed to sign in with Google. Please check your Supabase configuration.')
        setGoogleLoading(false)
      } else {
        // OAuth will redirect, so we don't need to do anything here
        // The loading state will persist until redirect happens
      }
    } catch (err) {
      console.error('Unexpected error:', err)
      setError(err.message || 'An unexpected error occurred. Please try again.')
      setGoogleLoading(false)
    }
  }

  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center', 
      minHeight: '100vh'
    }}>
      <div className="panel" style={{
        width: '100%',
        maxWidth: 400,
        padding: 32,
        marginTop: -60
      }}>
        <div style={{ width: "100%", display: "flex", justifyContent: "center", alignItems: "center" }}>
          <img src="/logo.png" alt="Logo" style={{width: "55%", objectFit: "cover", aspectRatio: "16 / 4.5"}} />
        </div>
        <p className="muted" style={{ margin: '0 0 24px', fontSize: 14, textAlign: "center" }}>Create a new account</p>

        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{
              marginBottom: 16,
              padding: 12,
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              color: 'var(--danger)',
              borderRadius: 10,
              fontSize: 13,
              border: '1px solid rgba(239, 68, 68, 0.3)'
            }}>
              {error}
            </div>
          )}

          {message && (
            <div style={{
              marginBottom: 16,
              padding: 12,
              backgroundColor: 'rgba(34, 197, 94, 0.15)',
              color: 'var(--brand)',
              borderRadius: 10,
              fontSize: 13,
              border: '1px solid rgba(34, 197, 94, 0.3)'
            }}>
              {message}
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label>Confirm Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading || googleLoading}
            className="btn"
            style={{ width: '100%', marginBottom: 16 }}
          >
            {loading ? 'Creating account...' : 'Sign Up'}
          </button>
        </form>

        {/* <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          margin: '24px 0',
          gap: 12
        }}>
          <div style={{ flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.1)' }} />
          <span className="muted" style={{ fontSize: 12 }}>OR</span>
          <div style={{ flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.1)' }} />
        </div>

        <button
          onClick={handleGoogleSignIn}
          disabled={loading || googleLoading}
          className="btn secondary"
          style={{ 
            width: '100%', 
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8
          }}
        >
          {googleLoading ? (
            'Connecting...'
          ) : (
            <>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/>
                <path d="M9 18c2.43 0 4.467-.806 5.965-2.184l-2.908-2.258c-.806.54-1.837.86-3.057.86-2.35 0-4.34-1.587-5.053-3.72H.957v2.331C2.438 15.983 5.482 18 9 18z" fill="#34A853"/>
                <path d="M3.957 10.698c-.18-.54-.282-1.117-.282-1.698s.102-1.158.282-1.698V4.971H.957C.348 6.175 0 7.55 0 9s.348 2.825.957 4.029l3-2.331z" fill="#FBBC05"/>
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.971L3.957 7.3C4.67 5.163 6.66 3.58 9 3.58z" fill="#EA4335"/>
              </svg>
              Continue with Google
            </>
          )}
        </button> */}

        <div style={{ textAlign: 'center', fontSize: 13 }} className="muted">
          Already have an account?{' '}
          <Link to="/login" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
            Sign in
          </Link>
        </div>
      </div>
    </div>
  )
}

