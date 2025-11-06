# ESG Automation (AI-Powered Carbon Compliance & Reporting)

A minimal React (Vite) starter that demonstrates an automated ESG reporting workflow for Nordic companies subject to CSRD and EU Taxonomy.

Features
- Dashboard with KPIs and emissions trend (mock data)
- Data Sources page for file uploads and live connectors (ERP, utility, meters)
- Reports page with CSRD-aligned preview table
- Compliance checklist for CSRD/EU Taxonomy
- AI Assistant sidebar with example insights and roadmap suggestions (mock)

Getting Started
1. Install dependencies

```bash
npm install
```

2. Run dev server

```bash
npm run dev
```

3. Build for production

```bash
npm run build && npm run preview
```

Tech Stack
- React + Vite
- react-router-dom for routing
- recharts for visualization

Next Steps (Integrations / AI)
- Replace mocks in `src/services/*` with real connectors (ERP, utility APIs, BMS gateways)
- Add ingestion pipelines (CSV/XLSX parsing, invoice OCR, emission factor mapping)
- Persist data (PostgreSQL + API) and compute scopes 1/2/3
- Integrate LLM for insights with retrieval over your ESG data (RAG)
- Export CSRD/EU Taxonomy-compliant reports (PDF/XLSX)

Project Structure
```
src/
  pages/             # Dashboard, DataSources, Reports, Compliance
  services/          # dataService, reportingService, complianceService, aiService
  shared/            # KPIs, EmissionsChart, DataUpload, SourceConnector, AISidebar
  App.jsx, main.jsx, styles.css
```

License
MIT

