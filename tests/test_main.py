"""Simple assert tests for main.py. No API is called.
Run from the project folder with: python -m tests.test_main
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from main import leave_time, show_time, format_summary, append_csv, AIRPORTS

berlin = ZoneInfo("Europe/Berlin")
chicago = ZoneInfo("America/Chicago")

# leave_time: target minus drive time and safety margin
target = datetime(2026, 11, 20, 16, 22, tzinfo=berlin)
assert leave_time(target, 35, 10) == datetime(2026, 11, 20, 15, 37, tzinfo=berlin)
assert leave_time(target, 0, 0) == target

# show_time: 6 hours difference on 28 Oct, 7 hours on 6 Nov (US3)
assert show_time(datetime(2026, 10, 28, 12, 0, tzinfo=berlin), AIRPORTS["EDDF"]) == "12:00 CET (06:00 CDT)"
assert show_time(datetime(2026, 11, 6, 12, 0, tzinfo=berlin), AIRPORTS["EDDF"]) == "12:00 CET (05:00 CST)"
assert show_time(datetime(2026, 11, 20, 20, 0, tzinfo=chicago), AIRPORTS["KORD"]) == "20:00 CST (03:00 CET)"

# format_summary: departure mode
moment = datetime(2026, 11, 20, 12, 0, tzinfo=berlin)
result = {"mode": "departure", "airport": "EDDF", "departure": moment, "target": moment, "leave": moment}
text = format_summary(result)
assert "Leave at: 12:00 CET" in text
assert "Estimate only" not in text

# append_csv: header once, then one row per call
path = "tests/test_log.csv"
if os.path.exists(path):
    os.remove(path)
append_csv(["t1", "pickup", "DLH123", "2026-11-20 15:52", "2026-11-20 15:37"], path)
append_csv(["t2", "departure", "", "", "2026-11-21 08:00"], path)
with open(path, encoding="utf-8") as file:
    lines = file.read().splitlines()
os.remove(path)
assert lines[0] == "time,mode,flight,landing,leave_time"
assert len(lines) == 3

print("All main.py tests passed.")
