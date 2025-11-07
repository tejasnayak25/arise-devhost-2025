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
export async function uploadFile(file, company_id) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('company_id', company_id)

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
export async function uploadFiles(files, company_id, onProgress) {
  const results = [];
  for (let i = 0; i < files.length; i++) {
    try {
      const result = await uploadFile(files[i], company_id);
      let invoiceData = null;
      if (result) {
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
export async function getFilesFromStorage(company_id) {
  try {
    const authHeaders = await getAuthHeaders()

    const response = await fetch(`${API_BASE_URL}/api/files?company_id=${encodeURIComponent(company_id)}`, {
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

/**
 * Create a sensor on the backend (saves to sensors table)
 * @param {Object} payload - sensor metadata (device_id, power_kW, emission_factor, last_analysis)
 * @returns {Promise<Object>} - created sensor record
 */
export async function createSensor(payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sensors`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...payload,
        email: (await supabase.auth.getUser()).data.user.email
      })
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `Failed to create sensor: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error creating sensor:', error)
    throw error
  }
}

/**
 * Fetch sensors for the authenticated user
 * @returns {Promise<Array>} - list of sensor records
 */
export async function getSensors(company_id) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sensors?company_id=${company_id}`, {
      method: 'GET',
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `Failed to fetch sensors: ${response.statusText}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Error fetching sensors:', error)
    throw error
  }
}

