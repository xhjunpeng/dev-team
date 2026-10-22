import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from export_orders import build_csv, select_orders
from test_target import order


class RegressionTests(unittest.TestCase):
    def test_actual_time_across_timezones(self):
        older = order("A001", amount="10.00", updated_at="2026-10-22T10:00:00+08:00")
        newer = order("A001", amount="12.00", updated_at="2026-10-22T03:00:00+00:00")
        self.assertEqual(select_orders([[older], [newer]])[0]["amount"], "12.00")

    def test_equal_timestamp_keeps_last_encountered(self):
        self.assertEqual(select_orders([[order("A001")], [order("A001", amount="12.00")]])[0]["amount"], "12.00")

    def test_input_remains_unchanged(self):
        pages = [[order("A001")], [order("A001", amount="12.00")]]
        original = copy.deepcopy(pages)
        select_orders(pages)
        build_csv(pages)
        self.assertEqual(pages, original)

    def test_csv_round_trip_handles_special_characters(self):
        row = order("A001")
        row["customer"] = '小李, "外卖"\n店'
        records = list(csv.DictReader(io.StringIO(build_csv([[row]]), newline="")))
        self.assertEqual(records, [{key: row[key] for key in ("id", "customer", "amount", "currency")}])

    def test_empty_result_preserves_header(self):
        text = build_csv([[], [order("B002", status="cancelled")]])
        reader = csv.DictReader(io.StringIO(text))
        self.assertEqual(reader.fieldnames, ["id", "customer", "amount", "currency"])
        self.assertEqual(list(reader), [])

    def test_single_page_without_duplicates(self):
        rows = select_orders([[order("A001"), order("B002", status="pending")]])
        self.assertEqual([row["id"] for row in rows], ["A001"])

    def test_cli_exports_final_order_state(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-B", str(root / "export_orders.py"), str(root / "fixtures/orders.json")], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        records = list(csv.DictReader(io.StringIO(result.stdout, newline="")))
        self.assertEqual([(row["id"], row["amount"]) for row in records], [("A001", "12.00"), ("C003", "8.50")])
