// Fetch the user's company info from the backend
export async function getUserCompany(email) {
  const response = await fetch(`/api/user-company?email=${encodeURIComponent(email)}`);
  if (!response.ok) {
    if (response.status === 404) return null; // Not in a company
    throw new Error('Failed to fetch company info');
  }
  return await response.json();
}
