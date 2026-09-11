"""The shapes that cross the wire, in and out.

    auth.py    signing in, and saying who you are
    orders.py  what a customer is sent
    admin.py   what the admin console is sent, and submits back

Nothing here touches the database or decides anything. These classes exist
so that what the API promises is written down: add a column to a model and
no customer sees it until it also appears here, which is the point.
"""

from app.schemas.admin import (
    ActiveIn,
    CustomerEditIn,
    CustomerIn,
    LoginIn,
    OrderIn,
    ShipmentIn,
    StaffCustomerOut,
    StaffDocumentOut,
    StaffOrderOut,
    StaffOrderShipmentOut,
    StaffPhotoOut,
    StaffAccountsOut,
    StaffActivityChangeOut,
    StaffActivityEventOut,
    StaffActivityOut,
    StaffCustomerAccountOut,
    StaffLoginOut,
    StaffShipmentOut,
    StaffShipmentPhotosOut,
    TemporaryPasswordOut,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    CustomerOut,
    LoginRequest,
    LoginResponse,
    MagicLinkRedeem,
    MagicLinkRequest,
)
from app.schemas.orders import (
    DocumentOut,
    OrderDetailOut,
    OrderOut,
    PhotoOut,
    ShipmentOut,
)

__all__ = [
    "TemporaryPasswordOut",
    "StaffLoginOut",
    "StaffCustomerAccountOut",
    "StaffAccountsOut",
    "StaffActivityChangeOut",
    "StaffActivityEventOut",
    "StaffActivityOut",
    "LoginIn",
    "CustomerIn",
    "CustomerEditIn",
    "ActiveIn",
    "ChangePasswordRequest",
    "CustomerOut",
    "DocumentOut",
    "LoginRequest",
    "LoginResponse",
    "MagicLinkRedeem",
    "MagicLinkRequest",
    "OrderDetailOut",
    "OrderIn",
    "OrderOut",
    "PhotoOut",
    "ShipmentIn",
    "ShipmentOut",
    "StaffCustomerOut",
    "StaffDocumentOut",
    "StaffOrderOut",
    "StaffOrderShipmentOut",
    "StaffPhotoOut",
    "StaffShipmentOut",
    "StaffShipmentPhotosOut",
]
