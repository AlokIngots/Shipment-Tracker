"""The shapes that cross the wire, in and out.

    auth.py    signing in, and saying who you are
    orders.py  what a customer is sent
    admin.py   what the admin console is sent, and submits back

Nothing here touches the database or decides anything. These classes exist
so that what the API promises is written down: add a column to a model and
no customer sees it until it also appears here, which is the point.
"""

from app.schemas.admin import (
    OrderIn,
    ShipmentIn,
    StaffCustomerOut,
    StaffDocumentOut,
    StaffOrderOut,
    StaffOrderShipmentOut,
    StaffShipmentOut,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    CustomerOut,
    LoginRequest,
    LoginResponse,
)
from app.schemas.orders import DocumentOut, OrderDetailOut, OrderOut, ShipmentOut

__all__ = [
    "ChangePasswordRequest",
    "CustomerOut",
    "DocumentOut",
    "LoginRequest",
    "LoginResponse",
    "OrderDetailOut",
    "OrderIn",
    "OrderOut",
    "ShipmentIn",
    "ShipmentOut",
    "StaffCustomerOut",
    "StaffDocumentOut",
    "StaffOrderOut",
    "StaffOrderShipmentOut",
    "StaffShipmentOut",
]
