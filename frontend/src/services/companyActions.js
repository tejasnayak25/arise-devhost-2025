// Create a new company and associate the user
export async function createCompany(companyName, userEmail) {
  const response = await fetch('/api/create-company', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_name: companyName, user_email: userEmail })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to create company');
  }
  return await response.json();
}

// Join an existing company by code or name
export async function joinCompany(id, userEmail) {
  const response = await fetch('/api/join-company', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: id, user_email: userEmail })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to join company');
  }
  return await response.json();
}
