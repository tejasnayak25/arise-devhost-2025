# --- New endpoint: Get last month's invoice data for dashboard ---
from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, Form, Body
from fastapi.responses import JSONResponse
import json as _json
import base64
import os
import requests
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import re
import unicodedata
import secrets
from pathlib import PurePosixPath

from backend.api.file_processor import process_uploaded_file
from backend.api import emission_factors
from backend.api.supabase_client import (
    get_supabase_client,
    initialize_supabase_from_env,
)
from backend.api.company_api import router as company_router
import io



app = FastAPI()
app.include_router(company_router)

GEMINI_API_KEY = os.getenv("GOOGLE_AI_API")

# Scheduler will be created at runtime only when enabled (not on serverless hosts like Vercel)
scheduler = None



@app.get("/")
async def root():
    return {"message": " AI-Powered Carbon Compliance & ESG Reporting Automation"}


@app.on_event("startup")
async def startup_event() -> None:
    # Initialize Supabase client and attach to app state
    client = initialize_supabase_from_env()
    app.state.supabase = client
    # Attempt to refresh cached emission factors (if EMISSION_FACTORS_SOURCES configured)
    try:
        emission_factors.refresh_cached_factors()
    except Exception:
        pass


def supabase_dep():
	return app.state.supabase


def _parse_iso(ts: str):
    try:
        if not ts:
            return None
        # handle Z suffix
        if ts.endswith('Z'):
            ts = ts.replace('Z', '+00:00')
        return datetime.fromisoformat(ts)
    except Exception:
        try:
            return datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S')
        except Exception:
            return None


def compute_sensor_emissions(client, company_id: str, start_iso: str, end_iso: str):
    """Fetch sensors and their activity for a company between start_iso and end_iso and compute estimated emissions in kg CO2e.
    Returns: (total_sensor_emissions_kg, sensors_summary_list)
    sensors_summary_list: [{ device_id, energy_kwh, emissions_kg, cycles, on_hours }]
    """
    try:
        # Fetch sensors tied to company_id
        sres = client.table('sensors').select('*').eq('company_id', company_id).execute()
        sensors = sres.data or []
    except Exception:
        sensors = []

    if not sensors:
        return 0, []

    # Map device_id to sensor metadata
    sensor_map = {}
    device_ids = []
    for s in sensors:
        did = s.get('device_id') or s.get('id')
        if not did:
            continue
        device_ids.append(did)
        sensor_map[did] = {
            'power_kW': float(s.get('power_kW') or 0),
            'emission_factor': float(s.get('emission_factor') or 0),
            'meta': s
        }

    # Fetch activity entries for this company in range
    try:
        ares = client.table('sensors_activity').select('*').eq('company_id', company_id).gte('session_start', start_iso).lt('session_end', end_iso).execute()
        activities = ares.data or []
    except Exception:
        activities = []

    # Group activities by device_id
    by_device = {}
    for a in activities:
        did = a.get('device_id') or a.get('device') or (a.get('sensor_id') and str(a.get('sensor_id')))
        if not did:
            continue
        by_device.setdefault(did, []).append(a)

    total_emissions = 0.0
    summaries = []

    for did, acts in by_device.items():
        meta = sensor_map.get(did, {})
        power_kw = float(meta.get('power_kW') or 0)
        factor = float(meta.get('emission_factor') or 0)

        # Calculate energy_kwh either from explicit energy fields or by ON/OFF events
        energy_kwh = 0.0
        events = []
        for a in acts:
            # direct energy reporting
            e = None
            for k in ('energy_kwh', 'kwh', 'energy'):
                if a.get(k) is not None:
                    try:
                        e = float(a.get(k))
                    except Exception:
                        e = None
                    break
            if e is not None:
                energy_kwh += e
                continue
            # state-based events
            state = (a.get('state') or '').upper() if a.get('state') else None
            ts = a.get('timestamp') or a.get('time') or a.get('created_at')
            dt = _parse_iso(ts) if ts else None
            if state in ('ON', 'OFF') and dt:
                events.append({'ts': dt, 'state': state})

        # If we have events, compute ON durations
        events.sort(key=lambda x: x['ts'])
        on_since = None
        cycles = 0
        on_ms = 0
        for ev in events:
            if ev['state'] == 'ON':
                if on_since is None:
                    on_since = ev['ts']
            elif ev['state'] == 'OFF':
                if on_since:
                    on_ms += (ev['ts'] - on_since).total_seconds() * 1000
                    on_since = None
                    cycles += 1
        # if still ON at the end of period, assume until end_iso
        if on_since:
            end_dt = _parse_iso(end_iso)
            if end_dt:
                on_ms += (end_dt - on_since).total_seconds() * 1000

        on_hours = on_ms / (1000 * 60 * 60)
        if on_hours and power_kw:
            energy_kwh += on_hours * power_kw

        emissions_kg = energy_kwh * factor
        total_emissions += emissions_kg

        summaries.append({
            'device_id': did,
            'energy_kwh': round(energy_kwh, 6),
            'emissions_kg': round(emissions_kg, 6),
            'cycles': cycles,
            'on_hours': round(on_hours, 4),
            'meta': meta.get('meta')
        })

    return total_emissions, summaries


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

        # Try to get per-item emissions (factor + calculation) from Gemini
        llm_item_results = None
        if GEMINI_API_KEY and rows:
            try:
                # Compose a short data payload
                items_payload = [
                    {
                        'name': r.get('name'),
                        'quantity': r.get('quantity'),
                        'price': r.get('price'),
                        'unit': r.get('unit'),
                        'type': r.get('type')
                    }
                    for r in rows
                ]

                system_prompt = (
                    "You are a carbon accounting assistant. Given a list of invoice line items, for each item return a JSON object with the following fields:"
                    "\n- name: item description"
                    "\n- quantity: numeric quantity (or null)"
                    "\n- unit: the unit string (e.g., kWh, l, kg, item, kgCO2)"
                    "\n- factor: the emission factor in kg CO2e per unit (if you can infer a reasonable default), otherwise null"
                    "\n- emissions: numeric kg CO2e computed as quantity * factor when possible, otherwise null"
                    "\n- formula: a short human-readable formula explaining the calculation"
                    "\nReturn a JSON array of these objects in the same order as input. If you cannot determine a factor, set factor to null and explain in formula. Use concise numeric formats."
                )

                client_g = genai.Client(api_key=GEMINI_API_KEY)
                response = client_g.models.generate_content(
                    model='gemini-2.5-flash',
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type='application/json',
                    ),
                    contents=_json.dumps({'items': items_payload})
                )
                try:
                    import json as _py
                    llm_item_results = _py.loads(response.text)
                except Exception:
                    llm_item_results = None
            except Exception:
                llm_item_results = None

        # Load regulations to include in the report (best-effort)
        try:
            with open('backend/data/regulations.json', 'r', encoding='utf-8') as rf:
                regs = _json.load(rf)
        except Exception:
            regs = []

        # Create PDF report (import reportlab lazily to avoid heavy imports on serverless)
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
        except Exception:
            # If reportlab is not available, skip PDF generation for this run
            continue

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
        c.drawString(40, y, f"Total Emissions (sum of quantity): {total_emissions} kg CO₂e")
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
        for idx, row in enumerate(rows):
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
            # If LLM returned item-level emissions, print them below the item
            try:
                item_llm = None
                if llm_item_results and isinstance(llm_item_results, list) and idx < len(llm_item_results):
                    item_llm = llm_item_results[idx]
                # Fallback: try to match by name
                if not item_llm and llm_item_results:
                    name = row.get('name','')
                    for it in llm_item_results:
                        if isinstance(it, dict) and it.get('name') and it.get('name').strip().lower() == str(name).strip().lower():
                            item_llm = it
                            break

                if item_llm:
                    factor = item_llm.get('factor')
                    emissions = item_llm.get('emissions')
                    formula = item_llm.get('formula') or ''
                    info_line = f"  → factor: {factor if factor is not None else 'n/a'} kg CO2e/unit | emissions: {emissions if emissions is not None else 'n/a'} kg CO2e"
                    c.drawString(52, y, info_line)
                    y -= 12
                    if formula:
                        # wrap formula if long
                        fparts = [formula[i:i+100] for i in range(0, len(formula), 100)]
                        for fp in fparts:
                            c.drawString(56, y, fp)
                            y -= 12
                            if y < 60:
                                c.showPage()
                                y = height - 50
                                c.setFont("Helvetica", 9)
                else:
                    # Try to use cached official emission factors (EU sources) as a fallback
                    try:
                        unit = row.get('unit')
                        qty = row.get('quantity') if isinstance(row.get('quantity'), (int, float)) else None
                        cached = emission_factors.get_factor_for_unit(unit)
                        if cached is not None:
                            emissions = qty * cached if qty is not None else None
                            info_line = f"  → factor (official cache): {cached} kg CO2e/{unit or 'unit'} | emissions: {emissions if emissions is not None else 'n/a'} kg CO2e"
                            c.drawString(52, y, info_line)
                            y -= 12
                            formula = f"{qty} * {cached} = {emissions}" if emissions is not None else f"factor: {cached} (quantity missing)"
                            c.drawString(56, y, formula)
                            y -= 12
                    except Exception:
                        pass
                # ensure page break if near bottom
                if y < 60:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 9)
            except Exception:
                # ignore LLM rendering errors and continue
                pass
            if y < 60:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)

        # Add sensors summary (if any)
        try:
            start_iso = first_of_this_month.isoformat()
            end_iso = next_month.isoformat()
            sensor_total, sensor_summaries = compute_sensor_emissions(client, company_id, start_iso, end_iso)
            if sensor_summaries:
                c.setFont("Helvetica-Bold", 12)
                if y < 80:
                    c.showPage()
                    y = height - 50
                c.drawString(40, y, "Sensor-derived emissions")
                y -= 18
                c.setFont("Helvetica", 9)
                for s in sensor_summaries:
                    line = f"- {s.get('device_id')}: {s.get('emissions_kg')} kg CO2e ({s.get('energy_kwh')} kWh)"
                    c.drawString(44, y, line)
                    y -= 12
                    if y < 60:
                        c.showPage()
                        y = height - 50
                        c.setFont("Helvetica", 9)
                y -= 8
                c.drawString(44, y, f"Sensor total emissions: {round(sensor_total,3)} kg CO2e")
                y -= 14
        except Exception:
            pass

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
    # Only start a background scheduler when running in a non-serverless environment.
    # Vercel sets the VERCEL environment variable in its runtime; skip scheduler there.
    global scheduler
    if os.getenv('VERCEL'):
        # Do not start scheduler on Vercel (serverless)
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception:
        return
    scheduler = BackgroundScheduler()
    scheduler.add_job(generate_monthly_reports, 'cron', hour=10, minute=15)
    scheduler.start()



@app.get("/health/supabase")
async def supabase_health(client = Depends(supabase_dep)):
	# Lightweight health: confirm client is initialized and env present
	url = client.rest_url if hasattr(client, "rest_url") else None
	return {"supabase_client_initialized": True, "rest_url": url}


def sanitize_filename(name: str) -> str:
    if not name:
        return "unnamed"
    # Normalize unicode characters to closest ASCII, remove path separators
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode('ascii')
    # Keep only safe characters, replace spaces with dash
    name = name.strip().replace(' ', '-')
    name = re.sub(r"[^A-Za-z0-9._-]", '', name)
    # Prevent hidden files or leading dots
    name = name.lstrip('.')
    if not name:
        name = 'unnamed'
    return name


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

        supabase = app.state.supabase
        base_name = sanitize_filename(file.filename)
        # Append a short random suffix to avoid collisions
        suffix = secrets.token_hex(4)
        # Preserve extension if present
        p = PurePosixPath(base_name)
        stem = p.stem
        ext = p.suffix
        safe_name = f"{stem}-{suffix}{ext}"
        file_path = f"{email}/{safe_name}"
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
        # Determine quantity and convert to kg if row unit indicates tonnes of CO2
        quantity_raw = row.get("quantity")
        quantity = quantity_raw if isinstance(quantity_raw, (int, float)) else None
        # Try to convert explicit tonne-of-CO2 quantities to kg
        try:
            converted = emission_factors.convert_to_kg(quantity, row.get("unit"))
            if converted is not None:
                quantity_kg = converted
            else:
                quantity_kg = quantity
        except Exception:
            quantity_kg = quantity

        if isinstance(quantity_kg, (int, float)):
            total_emissions += quantity_kg
        # Count by type
        typ = row.get("type")
        if typ:
            item_counts[typ] = item_counts.get(typ, 0) + 1
        # Time series by day (emissions)
        created = row.get("created_at")
        if created:
            day = created[:10]  # YYYY-MM-DD
            val = quantity_kg if isinstance(quantity_kg, (int, float)) else 0
            time_series[day] = time_series.get(day, 0) + val

    # Include sensor-derived emissions for the same period
    sensor_total = 0
    sensor_summaries = []
    try:
        start_iso = first_of_this_month.isoformat()
        end_iso = next_month.isoformat()
        sensor_total, sensor_summaries = compute_sensor_emissions(client, company_id, start_iso, end_iso)
    except Exception:
        sensor_total = 0
        sensor_summaries = []

    # Compose response
    return JSONResponse(content={
        "total_emissions": total_emissions,
        "sensor_emissions": sensor_total,
        "sensor_summaries": sensor_summaries,
        "total_spend": total_spend,
        "item_counts": item_counts,
        "time_series": time_series,
        "raw": rows
    })


@app.get('/api/company-item-emissions')
async def get_company_item_emissions(company_id: int, client=Depends(supabase_dep)):
    """Return per-invoice-item emission factors/emissions computed by Gemini for the current month."""
    # Calculate date range
    today = datetime.utcnow()
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (first_of_this_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    query = (
        client.table('invoices')
        .select('*')
        .eq('company_id', company_id)
        .gte('created_at', first_of_this_month.isoformat())
        .lt('created_at', next_month.isoformat())
    )
    res = query.execute()
    if hasattr(res, 'error') and res.error:
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {res.error}")
    rows = res.data or []

    items_payload = [
        {
            'name': r.get('name'),
            'quantity': r.get('quantity'),
            'price': r.get('price'),
            'unit': r.get('unit'),
            'type': r.get('type')
        }
        for r in rows
    ]

    if GEMINI_API_KEY and items_payload:
        try:
            system_prompt = (
                'You are a carbon accounting assistant. Given a list of invoice line items, for each item return a JSON object with: name, quantity (number or null), unit (string), factor (kg CO2e per unit or null), emissions (kg CO2e or null), formula (human-readable). Return a JSON array in the same order as input.'
            )
            client_g = genai.Client(api_key=GEMINI_API_KEY)
            response = client_g.models.generate_content(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type='application/json',
                ),
                contents=_json.dumps({'items': items_payload})
            )
            import json as _py
            try:
                findings = _py.loads(response.text)
            except Exception:
                findings = None
            if findings and isinstance(findings, list):
                return JSONResponse(content={'items': findings, 'raw': rows})
        except Exception:
            # fall through to fallback
            pass

    # Fallback: return rows with null factor/emissions and a helpful message
    fallback = []
    for r in items_payload:
        # Attempt to use cached factor for unit
        unit = r.get('unit')
        qty_raw = r.get('quantity')
        qty = qty_raw if isinstance(qty_raw, (int, float)) else None
        # If unit indicates tonnes of CO2, convert to kg for emissions calculation
        qty_for_calc = qty
        try:
            converted = emission_factors.convert_to_kg(qty, unit)
            if converted is not None:
                qty_for_calc = converted
        except Exception:
            pass
        cached = emission_factors.get_factor_for_unit(unit)
        if cached is not None:
            emissions = qty_for_calc * cached if qty_for_calc is not None else None
            if qty_for_calc is not None and qty_for_calc != qty:
                formula = f"Converted {qty} {unit} -> {qty_for_calc} kg; {qty_for_calc} * {cached} = {emissions}"
            else:
                formula = f"{qty_for_calc} * {cached} = {emissions}" if emissions is not None else f"factor: {cached} (quantity missing)"
            fallback.append({
                'name': r.get('name'),
                'quantity': qty,
                'unit': unit,
                'factor': cached,
                'emissions': emissions,
                'formula': formula
            })
        else:
            fallback.append({
                'name': r.get('name'),
                'quantity': qty,
                'unit': unit,
                'factor': None,
                'emissions': None,
                'formula': 'No factor available — Gemini not configured or failed. Please map unit to factor.'
            })
    return JSONResponse(content={'items': fallback, 'raw': rows})


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


@app.get('/api/emission-factors')
async def get_emission_factors():
    """Return the cached emission factors mapping."""
    try:
        mapping = emission_factors.load_cached_factors()
        return JSONResponse(content={'factors': mapping})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/emission-factors/refresh')
async def refresh_emission_factors():
    """Refresh cached emission factors from configured sources."""
    try:
        mapping = emission_factors.refresh_cached_factors()
        return JSONResponse(content={'factors': mapping})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/sensors')
async def create_sensor(payload: dict = Body(...), client=Depends(supabase_dep)):
    """Create a sensor record in the sensors table. Expects JSON payload with keys:
    device_id, power_kW, emission_factor, last_analysis
    Associates the record with the authenticated user if an Authorization Bearer token is provided.
    """
    try:

        record = {
            'device_id': payload.get('device_id'),
            'power_kW': payload.get('power_kW'),
            'emission_factor': payload.get('emission_factor'),
            'last_analysis': payload.get('last_analysis'),
            'company_id': payload.get('company_id')
        }

        res = client.table('sensors').insert(record).execute()
        if hasattr(res, 'error') and res.error:
            raise HTTPException(status_code=500, detail=f"Failed to insert sensor: {res.error}")
        created = None
        try:
            created = res.data[0] if res.data else None
        except Exception:
            created = res.data

        return JSONResponse(content=created)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/sensors')
async def list_sensors(company_id: str, client=Depends(supabase_dep)):
    """List sensors for the authenticated owner (best-effort)."""
    try:
        res = client.table('sensors').select('*').eq('company_id', company_id).execute()
        if hasattr(res, 'error') and res.error:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sensors: {res.error}")
        rows = res.data or []
        return JSONResponse(content=rows)
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

@app.post("/api/session/start")
async def start_session(payload: dict = Body(...)):
    try:
        supabase = app.state.supabase
        device_id = payload.get('device_id')
        if not device_id:
            raise HTTPException(status_code=400, detail="device_id is required")
        id = supabase.table('sensors').select('id').eq('device_id', device_id).execute()
        if hasattr(id, 'error') and id.error:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sensor: {id.error}")
        sensor_rows = id.data or []
        if not sensor_rows:
            raise HTTPException(status_code=404, detail="Sensor not found")
        sensor_id = sensor_rows[0].get('id')
        res = supabase.table('sensors').update({'session_start': datetime.utcnow().isoformat()}).eq('id', sensor_id).select().execute()
        if hasattr(res, 'error') and res.error:
            raise HTTPException(status_code=500, detail=f"Failed to start session: {res.error}")

        return JSONResponse(content=res.data[0] if res.data else {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/end")
def end_session(payload: dict = Body(...)):
    try:
        supabase = app.state.supabase
        device_id = payload.get('device_id')
        if not device_id:
            raise HTTPException(status_code=400, detail="device_id is required")
        id = supabase.table('sensors').select('id').eq('device_id', device_id).execute()
        if hasattr(id, 'error') and id.error:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sensor: {id.error}")
        sensor_rows = id.data or []
        if not sensor_rows:
            raise HTTPException(status_code=404, detail="Sensor not found")
        sensor_id = sensor_rows[0].get('id')
        now = datetime.utcnow().isoformat()
        startTime = sensor_rows[0].get('session_start')
        if not startTime:
            raise HTTPException(status_code=400, detail="No active session to end")
        hours = (datetime.fromisoformat(now) - datetime.fromisoformat(startTime)).total_seconds() / 3600.0
        supabase.table('sensors_activity').insert({
            'device_id': sensor_id,
            'hours': hours,
            'session_start': startTime,
            'session_end': now
        }).execute()
        res = supabase.table('sensors').update({'session_start': None}).eq('id', sensor_id).select().execute()
        if hasattr(res, 'error') and res.error:
            raise HTTPException(status_code=500, detail=f"Failed to end session: {res.error}")

        return JSONResponse(content=res.data[0] if res.data else {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))