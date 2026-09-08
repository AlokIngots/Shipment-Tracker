"""Alok Ingots Customer Portal — FastAPI backend.

Minimal entry point. Only the health check route exists so far.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Alok Ingots Customer Portal API",
    description="Backend API for the Alok Ingots export customer portal.",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe used to confirm the API is up."""
    return {"status": "ok"}
