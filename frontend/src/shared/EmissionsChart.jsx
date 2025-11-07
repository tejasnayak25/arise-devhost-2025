import React from 'react'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'

export default function EmissionsChart({ data }) {
  const formatYAxis = (value) => {
    // Format large numbers with commas
    try {
      return value.toLocaleString()
    } catch (e) {
      return value
    }
  }

  const formatXAxis = (val) => {
    // Expecting val like '2025-03' or '2025-03-01' or ISO-like. Return only the year.
    try {
      const s = String(val)
      const parts = s.split('-')
      if (parts.length >= 1 && parts[0].length === 4 && !isNaN(Number(parts[0]))) {
        return parts[1] + "/" + parts[0]
      }
      // fallback: attempt Date parse
      const d = new Date(s)
      if (!isNaN(d)) return d.getMonth() + 1 + '/' + d.getFullYear()
      return s
    } catch (e) {
      return val
    }
  }

  return (
    <div style={{ width: '100%', height: 280 }}>
      <ResponsiveContainer>
        {/* add left margin so the rotated Y-axis label doesn't get clipped */}
        <AreaChart data={data} margin={{ top: 20, right: 20, left: 20, bottom: 25 }}>
          <defs>
            <linearGradient id="colorCo2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="#60a5fa" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#9ca3af', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={formatXAxis}
            label={{ value: 'Year', position: 'bottom', offset: 12, fill: '#9ca3af', fontSize: 12 }}
          />
          <YAxis
            tick={{ fill: '#9ca3af', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={formatYAxis}
            label={{ value: 'Emissions (kg CO2e)', angle: -90, position: 'insideLeft', offset: 8, dx: 0, fill: '#9ca3af', fontSize: 12 }}
          />
          <Tooltip contentStyle={{ background: '#0b1220', border: '1px solid rgba(255,255,255,.1)', color: '#e5e7eb' }} formatter={(val) => [val, 'kg CO2e']} />
          <Area type="monotone" dataKey="kgco2" stroke="#60a5fa" fillOpacity={1} fill="url(#colorCo2)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

