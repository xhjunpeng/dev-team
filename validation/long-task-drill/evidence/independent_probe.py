"""Replay the independent reviewer's in-memory acceptance probes."""

import copy
import csv
import io
import itertools
from pathlib import Path

import export_orders as final

COLUMNS = ["id", "customer", "amount", "currency"]


def check_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def row(identifier, status, timestamp, amount="0001.2300", customer="虚构客户"):
    return dict(id=identifier, customer=customer, amount=amount, currency="CNY",
                status=status, updated_at=timestamp)


# UTC ranks are hand-derived, independent of the implementation's time parser.
records = [
    (row("A", "paid", "2025-12-31T23:30:00-02:00"), 1_500_000),
    (row("A", "cancelled", "2026-01-01T02:30:00+00:00"), 2_500_000),
    (row("A", "paid", "2026-01-01T11:30:00+09:00", "0099.9900"), 2_500_000),
    (row("B", "cancelled", "2026-01-01T02:00:00+00:00"), 2_000_000),
    (row("B", "paid", "2026-01-01T02:00:00.000001Z", "0.000001"), 2_000_001),
    (row("C", "pending", "2026-01-01T02:00:00+00:00"), 2_000_000),
]

cases = 0
for perm in itertools.permutations(records):
    first_ids = list(dict.fromkeys(record["id"] for record, _ in perm))
    expected = []
    for identifier in first_ids:
        candidates = [(rank, position, record)
                      for position, (record, rank) in enumerate(perm)
                      if record["id"] == identifier]
        chosen = max(candidates, key=lambda item: (item[0], item[1]))[2]
        if chosen["status"] == "paid":
            expected.append(chosen)
    flattened = [record for record, _ in perm]
    partitions = [
        [flattened],
        [[], *[[record] for record in flattened], []],
        [flattened[:2], [], flattened[2:5], flattened[5:]],
    ]
    for pages in partitions:
        before = copy.deepcopy(pages)
        check_equal(final.select_orders(pages), expected, "selected versions and order")
        actual_csv = list(csv.reader(io.StringIO(final.build_csv(pages), newline="")))
        expected_csv = [COLUMNS] + [[record[key] for key in COLUMNS] for record in expected]
        check_equal(actual_csv, expected_csv, "CSV data and amount spelling")
        check_equal(pages, before, "input mutation")
        cases += 1
print(f"PERMUTATION_CASES={cases}: PASS (UTC ordering, equal instant, microseconds, status, page layout, first-seen order, amount, immutability)")

for index, customer in enumerate(["甲\n乙", "甲\r\n乙", "甲\r乙", '甲,"乙"\n丙\r\n丁\r戊']):
    pages = [[row("SPECIAL", "paid", "2026-01-01T00:00:00Z", customer=customer)]]
    before = copy.deepcopy(pages)
    raw = final.build_csv(pages)
    check_equal(list(csv.reader(io.StringIO(raw, newline=""))),
                [COLUMNS, [pages[0][0][key] for key in COLUMNS]], f"special characters {index}")
    check_equal(pages, before, "special-character input mutation")
    print(f"CSV_SPECIAL_{index}: PASS input={customer!r} output={raw!r}")

for pages in [[], [[]], [[], []], [[row("EMPTY", "cancelled", "2026-01-01T00:00:00Z")]]]:
    check_equal(final.select_orders(pages), [], "empty selection")
    check_equal(final.build_csv(pages), "id,customer,amount,currency\r\n", "empty header")
print("EMPTY_CASES=4: PASS")

# Execute the original defect in memory; the frozen candidate stays untouched.
starter = {"__name__": "starter_negative_control"}
exec(compile(Path("../evidence/starter_export_orders.py").read_text(),
             "starter_export_orders.py", "exec"), starter)
control_pages = [[row("A", "paid", "2026-01-01T00:00:00Z")],
                 [row("A", "cancelled", "2026-01-01T00:01:00Z")]]
control = starter["select_orders"](control_pages)
check_equal(control != [], True, "negative control must expose starter defect")
print(f"NEGATIVE_CONTROL: expected=[] starter_actual={control!r}; starter rejected")
print("INDEPENDENT_PROBES=PASS")
