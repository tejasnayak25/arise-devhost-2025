import React from 'react'
import { ResponsiveContainer, PieChart, Pie, Cell, Legend, Tooltip } from 'recharts'

const COLORS = ['#60a5fa', '#34d399']

export default function EmissionsBreakdown({ invoiceKg = 0, sensorKg = 0 }) {
  const data = [
    { name: 'Invoices', value: Number(invoiceKg) || 0 },
    { name: 'Sensors', value: Number(sensorKg) || 0 }
  ]

  return (
    <div style={{ width: '100%', height: 220 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={40}
            outerRadius={80}
            paddingAngle={3}
            label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => `${value} kg CO₂e`} />
          <Legend verticalAlign="bottom" />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
