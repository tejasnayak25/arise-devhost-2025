# arise-devhost-2025
# AI-Powered Carbon Compliance & ESG Reporting Automation 
## Problem Statement: 
Across the Nordic region, companies are under increasing pressure from both 
EU and national regulations to 
report and reduce their carbon footprint. The upcoming **EU Corporate 
Sustainability Reporting Directive 
(CSRD) and EU Taxonomy rules** require organizations of all sizes to produce 
transparent **ESG** (Environmental, Social, Governance) data. 
However, many businesses — especially in construction, manufacturing, and 
energy sectors — rely on manual spreadsheets and inconsistent data 
collection from invoices, sensors, and energy systems. This results in 
inaccurate, late, or non-compliant ESG reports.\
The problem is further amplified by data fragmentation, where carbon 
information is stored in different systems (ERP, utility bills, energy meters) that 
don’t communicate. Companies risk financial penalties, reputation loss, 
and missed green financing opportunities due to non-compliance. 
There’s a critical need for an automated, intelligent system to simplify ESG 
reporting and help Nordic companies track and reduce emissions proactively.

## How to Run Locally

### Backend (FastAPI + Supabase)

1. **Set up environment variables:**

   Create a `.env` file in `backend/` with:
   ```
   SUPABASE_URL=<your-project-url>
   SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
   ```
   (Or use `SUPABASE_ANON_KEY` instead of service role key)

2. **Install dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Run the API server:**

   From the project root directory:
   ```bash
   uvicorn backend.main:app --reload
   ```

   Or if you're in the `backend/` directory:
   ```bash
   cd ..  # Go to project root
   uvicorn backend.main:app --reload
   ```

   The API will be available at `http://localhost:8000`

4. **Verify Supabase connection:**

   Visit `http://localhost:8000/health/supabase` — you should see:
   ```json
   { "supabase_client_initialized": true, "rest_url": "..." }
   ```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Code Structure

- **Backend API:** `backend/main.py` (FastAPI app)
- **Supabase client:** `backend/api/supabase_client.py`
- **Vercel entrypoint:** `backend/index.py` (for serverless deployment)

## Deploy to Vercel (frontend + serverless API)

Project is configured for Vercel with:

- Serverless Python API entry: `backend/index.py` (loads FastAPI app from `backend/main.py`)
- Python dependencies: `backend/requirements.txt`
- Build and routing config: `vercel.json`

### Configure environment variables in Vercel

Set these in the project settings (Production, Preview, Development):

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`)

Optionally, use Vercel Encrypted Environment Variables and reference them in `vercel.json`.

### One-time setup

1. Log in and link the repo:

   ```bash
   vercel login
   vercel link
   ```

2. Deploy (detects `vercel.json` and builds):

   ```bash
   vercel
   ```

3. Promote to production:

   ```bash
   vercel --prod
   ```

### Verify after deploy

- Backend health: `https://<your-vercel-domain>/api/health/supabase`
- Frontend built from `frontend/dist` and served for all non-`/api/*` routes