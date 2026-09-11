"""The database tables, one file per thing the business talks about.

    customer.py      Customer, User
    order.py         Order, Shipment
    document.py      Document
    photo.py         Photo
    notification.py  Notification
    audit.py         AuditEvent

Everything is re-exported here, so the rest of the app writes
``from app.models import Order`` and never has to know which file it is in.
Importing this package also registers every table on ``Base.metadata``,
which is what lets Alembic see them all.
"""

from app.models.audit import AuditEvent
from app.models.customer import Customer, User
from app.models.document import Document
from app.models.notification import Notification
from app.models.order import Order, Shipment
from app.models.photo import Photo

__all__ = [
    "AuditEvent", "Customer", "Document", "Notification", "Order", "Photo", "Shipment",
]
