"""Load real order and shipment data into the portal from a CSV file.

This is the bridge from SAP/PMS. Whatever those systems can export, the job
is to map it into the CSV described below; nothing else in the portal needs
to change.

    python import_data.py orders.csv --dry-run   # check the file, change nothing
    python import_data.py orders.csv             # apply it

Safe to run repeatedly. Rows are matched on sales_order_no and shipment_no,
so re-importing an updated export refreshes the existing rows rather than
creating duplicates. Nothing is ever deleted.

A file never makes a correction. A row that would move a shipment back down
the status sequence -- Delivered to Packed, say -- stops the whole import and
nothing is saved, because an export that goes backwards is far more likely
to be a stale file than a decision. Corrections are made on the staff screen.

CSV columns
-----------
One row per shipment. An order with no shipments yet gets one row with the
shipment columns left blank. Order fields repeat on every row of that order.

    customer_code       required   matches customers.code, e.g. CUST-001
    customer_name       required on the first row for a new customer
    customer_country    optional
    sales_order_no      required   e.g. AIMPL/SO/EXP/163/2025-26
    customer_po         optional
    grade               optional   e.g. 431 / 1.4057
    description         optional
    ordered_qty         required   decimal, e.g. 583.000
    unit                optional   defaults to MT
    order_status        optional   blank, or Cancelled to cancel the order.
                                   Nothing else: an order's status is worked
                                   out from its shipments. A blank never takes
                                   an order back out of Cancelled
    shipment_no         blank if nothing has shipped yet
    dispatched_qty      required when shipment_no is given
    shipment_status     optional   one of: In production, Packed, Shipped,
                                   In transit, Delivered, Cancelled
    last_shipment       optional   yes on the order's last shipment, or no.
                                   Blank leaves it as it is, so a tick made on
                                   the staff screen survives the next import
    vessel_name         optional
    imo_number          optional   7 digits, checksum validated
    container_no        optional   ISO 6346, e.g. MSCU1234566, check digit validated
    bl_number           optional   the carrier's Bill of Lading number, any format
    etd                 optional   YYYY-MM-DD
    eta                 optional   YYYY-MM-DD

A template lives in docs/import-template.csv.
"""

import argparse
import csv
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.core.database import SessionLocal
from app.models import Customer, Order, Shipment
from sqlalchemy import select
from app.services import audit, statuses
from app.services.tracking import tidy_container_no, valid_container_no, valid_imo

REQUIRED_COLUMNS = [
    "customer_code",
    "sales_order_no",
    "ordered_qty",
]

ALL_COLUMNS = [
    "customer_code", "customer_name", "customer_country",
    "sales_order_no", "customer_po", "grade", "description",
    "ordered_qty", "unit", "order_status",
    "shipment_no", "dispatched_qty", "shipment_status", "last_shipment",
    "vessel_name", "imo_number", "container_no", "bl_number", "etd", "eta",
]

YES = {"yes", "y", "true", "1", "x"}
NO = {"no", "n", "false", "0"}


# ----------------------------------------------------------------- checking

# valid_imo lives in tracking.py so the importer and the API agree on what
# counts as a usable IMO number.


def parse_decimal(value: str, field: str, errors: list[str]) -> Decimal | None:
    if not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        errors.append(f"{field}: {value!r} is not a number")
        return None


def parse_date(value: str, field: str, errors: list[str]) -> date | None:
    if not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        errors.append(f"{field}: {value!r} is not a date in YYYY-MM-DD form")
        return None


def parse_yes_no(value: str, field: str, errors: list[str]) -> bool | None:
    """True or False, or None for a blank -- which means "leave it as it is"."""
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned in YES:
        return True
    if cleaned in NO:
        return False
    errors.append(f"{field}: {value!r} is not yes or no")
    return None


def check_row(row: dict, line: int) -> tuple[dict, list[str]]:
    """Clean up one row and collect everything wrong with it."""
    errors: list[str] = []
    data = {k: (row.get(k) or "").strip() for k in ALL_COLUMNS}

    for column in REQUIRED_COLUMNS:
        if not data[column]:
            errors.append(f"{column} is required")

    data["ordered_qty"] = parse_decimal(data["ordered_qty"], "ordered_qty", errors)
    data["dispatched_qty"] = parse_decimal(data["dispatched_qty"], "dispatched_qty", errors)
    data["etd"] = parse_date(data["etd"], "etd", errors)
    data["eta"] = parse_date(data["eta"], "eta", errors)

    if data["shipment_no"] and data["dispatched_qty"] is None:
        errors.append("dispatched_qty is required when shipment_no is given")

    if not data["shipment_no"] and any(
        data[f]
        for f in ("vessel_name", "imo_number", "container_no", "bl_number",
                  "shipment_status", "last_shipment")
    ):
        errors.append("shipment details given without a shipment_no")

    if data["imo_number"] and not valid_imo(data["imo_number"]):
        errors.append(f"imo_number: {data['imo_number']!r} is not a valid IMO number")

    # Same rule as the staff screen applies, from the same function, so a
    # container number the screen refuses cannot arrive through a CSV.
    if data["container_no"]:
        data["container_no"] = tidy_container_no(data["container_no"])
        if not valid_container_no(data["container_no"]):
            errors.append(
                f"container_no: {data['container_no']!r} is not a valid "
                "container number (ISO 6346, e.g. MSCU1234566)"
            )

    # The staff screen refuses this too. Both sides of the portal have to
    # agree on what a valid shipment looks like, or a row the importer
    # accepts becomes one nobody can edit afterwards.
    if data["etd"] and data["eta"] and data["eta"] < data["etd"]:
        errors.append("eta is before etd")

    # The same status list the staff screen offers, from the same service,
    # so a spelling a CSV would accept is one the screen would accept too.
    for field in ("order_status", "shipment_status"):
        try:
            data[field] = statuses.canonical(data[field])
        except statuses.StatusProblem as problem:
            errors.append(f"{field}: {problem}")
            data[field] = None

    # An order's status is worked out from its shipments, so Cancelled is the
    # one thing a file can still say about it. Anything else would be thrown
    # away without a word, so it is refused instead.
    if data["order_status"] not in (None, statuses.CANCELLED):
        errors.append(
            f"order_status: {data['order_status']!r} is worked out from the "
            "shipments now, so leave it blank, or put Cancelled"
        )

    data["last_shipment"] = parse_yes_no(data["last_shipment"], "last_shipment", errors)

    if not data["unit"]:
        data["unit"] = "MT"

    return data, [f"line {line}: {e}" for e in errors]


# ------------------------------------------------------------------ loading


def apply_rows(rows: list[dict], dry_run: bool, file_name: str = "a CSV file") -> dict:
    counts = {
        "customers_created": 0, "orders_created": 0, "orders_updated": 0,
        "shipments_created": 0, "shipments_updated": 0,
    }

    with SessionLocal() as session:

        def record(action: str, summary: str, before: dict, after: dict, labels: dict):
            # Only what the import actually changed. The same export run
            # again every morning must not bury the one row that moved under
            # a hundred that did not. A dry run rolls these back with
            # everything else.
            changes = audit.diff(before, after, labels)
            if changes:
                audit.record(
                    session,
                    action,
                    f"{summary} (CSV import of {file_name})",
                    source=audit.CSV_IMPORT,
                    changes=changes,
                )

        for data in rows:
            customer = session.scalar(
                select(Customer).where(Customer.code == data["customer_code"])
            )
            if customer is None:
                if not data["customer_name"]:
                    raise ValueError(
                        f"customer {data['customer_code']} is new, so customer_name "
                        "is required on its first row"
                    )
                customer = Customer(
                    code=data["customer_code"],
                    name=data["customer_name"],
                    country=data["customer_country"] or None,
                )
                session.add(customer)
                session.flush()
                counts["customers_created"] += 1
                record(
                    "customer.created", f"Added customer {customer.code}",
                    {}, audit.snapshot(customer, audit.CUSTOMER_FIELDS),
                    audit.CUSTOMER_FIELDS,
                )
            elif data["customer_name"]:
                before = audit.snapshot(customer, audit.CUSTOMER_FIELDS)
                customer.name = data["customer_name"]
                if data["customer_country"]:
                    customer.country = data["customer_country"]
                record(
                    "customer.updated", f"Changed customer {customer.code}",
                    before, audit.snapshot(customer, audit.CUSTOMER_FIELDS),
                    audit.CUSTOMER_FIELDS,
                )

            order = session.scalar(
                select(Order).where(Order.sales_order_no == data["sales_order_no"])
            )
            order_values = {
                "customer_id": customer.id,
                "customer_po": data["customer_po"] or None,
                "grade": data["grade"] or None,
                "description": data["description"] or None,
                "ordered_qty": data["ordered_qty"],
                "unit": data["unit"],
            }
            # A file can cancel an order, but a blank never takes it back
            # out: that is a correction, and only the staff screen makes one.
            cancels = data["order_status"] == statuses.CANCELLED
            if order is None:
                order = Order(
                    sales_order_no=data["sales_order_no"],
                    cancelled=cancels,
                    **order_values,
                )
                session.add(order)
                session.flush()
                counts["orders_created"] += 1
                record(
                    "order.created",
                    f"Created order {order.sales_order_no} for {customer.code}",
                    {}, audit.order_state(session, order), audit.ORDER_LABELS,
                )
            else:
                before = audit.order_state(session, order)
                for field, value in order_values.items():
                    setattr(order, field, value)
                if cancels:
                    order.cancelled = True
                counts["orders_updated"] += 1
                record(
                    "order.updated", f"Changed order {order.sales_order_no}",
                    before, audit.order_state(session, order), audit.ORDER_LABELS,
                )

            if data["shipment_no"]:
                shipment = session.scalar(
                    select(Shipment).where(Shipment.shipment_no == data["shipment_no"])
                )
                shipment_values = {
                    "order_id": order.id,
                    "dispatched_qty": data["dispatched_qty"],
                    "unit": data["unit"],
                    "status": data["shipment_status"] or None,
                    "vessel_name": data["vessel_name"] or None,
                    "imo_number": data["imo_number"] or None,
                    "container_no": data["container_no"] or None,
                    "bl_number": data["bl_number"] or None,
                    "etd": data["etd"],
                    "eta": data["eta"],
                }
                if shipment is None:
                    shipment = Shipment(
                        shipment_no=data["shipment_no"],
                        is_final=bool(data["last_shipment"]),
                        **shipment_values,
                    )
                    session.add(shipment)
                    counts["shipments_created"] += 1
                    record(
                        "shipment.created",
                        f"Added shipment {shipment.shipment_no} "
                        f"to order {order.sales_order_no}",
                        {}, audit.snapshot(shipment, audit.SHIPMENT_FIELDS),
                        audit.SHIPMENT_FIELDS,
                    )
                else:
                    # A file never makes a correction. Stopping here, before
                    # anything is committed, means nothing in the file is
                    # saved -- not just this row.
                    try:
                        statuses.check_move(
                            shipment.status, shipment_values["status"],
                            allow_backwards=False,
                        )
                    except statuses.StatusProblem:
                        raise ValueError(
                            f"shipment {shipment.shipment_no} would move back from "
                            f"{shipment.status} to {shipment_values['status']}. An "
                            "import never makes a correction: if the earlier status "
                            "was wrong, change it on the staff screen first"
                        ) from None

                    before = audit.snapshot(shipment, audit.SHIPMENT_FIELDS)
                    for field, value in shipment_values.items():
                        setattr(shipment, field, value)
                    # Blank means "leave it", so a tick made on the staff
                    # screen is not wiped by the next morning's export.
                    if data["last_shipment"] is not None:
                        shipment.is_final = data["last_shipment"]
                    counts["shipments_updated"] += 1
                    record(
                        "shipment.updated",
                        f"Changed shipment {shipment.shipment_no} "
                        f"on order {order.sales_order_no}",
                        before, audit.snapshot(shipment, audit.SHIPMENT_FIELDS),
                        audit.SHIPMENT_FIELDS,
                    )

            session.flush()

        if dry_run:
            session.rollback()
        else:
            session.commit()

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Import orders and shipments from CSV.")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and report, but change nothing")
    args = parser.parse_args()

    if not args.csv_file.is_file():
        print(f"Error: no such file: {args.csv_file}")
        return 1

    with args.csv_file.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            print(f"Error: the file is missing these columns: {', '.join(missing)}")
            print(f"Expected columns: {', '.join(ALL_COLUMNS)}")
            return 1

        rows, errors = [], []
        for line, raw in enumerate(reader, start=2):
            data, row_errors = check_row(raw, line)
            errors.extend(row_errors)
            if not row_errors:
                rows.append(data)

    print(f"Read {len(rows) + len({e.split(':')[0] for e in errors})} row(s) "
          f"from {args.csv_file.name}")

    if errors:
        print(f"\n{len(errors)} problem(s) found:")
        for error in errors:
            print(f"  - {error}")
        print("\nNothing was imported. Fix the file and run again.")
        return 1

    try:
        counts = apply_rows(rows, args.dry_run, args.csv_file.name)
    except ValueError as exc:
        print(f"\nError: {exc}")
        print("Nothing was imported.")
        return 1

    print("\nDry run — nothing was saved:" if args.dry_run else "\nImported:")
    for label, value in counts.items():
        print(f"  {label.replace('_', ' '):<20} {value}")
    if args.dry_run:
        print("\nRun again without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
