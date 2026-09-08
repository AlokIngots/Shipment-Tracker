"""Alok Ingots Customer Portal — FastAPI backend.

Read-only endpoints for now: a health probe and the order list.
"""

from decimal import Decimal
from typing import Annotated, Iterator

from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Order

app = FastAPI(
    title="Alok Ingots Customer Portal API",
    description="Backend API for the Alok Ingots export customer portal.",
    version="0.1.0",
)


def get_db() -> Iterator[Session]:
    """Yield a database session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


class OrderOut(BaseModel):
    """An order as returned to the portal frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sales_order_no: str
    customer_po: str | None
    grade: str | None
    description: str | None
    ordered_qty: Decimal | None
    unit: str | None
    status: str | None


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe used to confirm the API is up."""
    return {"status": "ok"}


@app.get("/api/orders", response_model=list[OrderOut])
def list_orders(db: DbSession) -> list[Order]:
    """Return every order in the system, in insertion order."""
    return list(db.scalars(select(Order).order_by(Order.id)))
