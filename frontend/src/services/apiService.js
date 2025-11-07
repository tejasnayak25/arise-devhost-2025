// API service for backend communication
// In development, Vite proxy handles /api requests
// In production, use VITE_API_URL env variable or default to relative path
import { supabase } from './supabaseClient'

const API_BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '' : 'http://localhost:8000')

/**
 * Get auth headers with JWT token
 * @returns {Promise<Object>} - Headers object with Authorization
 */
async function getAuthHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  const headers = {}
  
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`
  }
  
  return headers
}

/**
 * Upload a file to the backend for processing
 * @param {File} file - The file to upload
 * @returns {Promise<Object>} - The processed file data
 */
export async function uploadFile(file, email) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('email', email)

  try {
    const authHeaders = await getAuthHeaders()
    
    const response = await fetch(`${API_BASE_URL}/api/upload`, {
      method: 'POST',
      headers: authHeaders,
      body: formData,
    })

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Unauthorized. Please sign in again.')
      }
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `Upload failed: ${response.statusText}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('File upload error:', error)
    throw error
  }
}

/**
 * Parse invoice using backend API
 * @param {string} text - The text content of the invoice
 * @returns {Promise<Object>} - Parsed invoice data
 */
export async function parseInvoice(text, company_id, storage_path) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/parse-invoice`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text, company_id, storage_path })
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Failed to parse invoice: ${response.statusText}`);
    }
    // Always return the parsed invoice data (array or object)
    return await response.json();
  } catch (error) {
    console.error('Error parsing invoice:', error);
    throw error;
  }
}

/**
 * Upload multiple files sequentially
 * @param {File[]} files - Array of files to upload
 * @param {Function} onProgress - Callback for progress updates (fileIndex, result)
 * @returns {Promise<Array>} - Array of upload results
 */
export async function uploadFiles(files, email, company_id, onProgress) {
  const results = [];
  for (let i = 0; i < files.length; i++) {
    try {
      const result = await uploadFile(files[i], email);
      let invoiceData = null;
      if (result) {
        console.log(result)
        if(result.type === "csv") {
          invoiceData = await parseInvoice(JSON.stringify(result), company_id, result.storage_path);
        } else if(result.text) {
          invoiceData = await parseInvoice(result.text, company_id, result.storage_path);
        }
      }
      results.push({ file: files[i], success: true, data: result, invoice: invoiceData });
      if (onProgress) {
        onProgress(i, { file: files[i], success: true, data: result, invoice: invoiceData });
      }
    } catch (error) {
      results.push({ file: files[i], success: false, error: error.message });
      if (onProgress) {
        onProgress(i, { file: files[i], success: false, error: error.message });
      }
    }
  }
  return results;
}

/**
 * Fetch files from the backend for a given email
 * @param {string} email - The email to fetch files for
 * @returns {Promise<Array>} - Array of files with metadata
 */
export async function getFilesFromStorage(email) {
  try {
    const authHeaders = await getAuthHeaders()

    const response = await fetch(`${API_BASE_URL}/api/files?email=${encodeURIComponent(email)}`, {
      method: 'GET',
      headers: authHeaders,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `Failed to fetch files: ${response.statusText}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching files from backend:', error)
    throw error
  }
}

