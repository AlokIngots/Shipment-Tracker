"""Check the ShipsGo key before anybody presses Enable tracking. Reads only.

    python -m scripts.shipsgo_check                      # does the key work?
    python -m scripts.shipsgo_check --bl EGLV100650230407  # is this B/L in ShipsGo?
    python -m scripts.shipsgo_check --id 5001            # read one shipment back

Nothing here can add a shipment or spend a credit: it uses the same client
as the portal, which refuses every write except the one Enable makes, and
this script never asks for that. Every read reports the credit cost ShipsGo
sent back, so it doubles as proof that reading really is free on this plan
-- run it once after putting SHIPSGO_API_KEY in .env, before tracking is
switched on for a real shipment.

On the server:
    docker compose -f docker-compose.prod.yml -f docker-compose.server.yml \\
        exec api python -m scripts.shipsgo_check
"""

import argparse
import json
import sys

from app.services import shipsgo


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only ShipsGo check.")
    parser.add_argument("--bl", help="look this B/L number up (free)")
    parser.add_argument("--id", type=int, help="read this ShipsGo shipment (free)")
    args = parser.parse_args()

    if not shipsgo.configured():
        print("SHIPSGO_API_KEY is empty. Live tracking is off on this server.")
        return 1

    try:
        answer = shipsgo._call("GET", "/ocean/shipments", query={"take": 1})
        print(
            f"Key works: ShipsGo answered {answer.status}. "
            f"Credit cost of this read: {answer.credits_cost or 0}."
        )

        if args.bl:
            found = shipsgo.find_by_booking(args.bl.strip().upper())
            print(
                f"{args.bl}: already in ShipsGo as #{found} -- enabling it costs nothing."
                if found
                else f"{args.bl}: not in ShipsGo yet -- enabling it would use 1 credit."
            )

        if args.id:
            detail = shipsgo.get_shipment(args.id)
            route = detail.get("route") or {}
            print(json.dumps(
                {
                    "status": detail.get("status"),
                    "booking_number": detail.get("booking_number"),
                    "port_of_loading": ((route.get("port_of_loading") or {}).get("location") or {}).get("name"),
                    "port_of_discharge": ((route.get("port_of_discharge") or {}).get("location") or {}).get("name"),
                    "transshipments": route.get("ts_count"),
                    "containers": [c.get("number") for c in detail.get("containers") or []],
                },
                indent=2,
            ))
    except shipsgo.ShipsGoError as error:
        print(f"ShipsGo: {error.message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
