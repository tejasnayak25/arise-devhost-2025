from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, Form, Body
from fastapi.responses import JSONResponse
import os
import requests
from google import genai
from google.genai import types

from backend.api.file_processor import process_uploaded_file
from backend.api.supabase_client import (
	get_supabase_client,
	initialize_supabase_from_env,
)

app = FastAPI()

GEMINI_API_KEY = os.getenv("GOOGLE_AI_API")


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

	try:
		# Process the file
		result = await process_uploaded_file(file)

		# Save the file to Supabase storage
		supabase = app.state.supabase
		file_content = await file.read()
		file_path = f"{email}/{file.filename}"
		response = supabase.storage.from_("Default Bucket").upload(file_path, file_content)

		if not response:
			raise HTTPException(status_code=500, detail=f"Error saving file to storage: {response['error']['message']}")

		result["storage_path"] = file_path
		return JSONResponse(content=result)

	except Exception as e:
		raise HTTPException(
			status_code=e['statusCode'],
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


@app.post("/api/parse-invoice")
async def parse_invoice(text):
    """
    Parse invoice data using Gemini 2.5 Flash model and return carbon emission data as JSON.
    Input: plain text (invoice)
    Output: JSON with carbon emission data
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured.")

    system_prompt = (
        "You are an expert in sustainability and carbon accounting. "
        "Parse the following invoice text and extract all relevant carbon emission data, "
        "such as emission source, amount, units, date, and any other useful fields. "
        "Return the result as a structured JSON array of objects, one per emission line item, "
        "with fields: source, emission_amount, emission_unit, date, and any other relevant details. "
        "If no emission data is found, return an empty array."
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
        		system_instruction=system_prompt
            ),
            contents=[
                {"role": "user", "parts": [{"text": text}]}
            ]
        )
        model_text = response.text
        import json as pyjson
        try:
            result = pyjson.loads(model_text)
        except Exception:
            result = {"raw_output": model_text}
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")