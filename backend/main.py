from fastapi import Depends, FastAPI

from backend.api.supabase_client import (
	get_supabase_client,
	initialize_supabase_from_env,
)

app = FastAPI()


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

