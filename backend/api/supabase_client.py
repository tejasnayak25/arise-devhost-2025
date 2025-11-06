import os
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client


_supabase_client: Optional[Client] = None


def initialize_supabase_from_env() -> Client:
	"""Initialize and cache a Supabase client using environment variables.

	Expected environment variables:
	- SUPABASE_URL
	- SUPABASE_SERVICE_ROLE_KEY (preferred) or SUPABASE_ANON_KEY
	"""
	global _supabase_client
	if _supabase_client is not None:
		return _supabase_client

	# Load variables from a local .env if present (no-op in production containers)
	load_dotenv()

	supabase_url = os.getenv("SUPABASE_URL")
	service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
	anon_key = os.getenv("SUPABASE_ANON_KEY")

	if not supabase_url:
		raise RuntimeError("SUPABASE_URL is not set")

	api_key = service_key or anon_key
	if not api_key:
		raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY must be set")

	_supabase_client = create_client(supabase_url, api_key)
	return _supabase_client


def get_supabase_client() -> Client:
	"""Accessor for the cached Supabase client."""
	if _supabase_client is None:
		return initialize_supabase_from_env()
	return _supabase_client


