"""Alok Ingots Customer Portal — FastAPI backend.

This file does one thing: build the app and hand it the four routers. The
routes themselves live in routers/, the shapes they exchange in schemas.py,
and the rules about who may call what in deps.py.

Every customer-facing route scopes on the customer taken from the sign-in
token, never on anything in the request, so a signed-in user can only ever
read their own orders.
"""

from fastapi import FastAPI
from routers import auth, orders, staff_documents, staff_orders

app = FastAPI(
    title="Alok Ingots Customer Portal API",
    description="Backend API for the Alok Ingots export customer portal.",
    version="0.3.0",
)

app.include_router(auth.router, tags=["auth"])
app.include_router(orders.router, tags=["customer"])
app.include_router(staff_orders.router, tags=["staff"])
app.include_router(staff_documents.router, tags=["staff"])
