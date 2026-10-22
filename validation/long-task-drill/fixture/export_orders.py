"""Export the latest paid order versions for a local development drill."""

import argparse
import csv
import io
import json
from datetime import datetime
from pathlib import Path


def select_orders(pages):
    latest_by_id = {}
    for page in pages:
        for order in page:
            identifier = order["id"]
            updated_at = datetime.fromisoformat(order["updated_at"])
            if identifier not in latest_by_id or updated_at >= latest_by_id[identifier][0]:
                latest_by_id[identifier] = (updated_at, order)
    return [dict(order) for _, order in latest_by_id.values() if order["status"] == "paid"]


def build_csv(pages):
    output = io.StringIO(newline="")
    columns = ("id", "customer", "amount", "currency")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for order in select_orders(pages):
        writer.writerow({column: order[column] for column in columns})
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    pages = json.loads(args.input.read_text(encoding="utf-8"))
    print(build_csv(pages), end="")


if __name__ == "__main__":
    main()
