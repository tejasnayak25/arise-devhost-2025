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
   
   # OCR API Configuration (choose one)
   OCR_PROVIDER=ocrspace  # or "google_vision"
   OCRSPACE_API_KEY=<your-ocrspace-key>  # Optional for free tier
   # OR for Google Vision:
   # GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   # OR
   # GOOGLE_VISION_API_KEY=<your-api-key>
   ```
   
   **OCR Provider Options:**
   - **OCR.space** (default, free tier available): Set `OCR_PROVIDER=ocrspace` and optionally `OCRSPACE_API_KEY`
   - **Google Cloud Vision**: Set `OCR_PROVIDER=google_vision` and provide credentials

2. **Install Python dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```
   
   **Note**: OCR uses external APIs (no local model downloads required). See OCR configuration above.

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

1. **Set up environment variables:**

   Create a `.env` file in `frontend/` with:
   ```
   VITE_SUPABASE_URL=<your-supabase-project-url>
   VITE_SUPABASE_ANON_KEY=<your-supabase-anon-key>
   ```

2. **Install dependencies and run:**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   The frontend will be available at `http://localhost:5173` (or the port Vite assigns)

### API Endpoints

- `GET /` - Root endpoint
- `GET /health/supabase` - Health check for Supabase connection
- `POST /api/upload` - File upload endpoint
  - **CSV files**: Parses and returns structured data as JSON
  - **Other files** (PDF, images): Uses OCR API to extract text (no local dependencies)
  - **OCR Providers**: Supports OCR.space (free tier) and Google Cloud Vision
  - Example request:
    ```bash
    curl -X POST "http://localhost:8000/api/upload" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "file=@yourfile.csv"
    ```

### Code Structure

- **Backend API:** `backend/main.py` (FastAPI app)
- **Supabase client:** `backend/api/supabase_client.py`
- **File processor:** `backend/api/file_processor.py` (CSV parsing & OCR API integration)
- **OCR API:** `backend/api/ocr_api.py` (supports multiple OCR providers)
- **Vercel entrypoint:** `backend/index.py` (for serverless deployment)

**OCR Technology:**
- Uses **OCR APIs** (no local dependencies or model downloads)
- Supports **OCR.space** (free tier available) and **Google Cloud Vision**
- Uses **PyMuPDF** for PDF handling (pure Python)
- Works in serverless environments like Vercel
- Configure via `OCR_PROVIDER` environment variable

**Authentication:**
- Uses **Supabase Auth** for user authentication
- Supports **email/password** and **Google OAuth** sign-in
- Protected routes require login
- JWT tokens included in API requests
- Session persistence enabled

**To enable Google OAuth:**

1. **Set up Google OAuth credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google+ API
   - Go to "Credentials" > "Create Credentials" > "OAuth client ID"
   - Application type: "Web application"
   - Authorized redirect URIs: Add your Supabase redirect URL (see step 3)

2. **Configure Supabase:**
   - Go to your Supabase project dashboard
   - Navigate to **Authentication > Providers**
   - Enable **Google** provider
   - Add your Google OAuth credentials:
     - **Client ID** (from Google Cloud Console)
     - **Client Secret** (from Google Cloud Console)
   - **Site URL**: Set to `http://localhost:5173` (dev) or your production domain
   - **Redirect URLs**: Add these exact URLs:
     - `http://localhost:5173` (for development)
     - `http://localhost:5173/` (with trailing slash)
     - Your production domain (e.g., `https://yourdomain.com`)

3. **Get Supabase Redirect URL:**
   - In Supabase dashboard, go to **Authentication > URL Configuration**
   - Copy the **Redirect URL** (format: `https://<project-ref>.supabase.co/auth/v1/callback`)
   - Add this exact URL to Google Cloud Console's "Authorized redirect URIs"

**Troubleshooting 400 errors:**
- Ensure redirect URLs match exactly (including trailing slashes)
- Check that Google OAuth is enabled in Supabase
- Verify Client ID and Secret are correct
- Make sure Site URL is set in Supabase Authentication settings
- Check browser console for detailed error messages

## Deploy to Vercel (frontend + serverless API)

Project is configured for Vercel with:

- Serverless Python API entry: `backend/index.py` (loads FastAPI app from `backend/main.py`)
- Python dependencies: `backend/requirements.txt`
- Build and routing config: `vercel.json`

### Configure environment variables in Vercel

Set these in the project settings (Production, Preview, Development):

**Backend (Python API):**
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`)
- `OCR_PROVIDER` (default: `ocrspace`)
- `OCRSPACE_API_KEY` (optional, for OCR.space free tier)
- Or for Google Vision: `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_VISION_API_KEY`

**Frontend (React):**
- `VITE_SUPABASE_URL` (same as `SUPABASE_URL`)
- `VITE_SUPABASE_ANON_KEY` (your Supabase anon/public key)

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