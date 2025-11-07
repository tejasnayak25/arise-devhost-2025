import os
import json
import time
from typing import Dict, Optional
import requests

# Simple emission factors fetcher and cache. This module does not include
# a built-in authoritative EU source URL because official sources vary
# (EEA, JRC, national bodies). Configure the source via the
# EMISSION_FACTORS_SOURCES environment variable as a comma-separated list
# of URLs that return JSON or CSV data. Each source should provide a mapping
# of unit (string) to factor (number in kg CO2e per unit).

CACHE_PATH = os.path.join('backend', 'data', 'emission_factors.json')
DEFAULT_SOURCES = os.getenv('EMISSION_FACTORS_SOURCES', '')


def normalize_unit(u: str) -> str:
    if not u:
        return ''
    return str(u).lower().strip().replace(' ', '').replace('.', '')


def load_cached_factors() -> Dict[str, float]:
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # keys may be normalized already
                return {normalize_unit(k): float(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def save_cached_factors(mapping: Dict[str, float]):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2)
    except Exception:
        pass


def parse_json_source(text: str) -> Optional[Dict[str, float]]:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            # expect { unit: factor }
            return {normalize_unit(k): float(v) for k, v in obj.items() if _is_number(v)}
    except Exception:
        pass
    return None


def parse_csv_source(text: str) -> Optional[Dict[str, float]]:
    # very small CSV parser that looks for two columns unit, factor
    import csv
    try:
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        mapping = {}
        for r in rows:
            if len(r) < 2:
                continue
            unit = normalize_unit(r[0])
            try:
                val = float(r[1])
                mapping[unit] = val
            except Exception:
                continue
        return mapping if mapping else None
    except Exception:
        return None


def _is_number(v) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


def fetch_from_url(url: str) -> Dict[str, float]:
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            return {}
        ct = resp.headers.get('content-type', '')
        text = resp.text
        if 'application/json' in ct or text.strip().startswith('{'):
            parsed = parse_json_source(text)
            if parsed:
                return parsed
        # fallback to CSV parse
        parsed = parse_csv_source(text)
        if parsed:
            return parsed
    except Exception:
        pass
    return {}


def refresh_cached_factors() -> Dict[str, float]:
    """Fetch emission factors from configured sources and cache them locally.
    Returns the combined mapping (unit -> factor).
    """
    combined: Dict[str, float] = {}
    sources = [s.strip() for s in DEFAULT_SOURCES.split(',') if s.strip()]
    # if no sources configured, return existing cache
    if not sources:
        return load_cached_factors()

    for src in sources:
        try:
            mapping = fetch_from_url(src)
            for k, v in mapping.items():
                # prefer existing cached value if present
                if k not in combined:
                    combined[k] = v
        except Exception:
            continue

    # Save combined mapping
    if combined:
        save_cached_factors(combined)
    return load_cached_factors()

def get_factor(unit: str) -> Optional[float]:
    if not unit:
        return None
    # requests.get()


def get_factor_for_unit(unit: str) -> Optional[float]:
    if not unit:
        return None
    mapping = load_cached_factors()
    return mapping.get(normalize_unit(unit))


def convert_to_kg(quantity: Optional[float], unit: Optional[str]) -> Optional[float]:
    """If the unit explicitly represents tonnes of CO2 (or similar), convert quantity to kg.
    Returns converted kg value or None if conversion isn't applicable.
    Heuristic: if unit normalized is 't', 'tonne', 'tonnes', 'tco2', 'tco2e', treat quantity as tonnes of CO2.
    """
    try:
        if quantity is None:
            return None
        if unit is None:
            return None
        u = normalize_unit(unit)
        if u in ('t', 'tonne', 'tonnes', 'tco2', 'tco2e'):
            return float(quantity) * 1000.0
    except Exception:
        pass
    return None
