# --- New endpoint: Get last month's invoice data for dashboard ---
from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, Form, Body
from fastapi.responses import JSONResponse
import json as _json
import os
import requests
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from backend.api.file_processor import process_uploaded_file
from backend.api.supabase_client import (
    get_supabase_client,
    initialize_supabase_from_env,
)
from backend.api.company_api import router as company_router
from apscheduler.schedulers.background import BackgroundScheduler
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4



app = FastAPI()
app.include_router(company_router)

GEMINI_API_KEY = os.getenv("GOOGLE_AI_API")

# Initialize scheduler
scheduler = BackgroundScheduler()



@app.get("/")
async def root():
    return {"message": " AI-Powered Carbon Compliance & ESG Reporting Automation"}


@app.on_event("startup")
async def startup_event() -> None:
	# Initialize Supabase client and attach to app state
	client = initialize_supabase_from_env()
	app.state.supabase = client


def supabase_dep():
	return app.state.supabase


def generate_monthly_reports():
    """Generate a markdown report per company for the current month and upload to storage."""
    client = app.state.supabase
    if not client:
        return
    # Fetch all companies
    companies_res = client.table("companies").select("id, name").execute()
    companies = companies_res.data or []
    for c in companies:
        company_id = c.get("id")
        company_name = c.get("name")
        # Use existing analytics endpoint logic programmatically
        today = datetime.utcnow()
        first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (first_of_this_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        q = (
            client.table("invoices")
            .select("*")
            .eq("company_id", company_id)
            .gte("created_at", first_of_this_month.isoformat())
            .lt("created_at", next_month.isoformat())
        )
        r = q.execute()
        rows = r.data or []
        # Simple aggregates
        total_spend = sum([row.get("price") or 0 for row in rows if isinstance(row.get("price"), (int, float))])
        total_emissions = sum([row.get("quantity") or 0 for row in rows if isinstance(row.get("quantity"), (int, float))])
        item_counts = {}
        for row in rows:
            typ = row.get("type") or "other"
            item_counts[typ] = item_counts.get(typ, 0) + 1

        # Load regulations to include in the report (best-effort)
        try:
            with open('backend/data/regulations.json', 'r', encoding='utf-8') as rf:
                regs = _json.load(rf)
        except Exception:
            regs = []

        # Create PDF report
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=A4)
        width, height = A4
        y = height - 50
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"Monthly Carbon Report - {company_name}")
        y -= 30
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Period: {first_of_this_month.date()} to {(next_month - timedelta(days=1)).date()}")
        y -= 20
        c.drawString(40, y, f"Total Emissions (sum of quantity): {total_emissions} tCO₂e")
        y -= 16
        c.drawString(40, y, f"Total Spend: ${total_spend}")
        y -= 24
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Breakdown by Type")
        y -= 18
        c.setFont("Helvetica", 10)
        for t, cnt in item_counts.items():
            line = f"- {t}: {cnt}"
            c.drawString(50, y, line)
            y -= 14
            if y < 60:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

        # Regulations cited
        y -= 8
        c.setFont("Helvetica-Bold", 12)
        if y < 80:
            c.showPage()
            y = height - 50
        c.drawString(40, y, "Regulations referenced")
        y -= 18
        c.setFont("Helvetica", 9)
        for reg in regs:
            reg_line = f"{reg.get('id')}: {reg.get('title')}"
            c.drawString(44, y, reg_line)
            y -= 12
            if y < 60:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)

        # Raw items
        y -= 8
        c.setFont("Helvetica-Bold", 12)
        if y < 80:
            c.showPage()
            y = height - 50
        c.drawString(40, y, "Raw Items")
        y -= 18
        c.setFont("Helvetica", 9)
        for row in rows:
            text = f"- {row.get('name','')} | qty: {row.get('quantity','')} | price: {row.get('price','')} | unit: {row.get('unit','')} | type: {row.get('type','')}"
            # naive wrap: if too long, split
            if len(text) > 100:
                parts = [text[i:i+100] for i in range(0, len(text), 100)]
                for p in parts:
                    c.drawString(44, y, p)
                    y -= 12
                    if y < 60:
                        c.showPage()
                        y = height - 50
                        c.setFont("Helvetica", 9)
            else:
                c.drawString(44, y, text)
                y -= 12
            if y < 60:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)

        c.save()
        pdf_bytes = pdf_buffer.getvalue()

        # Upload PDF to storage
        filename = f"reports/{company_id}/monthly-report-{first_of_this_month.strftime('%Y-%m')}.pdf"
        try:
            client.storage.from_("Default Bucket").upload(filename, pdf_bytes)
        except Exception:
            try:
                client.storage.from_("Default Bucket").remove([filename])
            except Exception:
                pass
            client.storage.from_("Default Bucket").upload(filename, pdf_bytes)


# Start scheduler job: run once daily at 00:05 to ensure monthly file on first of month
@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(generate_monthly_reports, 'cron', hour=10, minute=15)
    scheduler.start()



@app.get("/health/supabase")
async def supabase_health(client = Depends(supabase_dep)):
	# Lightweight health: confirm client is initialized and env present
	url = client.rest_url if hasattr(client, "rest_url") else None
	return {"supabase_client_initialized": True, "rest_url": url}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), email: str = Form(...)):
    """
    Upload and process a file.
    - If CSV: parses and returns structured data
    - If other format (PDF, images): uses OCR to extract text
    - Saves the file to Supabase storage under /{email}/{filename}
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    # return
    try:
		# Process the file

        if(file.content_type == 'application/pdf' or file.content_type.startswith('image/')):
            result = await process_uploaded_file(file)
            # For images/PDFs, need to re-read for upload
            await file.seek(0)
            file_content = await file.read()
        else:
            # Read file content as bytes, then decode to string (try utf-8, fallback to latin-1)
            file_bytes = await file.read()
            try:
                text = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                text = file_bytes.decode('latin-1')
            result = {"text": text}
            file_content = file_bytes

        # Save the file to Supabase storage
        supabase = app.state.supabase
        file_path = f"{email}/{file.filename}"
        response = supabase.storage.from_("Default Bucket").upload(file_path, file_content)

        if not response:
            raise HTTPException(status_code=500, detail=f"Error saving file to storage: {response['error']['message']}")

        result["storage_path"] = file_path
        return JSONResponse(content=result)

    except Exception as e:
        raise HTTPException(
            status_code=e['statusCode'] if isinstance(e, dict) and 'statusCode' in e else 500,
            detail=f"Error processing file: {str(e)}"
        )


@app.get("/api/files")
async def get_files(email: str, client = Depends(supabase_dep)):
    try:
        response = client.storage.from_("Default Bucket").list(email, {"limit": 100, "offset": 0})

        files = [
            {
                "id": file.get("id"),
                "name": file.get("name"),
                "created_at": file.get("created_at"),
				"size": file.get("metadata").get("size")
            }
            for file in response
        ]

        return JSONResponse(content=files)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching files: {str(e)}"
        )


# Request model for parse-invoice
class ParseInvoiceRequest(BaseModel):
    text: str
    company_id: str

# Invoice line item model
class Invoice(BaseModel):
    name: str | None = Field(default=None)
    quantity: int | None = Field(default=None)
    price: int | None = Field(default=None)
    unit: str | None = Field(default=None)
    type: str | None = Field(default=None)

@app.post("/api/parse-invoice")
async def parse_invoice(payload:dict = Body(...)):
    """
    Parse invoice data using Gemini 2.5 Flash model, store in invoices table, and return carbon emission data as JSON.
    Input: plain text (invoice)
    Output: JSON with carbon emission data
    """

    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured.")

    system_prompt = (
        "You are an expert in sustainability and carbon accounting. "
        "From the following raw invoice text, extract only the following fields for each item: "
        "name (the description of the item, e.g., 'Electricity', 'Natural Gas', 'Freight'), "
        "quantity (the amount or number of units for the item, e.g., 100, 5), "
        "price (the price or cost associated with the item, e.g., 1200, 50), "
        "unit (the unit of measurement for the quantity, e.g., 'kWh', 'kg', 'liters', 'hours'; if no unit is applicable, use 'item'), "
        "type (the type or category of the item, e.g., 'energy', 'material', 'service'). "
        "Remove any unnecessary or unrelated information. "
        "Return ALL line items found in the invoice as a JSON array of objects (do not stop after the first item). "
        "Each object must contain the fields: name, quantity, price, unit, and type. If a field is missing for an item, use null. "
        "If a numeric value is present for quantity or price, return it as a number. If no unit applies, set unit to 'item'."
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                # Require an array of Invoice objects
                response_json_schema={
                    "type": "array",
                    "items": Invoice.model_json_schema()
                },
            ),
            contents=payload['text']
        )

        # Try to parse as list of Invoice dicts
        import json as pyjson
        try:
            result = pyjson.loads(response.text)
        except Exception:
            result = {"raw_output": response.text}
            return JSONResponse(content=result)

        # Store parsed data in invoices table
        supabase = app.state.supabase
        # If result is a dict (single item), wrap in list for DB insert
        items = result if isinstance(result, list) else [result] if isinstance(result, dict) else []
        if items:
            to_insert = []
            for row in items:
                # Only insert if at least one field is present and company_id is provided
                if payload['company_id'] and any(row.get(f) is not None for f in ("quantity", "price", "unit", "type")):
                    to_insert.append({
                        "name": row.get("name", None),
                        "quantity": row.get("quantity", None),
                        "price": row.get("price", None),
                        "unit": row.get("unit", None),
                        "type": row.get("type", None),
                        "company_id": payload['company_id'],
                        "invoice_path": payload["storage_path"]
                    })
            if to_insert:
                insert_result = supabase.table("invoices").insert(to_insert).execute()
                if hasattr(insert_result, "error") and insert_result.error:
                    raise HTTPException(status_code=500, detail=f"Failed to insert invoices: {insert_result.error}")

        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")
    


@app.get("/api/company-invoices-current-month")
async def get_company_invoices_current_month(company_id: str, client=Depends(supabase_dep)):
    """
    Fetch and aggregate invoice data for the given company for the current calendar month.
    Returns: { total_emissions, total_spend, item_counts, time_series, raw }
    """
    # Calculate current month's date range
    today = datetime.utcnow()
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (first_of_this_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    # Query invoices for this company and current month
    query = (
        client.table("invoices")
        .select("*")
        .eq("company_id", company_id)
        .gte("created_at", first_of_this_month.isoformat())
        .lt("created_at", next_month.isoformat())
    )
    result = query.execute()
    if hasattr(result, "error") and result.error:
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {result.error}")
    rows = result.data or []

    # Aggregate KPIs
    total_emissions = 0
    total_spend = 0
    item_counts = {}
    time_series = {}
    for row in rows:
        # Sum price as spend
        price = row.get("price")
        if isinstance(price, (int, float)):
            total_spend += price
        # Sum quantity as emissions for all types
        quantity = row.get("quantity")
        if isinstance(quantity, (int, float)):
            total_emissions += quantity
        # Count by type
        typ = row.get("type")
        if typ:
            item_counts[typ] = item_counts.get(typ, 0) + 1
        # Time series by day (emissions)
        created = row.get("created_at")
        if created:
            day = created[:10]  # YYYY-MM-DD
            val = quantity if isinstance(quantity, (int, float)) else 0
            time_series[day] = time_series.get(day, 0) + val

    # Compose response
    return JSONResponse(content={
        "total_emissions": total_emissions,
        "total_spend": total_spend,
        "item_counts": item_counts,
        "time_series": time_series,
        "raw": rows
    })


@app.get('/api/reports')
async def list_reports(company_id: str, client=Depends(supabase_dep)):
    """List report files for a company in storage"""
    try:
        prefix = f"reports/{company_id}/"
        objs = client.storage.from_("Default Bucket").list(prefix)
        files = []
        for o in objs:
            # storage list may return full path in 'name'
            name = o.get('name')
            display_name = name
            if isinstance(name, str) and name.startswith(prefix):
                display_name = name[len(prefix):]
            files.append({"name": display_name, "path": name})
        return JSONResponse(content={"files": files})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/reports/download')
async def download_report(path: str, company_id: int, client=Depends(supabase_dep)):
    """Generate a temporary download URL for a report file. `path` should be the full storage path (e.g. 'reports/<company_id>/file.pdf')."""
    try:
        # create signed URL for 1 hour
        url = client.storage.from_("Default Bucket").create_signed_url(f"reports/{company_id}/{path}", 3600)
        # supabase-py may return a dict with various key names for the url
        if isinstance(url, dict):
            signed = url.get('signedURL') or url.get('signed_url') or url.get('signedUrl') or url.get('url')
        else:
            signed = url
        return JSONResponse(content={"url": signed})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Analyze current month report with Gemini
@app.post("/api/analyze-current-month-report")
async def analyze_current_month_report(company_id: int, prompt:str = Body(...), client=Depends(supabase_dep)):
    """
    Analyze the current month's invoice report for a company using Gemini.
    """
    # Fetch current month analytics (reuse logic from /api/company-invoices-current-month)
    today = datetime.utcnow()
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (first_of_this_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    query = (
        client.table("invoices")
        .select("*")
        .eq("company_id", company_id)
        .gte("created_at", first_of_this_month.isoformat())
        .lt("created_at", next_month.isoformat())
    )
    result = query.execute()
    if hasattr(result, "error") and result.error:
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {result.error}")
    rows = result.data or []

    # Compose a summary string for Gemini
    summary = f"{prompt}. Given data for the month: " + "\n".join([
        f"{r.get('name','')}, {r.get('quantity','')}, {r.get('price','')}, {r.get('unit','')}, {r.get('type','')}" for r in rows
    ])

    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured.")

    try:
        client_gemini = genai.Client(api_key=GEMINI_API_KEY)
        response = client_gemini.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction="You are a sustainability analyst. Answer concisely based on the provided invoice data.",
                response_mime_type="text/plain",
            ),
            contents=summary
        )
        return {"analysis": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini analysis error: {str(e)}")



@app.post('/api/reports/generate')
async def trigger_generate_reports(client=Depends(supabase_dep)):
    """Trigger generation of monthly reports on-demand (for testing)."""
    try:
        generate_monthly_reports()
        return JSONResponse(content={'status': 'started'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ComplianceCompareRequest(BaseModel):
    company_id: int
    prompt: str | None = None


@app.post('/api/compliance/compare')
async def compare_compliance(payload: ComplianceCompareRequest = Body(...), client=Depends(supabase_dep)):
    """Compare current month's invoice-derived emissions/spend against regulations and return a structured comparison.
    Expects JSON body: { company_id: int, prompt?: string }
    """
    # Load regulations
    try:
        with open('backend/data/regulations.json', 'r', encoding='utf-8') as f:
            regulations = _json.load(f)
    except Exception:
        regulations = []

    # Fetch current month invoices
    today = datetime.utcnow()
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (first_of_this_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    query = (
        client.table('invoices')
        .select('*')
        .eq('company_id', payload.company_id)
        .gte('created_at', first_of_this_month.isoformat())
        .lt('created_at', next_month.isoformat())
    )
    res = query.execute()
    rows = res.data or []

    # Compose summary for model
    prmpt = payload.prompt or 'Compare this company month against regulations'
    summary = f"{prmpt}. Month: {first_of_this_month.date()} - {(next_month - timedelta(days=1)).date()}\n"
    summary += "Items:\n"
    for r in rows:
        summary += f"- {r.get('name','')} | qty: {r.get('quantity','')} | price: {r.get('price','')} | unit: {r.get('unit','')} | type: {r.get('type','')}\n"

    # If Gemini configured, attempt LLM analysis
    if GEMINI_API_KEY:
        try:
            client_g = genai.Client(api_key=GEMINI_API_KEY)
            response = client_g.models.generate_content(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(
                    system_instruction='You are a regulatory compliance analyst. Compare the provided company monthly invoice data against the list of regulations and produce a JSON array of findings. Each finding should include: regulation_id, regulation_title, compliance_status (Compliant/Non-compliant/Not enough data), explanation, recommended_actions.',
                    response_mime_type='application/json'
                ),
                contents=summary + '\nRegulations:\n' + _json.dumps(regulations)
            )
            import json as _pyjson
            try:
                findings = _pyjson.loads(response.text)
            except Exception:
                findings = {'analysis': response.text}
            return JSONResponse(content={'regulations': regulations, 'findings': findings})
        except Exception:
            # fall back to heuristic
            pass

    # Heuristic fallback
    total_emissions = sum([r.get('quantity') or 0 for r in rows if isinstance(r.get('quantity'), (int, float))])
    total_spend = sum([r.get('price') or 0 for r in rows if isinstance(r.get('price'), (int, float))])
    findings = []
    for reg in regulations:
        status = 'Not enough data'
        explanation = ''
        if reg.get('id') == 'CSRD-1':
            if total_emissions > 0:
                status = 'Compliant'
                explanation = f'GHG inventory present (sum quantity = {total_emissions})'
            else:
                status = 'Non-compliant'
                explanation = 'No GHG quantity data present in invoices.'
        else:
            status = 'Not enough data'
            explanation = 'Requires manual evidence collection.'
        findings.append({
            'regulation_id': reg.get('id'),
            'regulation_title': reg.get('title'),
            'compliance_status': status,
            'explanation': explanation,
            'recommended_actions': reg.get('notes')
        })

    return JSONResponse(content={'regulations': regulations, 'findings': findings})