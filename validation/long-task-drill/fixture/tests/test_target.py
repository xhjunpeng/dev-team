import unittest

from export_orders import select_orders


def order(identifier, amount="10.00", status="paid", updated_at="2026-10-22T10:00:00+08:00"):
    return {"id": identifier, "customer": "测试客户", "amount": amount, "currency": "CNY", "status": status, "updated_at": updated_at}


class TargetTests(unittest.TestCase):
    def test_latest_record_across_pages_is_exported_once(self):
        pages = [[order("A001")], [order("A001", amount="12.00", updated_at="2026-10-22T11:00:00+08:00")]]
        self.assertEqual([(row["id"], row["amount"]) for row in select_orders(pages)], [("A001", "12.00")])

    def test_latest_cancelled_record_removes_earlier_paid_version(self):
        pages = [[order("B002")], [order("B002", status="cancelled", updated_at="2026-10-22T11:00:00+08:00")]]
        self.assertEqual(select_orders(pages), [])

    def test_newer_version_does_not_move_first_seen_order(self):
        pages = [[order("A001", amount="12.00", updated_at="2026-10-22T11:00:00+08:00"), order("C003")], [order("A001")]]
        self.assertEqual([(row["id"], row["amount"]) for row in select_orders(pages)], [("A001", "12.00"), ("C003", "10.00")])
