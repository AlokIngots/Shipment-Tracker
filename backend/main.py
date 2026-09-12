"""Alok Ingots Customer Portal — API entry point.

This file does one thing: build the app and hand it its routers. Everything
else lives under app/ — see backend/README.md for the code map.

The portal has two halves and they are separated here, in the routing, not
only in the screens:

  * The customer half (auth, orders, documents) is read-only. It has no
    POST, PUT or DELETE except the one that changes your own password.
  * The admin half, everything under /api/staff, is where data is written,
    and every route in it depends on StaffUser.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import auth, documents, orders, photos
from app.routers.admin import accounts as admin_accounts
from app.routers.admin import activity as admin_activity
from app.routers.admin import documents as admin_documents
from app.routers.admin import notifications as admin_notifications
from app.routers.admin import orders as admin_orders
from app.routers.admin import photos as admin_photos
from app.routers.admin import shipments as admin_shipments
from app.services import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """What runs for as long as the API does.

    One thing so far: the timer that sends customers their notifications
    without anybody having to remember to. NOTIFY_EVERY_MINUTES=0 turns it
    off, and then the only ways to send are the Send now button and
    `python -m scripts.notify`.
    """
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(
    title="Alok Ingots Customer Portal API",
    description="Backend API for the Alok Ingots export customer portal.",
    version="0.5.0",
    lifespan=lifespan,
)

# The customer portal: read-only.
app.include_router(auth.router, tags=["auth"])
app.include_router(orders.router, tags=["customer"])
app.include_router(documents.router, tags=["customer"])
app.include_router(photos.router, tags=["customer"])

# The admin console: the only place anything is written.
app.include_router(admin_accounts.router, tags=["admin"])
app.include_router(admin_orders.router, tags=["admin"])
app.include_router(admin_shipments.router, tags=["admin"])
app.include_router(admin_documents.router, tags=["admin"])
app.include_router(admin_photos.router, tags=["admin"])
app.include_router(admin_activity.router, tags=["admin"])
app.include_router(admin_notifications.router, tags=["admin"])
