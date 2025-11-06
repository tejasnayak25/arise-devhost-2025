// Simplified compliance checklist for CSRD / EU Taxonomy tracking

export function getComplianceChecklist() {
  return [
    {
      area: 'CSRD Disclosures',
      requirement: 'Double materiality assessment completed',
      status: 'Pending',
      nextAction: 'Run stakeholder workshop; document financial + impact materiality.'
    },
    {
      area: 'CSRD KPIs',
      requirement: 'GHG inventory (Scopes 1-3) compiled',
      status: 'In Progress',
      nextAction: 'Ingest supplier data (Scope 3 cat. 1, 4, 5).'
    },
    {
      area: 'EU Taxonomy',
      requirement: 'Eligibility assessment for CapEx/OpEx',
      status: 'Done',
      nextAction: 'Collect technical screening criteria evidence.'
    },
    {
      area: 'Governance',
      requirement: 'Board oversight of climate targets',
      status: 'In Progress',
      nextAction: 'Schedule quarterly review; link exec compensation.'
    }
  ]
}

