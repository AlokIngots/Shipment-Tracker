"""The API endpoints, grouped by feature.

    auth.py       signing in, /api/me, changing your own password
    orders.py     a customer reading their own orders          (read-only)
    documents.py  a customer downloading their own documents   (read-only)
    photos.py     a customer viewing their own material photos (read-only)
    admin/        everything that writes, staff only

Reserved for features not built yet, so they land in the right place:
tracking.py (if tracking ever becomes its own endpoint rather than a field
on a shipment), notifications.py (if sending ever moves from a script to an
endpoint).
"""
