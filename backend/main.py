# --- New endpoint: Get last month's invoice data for dashboard ---
from datetime import datetime, timedelta, timezone
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
from apscheduler.schedulers.background import BackgroundScheduler
import logging
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
scheduler = BackgroundScheduler()
logger = logging.getLogger(__name__)



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


def _parse_iso(ts: str):
    """Robustly parse many date/time formats into a naive UTC datetime.

    Accepts:
    - ISO 8601 strings (with or without Z)
    - Month name + year (e.g., 'February 2025' -> 2025-02-01)
    - Common variants like 'Feb 3, 2025', '2025-02', '02/2025', '20250203'
    - Epoch seconds (10 or 13 digit)
    - Uses python-dateutil if available for flexible parsing

    Returns a datetime (naive, UTC) or None on failure.
    """
    if not ts:
        return None

    # If already a datetime or date
    try:
        if isinstance(ts, datetime):
            dt = ts
            # convert aware -> UTC naive
            if getattr(dt, 'tzinfo', None):
                try:
                    dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                except Exception:
                    dt = dt.replace(tzinfo=None)
            return dt
        # support date objects
        from datetime import date as _date
        if isinstance(ts, _date):
            return datetime(ts.year, ts.month, ts.day)
    except Exception:
        pass

    s = str(ts).strip()
    if not s:
        return None

    # Normalize common Z suffix
    if s.endswith('Z'):
        s = s.replace('Z', '+00:00')

    # 1) Try fromisoformat (fast path)
    try:
        dt = datetime.fromisoformat(s)
        if getattr(dt, 'tzinfo', None):
            try:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            except Exception:
                dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        pass

    # 2) Try python-dateutil if available (very flexible)
    try:
        from dateutil import parser as _du_parser
        try:
            # fuzzy parsing helps with extraneous text like 'Invoice date: February 2025'
            dt = _du_parser.parse(s, fuzzy=True)
            if getattr(dt, 'tzinfo', None):
                try:
                    dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                except Exception:
                    dt = dt.replace(tzinfo=None)
            return dt
        except Exception:
            pass
    except Exception:
        # dateutil not installed; continue to fallback heuristics
        pass

    # 3) Numeric epoch (10 or 13 digits)
    if re.fullmatch(r"\d{10}(?:\d{3})?", s):
        try:
            iv = int(s)
            if len(s) == 13:
                iv = iv / 1000.0
            dt = datetime.utcfromtimestamp(iv)
            return dt
        except Exception:
            pass

    # 4) Try a list of common strptime formats
    formats = [
        '%B %Y',        # February 2025
        '%b %Y',        # Feb 2025
        '%B %d, %Y',    # February 3, 2025
        '%b %d, %Y',    # Feb 3, 2025
        '%Y-%m',        # 2025-02
        '%Y/%m',        # 2025/02
        '%m/%Y',        # 02/2025
        '%m-%Y',        # 02-2025
        '%Y-%m-%d',     # 2025-02-03
        '%d/%m/%Y',     # 03/02/2025
        '%d-%m-%Y',     # 03-02-2025
        '%Y.%m.%d',     # 2025.02.03
        '%Y%m%d',       # 20250203
        '%m%d%Y',       # 02032025
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt
        except Exception:
            continue

    # 5) Heuristics: Month name + year using regex
    m = re.search(r'([A-Za-z]+)\s+(\d{4})', s)
    if m:
        month_name = m.group(1)
        year = int(m.group(2))
        try:
            # try abbreviated month first
            month = datetime.strptime(month_name[:3], '%b').month
        except Exception:
            try:
                month = datetime.strptime(month_name, '%B').month
            except Exception:
                month = None
        if month:
            return datetime(year, month, 1)

    # 6) mm/yyyy or yyyy
    m2 = re.search(r'(\d{1,2})[\-/](\d{4})', s)
    if m2:
        mth = int(m2.group(1))
        yr = int(m2.group(2))
        if 1 <= mth <= 12:
            return datetime(yr, mth, 1)
        system_prompt = (
            "You are an expert in sustainability and carbon accounting and invoice parsing. "
            "From the following raw invoice text, extract ALL line items and return a JSON array of objects. For each item include the fields:\n"
            "- name (string)\n"
            "- quantity (number or null)\n"
            "- price (number or null)\n"
            "- unit (string or null; use 'item' when not applicable)\n"
            "- type (string or null)\n"
            "- date (string or null)\n"
            "Additionally, for each item determine whether it represents a net-negative carbon resource (a \"positive\" resource) and include classification fields:\n"
            "- is_positive (boolean) -- true when this item is a carbon removal or negative-emission resource\n"
            "- confidence (number between 0 and 1) -- your confidence in the classification\n"
            "- reason (short string) -- brief explanation for the classification decision\n"
            "Return ONLY a JSON array (no extra text). Preserve the input ordering. Be conservative when labeling items as positive; when unsure, set is_positive=false and confidence below 0.6."
        )
def compute_sensor_emissions(client, company_id, start_iso, end_iso):
    """Compute sensor-derived emissions for a company between start_iso and end_iso.

    Returns: (total_emissions_kg: float, summaries: list)
    """
    # Fetch sensors tied to company_id
    try:
        sres = client.table('sensors').select('*').eq('company_id', company_id).execute()
        sensors = sres.data or []
    except Exception:
        sensors = []

    if not sensors:
        return 0.0, []

    # Build a mapping from all possible device identifiers to sensor metadata.
    sensor_map = {}
    device_keys = set()
    for s in sensors:
        sid = s.get('id')
        ext_did = s.get('device_id')
        meta = {
            'id': sid,
            'device_id': ext_did,
            'power_kW': float(s.get('power_kW') or 0),
            'emission_factor': float(s.get('emission_factor') or 0),
            'meta': s
        }
        if sid is not None:
            # Map the primary key (e.g., 123) -> meta
            sensor_map[sid] = meta
            device_keys.add(sid)
        if ext_did is not None:
            # Map the external ID (e.g., 'abc-xyz') -> meta
            sensor_map[ext_did] = meta
            device_keys.add(ext_did)

    # Query activity rows for the sensors we just fetched.
    activities = []
    try:
        if device_keys:
            dev_list = list(device_keys)
            a_query = client.table('sensors_activity').select('*').in_('device_id', dev_list)
        else:
            # This case shouldn't be hit if we have sensors, but as a fallback
            a_query = client.table('sensors_activity').select('*')

        # **FIXED**: Correctly filter for an *overlapping* time window:
        # A session overlaps if it starts *before* the end_iso
        # AND ends *after* the start_iso.
        try:
            a_query = a_query.lt('session_start', end_iso).gte('session_end', start_iso)
            ares = a_query.execute()
            activities = ares.data or []
        except Exception:
            # Fallback if chained filters fail: fetch by device_id only and filter in Python
            ares = client.table('sensors_activity').select('*').in_('device_id', dev_list).execute()
            py_activities = ares.data or []
            
            # Manual time filtering
            start_dt = _parse_iso(start_iso)
            end_dt = _parse_iso(end_iso)
            if start_dt and end_dt:
                for a in py_activities:
                    ss = _parse_iso(a.get('session_start'))
                    se = _parse_iso(a.get('session_end'))
                    if ss and se and ss < end_dt and se >= start_dt:
                        activities.append(a)
            else:
                # If time parsing fails, just use all activities (less accurate)
                activities = py_activities
            
    except Exception:
        activities = [] # Failed to get any activities

    # **FIXED**: Group activities by the *canonical sensor ID* to avoid double counting
    by_canonical_id = {}
    for a in activities:
        # Find the device identifier in the activity row
        did = a.get('device_id') or a.get('sensor_id') or a.get('device') or a.get('deviceId')
        if did is None:
            continue
        
        # Find the canonical sensor metadata using the map
        meta = sensor_map.get(did)
        if not meta:
            # Activity for a sensor we don't own or don't know about
            continue
            
        # Group by the sensor's primary key (e.g., 'id' from sensors table)
        canonical_id = meta['id']
        by_canonical_id.setdefault(canonical_id, []).append(a)

    total_emissions = 0.0
    summaries = []

    # **FIXED**: Reworked entire energy calculation logic
    for canonical_id, acts in by_canonical_id.items():
        # Get the metadata for this canonical sensor
        meta = sensor_map.get(canonical_id)
        if not meta:
            continue # Should be impossible, but good to check

        power_kw = float(meta.get('power_kW') or 0)
        factor = float(meta.get('emission_factor') or 0)

        energy_kwh = 0.0
        cycles = 0
        on_hours = 0.0

        explicit_energy_acts = []
        duration_acts = []
        event_acts = []

        # --- 1. Classify all activities for this sensor ---
        for a in acts:
            # Check for explicit energy (Method A)
            has_explicit_kwh = False
            for k in ('energy_kwh', 'kwh', 'energy'):
                if a.get(k) is not None:
                    explicit_energy_acts.append(a)
                    has_explicit_kwh = True
                    break
            if has_explicit_kwh:
                continue # This row is classified, move to next row

            # Check for duration-based (Method B)
            if a.get('hours') is not None:
                duration_acts.append(a)
                continue
            ss = a.get('session_start') or a.get('start') or a.get('timestamp')
            se = a.get('session_end') or a.get('end')
            if ss and se:
                duration_acts.append(a)
                continue
                
            # Check for state-based (Method C)
            state = (a.get('state') or '').upper() if a.get('state') else None
            ts = a.get('timestamp') or a.get('time') or a.get('created_at')
            if state in ('ON', 'OFF') and ts:
                event_acts.append(a)

        # --- 2. Process based on preference: Explicit (A) > Duration (B) > Events (C) ---
        
        if explicit_energy_acts:
            # Method A: Use explicit energy reports
            for a in explicit_energy_acts:
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
            cycles = len(explicit_energy_acts)
            # We can't reliably know on_hours from this data model
        
        elif duration_acts:
            # Method B: Use duration * power
            for a in duration_acts:
                hrs = None
                if a.get('hours') is not None:
                    try:
                        hrs = float(a.get('hours'))
                    except Exception:
                        hrs = None
                
                if hrs is None:
                    # 'ss' and 'se' must exist from classification logic
                    ss = a.get('session_start') or a.get('start') or a.get('timestamp')
                    se = a.get('session_end') or a.get('end')
                    try:
                        s_dt = _parse_iso(ss)
                        e_dt = _parse_iso(se)
                        if s_dt and e_dt and e_dt > s_dt:
                            # Clamp duration to the query window
                            s_dt_clamped = max(s_dt, _parse_iso(start_iso))
                            e_dt_clamped = min(e_dt, _parse_iso(end_iso))
                            if e_dt_clamped > s_dt_clamped:
                                hrs = (e_dt_clamped - s_dt_clamped).total_seconds() / 3600.0
                            else:
                                hrs = 0.0
                    except Exception:
                        hrs = None

                if hrs is not None:
                    cycles += 1
                    on_hours += hrs
                    if power_kw > 0:
                        energy_kwh += hrs * power_kw
        
        elif event_acts and power_kw > 0:
            # Method C: Use ON/OFF state events
            events = []
            for a in event_acts:
                state = (a.get('state') or '').upper()
                ts = a.get('timestamp') or a.get('time') or a.get('created_at')
                dt = _parse_iso(ts)
                if dt:
                    events.append({'ts': dt, 'state': state})
            
            if events:
                events.sort(key=lambda x: x['ts'])
                on_since = None
                ev_on_seconds = 0
                ev_cycles = 0
                
                start_dt = _parse_iso(start_iso)
                end_dt = _parse_iso(end_iso)

                for ev in events:
                    # Ignore events outside our window
                    if ev['ts'] < start_dt or ev['ts'] > end_dt:
                        continue
                        
                    if ev['state'] == 'ON':
                        if on_since is None:
                            on_since = ev['ts']
                    elif ev['state'] == 'OFF':
                        if on_since:
                            # Clamp event duration to our window
                            start_clamp = max(on_since, start_dt)
                            end_clamp = min(ev['ts'], end_dt)
                            if end_clamp > start_clamp:
                                ev_on_seconds += (end_clamp - start_clamp).total_seconds()
                            on_since = None
                            ev_cycles += 1
                
                # If it was left ON at the end of the period, cap it at 'end_iso'
                if on_since:
                    start_clamp = max(on_since, start_dt)
                    end_clamp = end_dt
                    if end_clamp > start_clamp:
                         ev_on_seconds += (end_clamp - start_clamp).total_seconds()

                ev_hours = ev_on_seconds / 3600.0
                if ev_hours > 0:
                    energy_kwh = ev_hours * power_kw # Use = not +=
                    cycles = ev_cycles
                    on_hours = ev_hours

        # --- 3. Calculate emissions and append summary ---
        emissions_kg = energy_kwh * factor
        total_emissions += emissions_kg

        summaries.append({
            'sensor_id': meta.get('id'), # The canonical internal ID
            'device_id': meta.get('device_id'), # The external/user-facing ID
            'energy_kwh': round(energy_kwh, 6),
            'emissions_kg': round(emissions_kg, 6),
            'cycles': cycles,
            'on_hours': round(on_hours, 4),
            'meta': meta.get('meta')
        })

    return round(total_emissions, 6), summaries

def generate_monthly_reports():
    """Generate a markdown report per company for the current month and upload to storage."""
    client = app.state.supabase
    print("Generating monthly reports...")
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
        total_spend = 0
        total_emissions = 0
        # When an invoice line item has is_positive=True it represents a net-negative resource
        # and should reduce overall emissions (subtract from totals). We still count spend
        # as positive (money out), but emissions are negated for positive items.
        for row in rows:
            # accumulate spend
            price = row.get("price")
            if isinstance(price, (int, float)):
                total_spend += price

            # handle quantity/emissions: negate when is_positive True
            qty = row.get("quantity")
            if isinstance(qty, (int, float)):
                try:
                    # some rows may specify units like 'tonne CO2' -- try converting
                    converted = emission_factors.convert_to_kg(qty, row.get('unit'))
                    qty_val = converted if converted is not None else qty
                except Exception:
                    qty_val = qty

                if row.get('is_positive'):
                    total_emissions -= qty_val
                else:
                    total_emissions += qty_val
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

        print(f"Uploaded report for company {company_id} to {filename}")


@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(generate_monthly_reports, 'cron', day=1, hour=0, minute=0)
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
async def upload_file(file: UploadFile = File(...), company_id: int = Form(...)):
    """
    Upload and process a file.
    - If CSV: parses and returns structured data
    - If other format (PDF, images): uses OCR to extract text
    - Saves the file to Supabase storage under /{company_id}/{filename}
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
        file_path = f"{company_id}/{safe_name}"
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
async def get_files(company_id: int, client = Depends(supabase_dep)):
    try:
        response = client.storage.from_("Default Bucket").list(company_id, {"limit": 100, "offset": 0})

        files = [
            {
                "id": file.get("id"),
                "name": file.get("name"),
                "created_at": file.get("created_at"),
				"size": file.get("metadata").get("size"),
                "date": file.get("date"),
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
    date: str | None = Field(default=None)
    is_positive: bool | None = Field(default=None)
    confidence: float | None = Field(default=None)
    reason: str | None = Field(default=None)

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
        """
        You are an expert in sustainability and carbon accounting. From the invoice text, extract all line items and return them as a JSON array. Each object must have the following fields: name, quantity, price, unit, type, date, is_positive, confidence, reason.
        name is the item description, quantity is a number, price is a number, unit is the measurement unit or item if none, type is the category such as energy, material, or service, date is the invoice date.
        is_positive is true if the item reduces or removes carbon emissions, false if it produces or increases emissions. Do not confuse this with financial payment direction. Be conservative when assigning true.
        confidence is a number between 0 and 1 showing how sure you are. reason is a short explanation of why the item is positive or not.
        Only return the JSON array with all items. No extra text.
        """
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
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
                company_id = payload.get('company_id')
                storage_path = payload.get('storage_path')
                if company_id and any(row.get(f) is not None for f in ("quantity", "price", "unit", "type", "name")):
                    # Normalize date: accept single dates or ranges like '01 Feb 2025- 28 Feb 2025'
                    raw_date = row.get('date') or row.get('invoice_date')
                    date_str = datetime.utcnow().date().isoformat()
                    try:
                        if raw_date:
                            s = str(raw_date).strip()
                            # If it's a range like '01 Feb 2025- 28 Feb 2025', split and take the first part
                            parts = re.split(r"\s*[-–—]\s*", s)
                            first = parts[0] if parts and parts[0] else s
                            dt = _parse_iso(first)
                            if dt:
                                date_str = dt.date().isoformat()
                    except Exception:
                        # fallback to today's date
                        date_str = datetime.utcnow().date().isoformat()
                    to_insert.append({
                        "name": row.get("name", None),
                        "quantity": row.get("quantity", None),
                        "price": row.get("price", None),
                        "unit": row.get("unit", None),
                        "type": row.get("type", None),
                        "date": date_str,
                        "company_id": company_id,
                        "invoice_path": storage_path,
                        "is_positive": row.get("is_positive", None),
                        "confidence": row.get("confidence", None),
                        "reason": row.get("reason", None),
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
            # If this invoice line is marked as a net-negative (is_positive), it reduces
            # the company's footprint so subtract it; otherwise add it.
            if row.get('is_positive'):
                total_emissions -= quantity_kg
            else:
                total_emissions += quantity_kg
        # Count by type
        typ = row.get("type")
        if typ:
            item_counts[typ] = item_counts.get(typ, 0) + 1
        # Time series by day (emissions)
        created = row.get("date")
        if created:
            day = created[:10]  # YYYY-MM-DD
            val = quantity_kg if isinstance(quantity_kg, (int, float)) else 0
            if row.get('is_positive'):
                time_series[day] = time_series.get(day, 0) - val
            else:
                time_series[day] = time_series.get(day, 0) + val

    # Include sensor-derived emissions for the same period
    sensor_total = 0
    sensor_summaries = []
    try:
        start_iso = first_of_this_month.isoformat()
        end_iso = next_month.isoformat()
        sensor_total, sensor_summaries = compute_sensor_emissions(client, company_id, start_iso, end_iso)
    except Exception as e:
        sensor_total = 0
        sensor_summaries = []

    sensor_count = len(sensor_summaries)

    # Compose response
    return JSONResponse(content={
        "total_emissions": total_emissions,
        "sensor_emissions": sensor_total,
        "sensor_summaries": sensor_summaries,
        "sensor_count": sensor_count,
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
            'type': r.get('type'),
            'is_positive': r.get('is_positive')
        }
        for r in rows
    ]

    if GEMINI_API_KEY and items_payload:
        try:
            system_prompt = (
                'You are a carbon accounting assistant. Given a list of invoice line items, for each item return a JSON object with: name, quantity (number or null), unit (string), factor (kg CO2e per unit or null), emissions (kg CO2e or null), formula (human-readable), is_positive. Return a JSON array in the same order as input.'
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
            # If the original invoice line was a net-negative (is_positive), make emissions negative
            if r.get('is_positive') and emissions is not None:
                emissions = -abs(emissions)
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
                'formula': formula,
                'is_positive': r.get('is_positive')
            })
        else:
            fallback.append({
                'name': r.get('name'),
                'quantity': qty,
                'unit': unit,
                'factor': None,
                'emissions': None,
                'formula': 'No factor available — Gemini not configured or failed. Please map unit to factor.',
                'is_positive': r.get('is_positive')
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


@app.post('/api/files/remove')
async def remove_file_source(payload: dict = Body(...), client=Depends(supabase_dep)):
    """Remove an invoice record and its associated file from storage.
    Expects JSON payload with: { invoice_id: int, company_id: int, invoice_path: str }
    The invoice deletion is scoped by company_id. File removal is best-effort.
    Returns JSON { deleted_invoice: <row or null>, removed_storage: bool }
    """
    try:
        company_id = payload.get('company_id')
        invoice_path = payload.get('invoice_path')

        if not company_id:
            raise HTTPException(status_code=400, detail='company_id is required')

        # Delete the invoice record (scoped by company)
        try:
            del_q = client.table('invoices').delete().eq('invoice_path', invoice_path).eq('company_id', company_id)
            del_res = del_q.execute()
            if hasattr(del_res, 'error') and del_res.error:
                raise HTTPException(status_code=500, detail=f"Failed to delete invoice: {del_res.error}")
            deleted_invoice = None
            try:
                deleted_invoice = del_res.data[0] if del_res.data else None
            except Exception:
                deleted_invoice = None
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail=str(e))

        removed_storage = False
        # Remove file from storage if invoice_path provided
        if invoice_path:
            try:
                # Attempt to remove the object. Wrap in try/except for best-effort.
                client.storage.from_("Default Bucket").remove([invoice_path])
                removed_storage = True
            except Exception:
                removed_storage = False

        return JSONResponse(content={
            'deleted_invoice': deleted_invoice,
            'removed_storage': removed_storage
        })

    except HTTPException:
        raise
    except Exception as e:
        print(e)
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


@app.post('/api/sensors/remove')
async def remove_sensor(payload: dict = Body(...), client=Depends(supabase_dep)):
    print("remove_sensor payload:", payload)
    try:
        device_id = payload.get('device_id')
        company_id = payload.get('company_id')

        if not device_id:
            raise HTTPException(status_code=400, detail='device_id is required')

        # Lookup the sensor by external device_id (and optional company_id)
        q = client.table('sensors').select('*').eq('device_id', device_id)
        if company_id:
            q = q.eq('company_id', company_id)
        res = q.execute()
        if hasattr(res, 'error') and res.error:
            raise HTTPException(status_code=500, detail=f"Failed to lookup sensor: {res.error}")
        rows = res.data or []
        if not rows:
            raise HTTPException(status_code=404, detail='Sensor not found')
        sensor = rows[0]

        # Delete related activity rows first (match by device_id)
        deleted_activity_count = 0
        try:
            da = client.table('sensors_activity').delete().eq('device_id', device_id).execute()
            if not (hasattr(da, 'error') and da.error):
                try:
                    deleted_activity_count = len(da.data) if da.data else 0
                except Exception:
                    deleted_activity_count = 0
        except Exception:
            # best-effort: continue to delete sensor even if activity deletion fails
            deleted_activity_count = 0

        # Finally delete the sensor record (scoped by company_id if provided)
        try:
            del_q = client.table('sensors').delete().eq('device_id', device_id)
            if company_id:
                del_q = del_q.eq('company_id', company_id)
            del_res = del_q.execute()
            if hasattr(del_res, 'error') and del_res.error:
                raise HTTPException(status_code=500, detail=f"Failed to delete sensor: {del_res.error}")
            deleted_sensor = None
            try:
                deleted_sensor = del_res.data[0] if del_res.data else None
            except Exception:
                deleted_sensor = None
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse(content={
            'deleted_sensor': deleted_sensor,
            'deleted_activity_count': deleted_activity_count
        })

    except HTTPException:
        raise
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
    
