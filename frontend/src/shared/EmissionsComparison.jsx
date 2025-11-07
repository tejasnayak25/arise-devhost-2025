import React from 'react'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts'

export default function EmissionsComparison({ data }) {
  // data expected: [{ date: 'YYYY-MM-DD', positive: 10, negative: 50 }, ...]
  // Compute totals across the dataset
  let totalPositive = 0
  let totalNegative = 0
  try {
    for (const d of data || []) {
      const p = Number(d?.positive) || 0
      const n = Number(d?.negative) || 0
      totalPositive += p
      totalNegative += n
    }
  } catch (e) {
    totalPositive = 0
    totalNegative = 0
  }

  const pieData = [
    { name: 'Emissions (kg CO2e)', value: totalNegative },
    { name: 'Removals / Credits (kg CO2e)', value: totalPositive }
  ]

  const COLORS = ['#60a5fa', '#34d399']

  const total = totalNegative + totalPositive

  return (
    <div style={{ width: '100%', height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={pieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={48}
            outerRadius={80}
            paddingAngle={4}
            label={({ name, percent, value }) => `${name.split(' ')[0]} ${percent ? (percent*100).toFixed(0) + '%' : ''}`}
          >
            {pieData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{backgroundColor: "white"}} formatter={(value) => `${value} kg CO₂e`} />
          <Legend verticalAlign="bottom" />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: 'absolute', textAlign: 'center', pointerEvents: 'none' }}>
        <div style={{ fontSize: 16, fontWeight: 600 }}>{total.toLocaleString()}</div>
        <div style={{ fontSize: 12, color: '#9ca3af' }}>kg CO2e (total)</div>
      </div>
    </div>
  )
}
