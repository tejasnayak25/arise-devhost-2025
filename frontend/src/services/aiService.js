// Placeholder AI layer. Replace with real LLM/Rules/Vector logic.

export function getAiInsights() {
  return [
    {
      title: 'High electricity intensity at Plant A',
      detail: 'Shift 2 shows 14% higher kWh/unit vs baseline. Consider motor retrofits or VFDs.'
    },
    {
      title: 'Scope 3 data coverage gap',
      detail: 'Only 41% of supplier categories reported. Prioritize Tier-1 metals & transport.'
    },
    {
      title: 'Eligible green CapEx opportunity',
      detail: 'Heat pump upgrade qualifies under EU Taxonomy: substantial contribution to climate mitigation.'
    }
  ]
}

export function suggestReductionRoadmap(input) {
  // Return an example ordered set of actions
  return [
    { action: 'Energy audit (ISO 50002)', impact: 'Medium', cost: 'Low', payback: '3-6 mo' },
    { action: 'LED + controls', impact: 'Medium', cost: 'Low', payback: '12 mo' },
    { action: 'Heat pump retrofit', impact: 'High', cost: 'High', payback: '36 mo' },
    { action: 'PV + PPA', impact: 'High', cost: 'Medium', payback: '48 mo' },
  ]
}

