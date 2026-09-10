"""Load real order and shipment data into the portal from a CSV file.

This is the bridge from SAP/PMS. Whatever those systems can export, the job
is to map it into the CSV described below; nothing else in the portal needs
to change.

    python import_data.py orders.csv --dry-run   # check the file, change nothing
    python import_data.py orders.csv             # apply it

Safe to run repeatedly. Rows are matched on sales_order_no and shipment_no,
so re-importing an updated export refreshes the existing rows rather than
creating duplicates. Nothing is ever deleted.

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
    order_status        optional
    shipment_no         blank if nothing has shipped yet
    dispatched_qty      required when shipment_no is given
    shipment_status     optional
    vessel_name         optional
    imo_number          optional   7 digits, checksum validated
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

from database import SessionLocal
from models import Customer, Order, Shipment
from sqlalchemy import select
from tracking import valid_imo

REQUIRED_COLUMNS = [
    "customer_code",
    "sales_order_no",
    "ordered_qty",
]

ALL_COLUMNS = [
    "customer_code", "customer_name", "customer_country",
    "sales_order_no", "customer_po", "grade", "description",
    "ordered_qty", "unit", "order_status",
    "shipment_no", "dispatched_qty", "shipment_status",
    "vessel_name", "imo_number", "etd", "eta",
]


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
        data[f] for f in ("vessel_name", "imo_number", "shipment_status")
    ):
        errors.append("shipment details given without a shipment_no")

    if data["imo_number"] and not valid_imo(data["imo_number"]):
        errors.append(f"imo_number: {data['imo_number']!r} is not a valid IMO number")

    # The staff screen refuses this too. Both sides of the portal have to
    # agree on what a valid shipment looks like, or a row the importer
    # accepts becomes one nobody can edit afterwards.
    if data["etd"] and data["eta"] and data["eta"] < data["etd"]:
        errors.append("eta is before etd")

    if not data["unit"]:
        data["unit"] = "MT"

    return data, [f"line {line}: {e}" for e in errors]


# ------------------------------------------------------------------ loading


def apply_rows(rows: list[dict], dry_run: bool) -> dict:
    counts = {
        "customers_created": 0, "orders_created": 0, "orders_updated": 0,
        "shipments_created": 0, "shipments_updated": 0,
    }

    with SessionLocal() as session:
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
            elif data["customer_name"]:
                customer.name = data["customer_name"]
                if data["customer_country"]:
                    customer.country = data["customer_country"]

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
                "status": data["order_status"] or None,
            }
            if order is None:
                order = Order(sales_order_no=data["sales_order_no"], **order_values)
                session.add(order)
                session.flush()
                counts["orders_created"] += 1
            else:
                for field, value in order_values.items():
                    setattr(order, field, value)
                counts["orders_updated"] += 1

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
                    "etd": data["etd"],
                    "eta": data["eta"],
                }
                if shipment is None:
                    shipment = Shipment(
                        shipment_no=data["shipment_no"], **shipment_values
                    )
                    session.add(shipment)
                    counts["shipments_created"] += 1
                else:
                    for field, value in shipment_values.items():
                        setattr(shipment, field, value)
                    counts["shipments_updated"] += 1

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
        counts = apply_rows(rows, args.dry_run)
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
