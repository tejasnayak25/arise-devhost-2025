# Vercel Python Serverless entrypoint for FastAPI
# Exposes the ASGI app for Vercel to serve at /api/*

from backend.main import app  # noqa: F401

