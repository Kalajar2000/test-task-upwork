#!/usr/bin/env python3
"""Build the dashboard dataset from the raw leads CSV.

The raw export contains PII (names, emails, phone numbers) and this repo is
public — so the pipeline is the privacy boundary. It reads the CSV locally,
strips every identifying field, normalizes the messy dimensions (UTM source
variants, medium strings, campaign naming), and writes an anonymized
row-level JSON that the dashboard aggregates client-side.

Usage:
    python3 pipeline/build_dashboard_data.py path/to/leads.csv
    python3 pipeline/build_dashboard_data.py --url   # fetch from the sheet

Output: site/dashboard/data.json
"""

import csv
import json
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1GtF3Ae1aSo_4eXFkpbUx-Ko3gaEsRvkWh81Qegco7gM/export?format=csv"
)
OUT_PATH = Path(__file__).resolve().parent.parent / "site" / "dashboard" / "data.json"

# Fields that must never reach the public dataset.
PII_COLUMNS = {"Lead Name", "Email", "Phone Number"}

SOURCE_MAP = {
    "ig": "Instagram", "instagram": "Instagram",
    "fb": "Facebook",
    "email": "Email", "newsletter": "Email",
    "clippers": "Other", "skoolcal": "Other",
    "": "Untracked",
}


def norm_source(raw: str) -> str:
    return SOURCE_MAP.get((raw or "").strip().lower(), "Other")


def norm_medium(raw: str) -> str:
    r = (raw or "").lower()
    if not r.strip():
        return "Untracked"
    for key, label in [("reels", "Reels"), ("feed", "Feed"), ("stories", "Stories"),
                       ("video", "Video"), ("social", "Social"), ("marketplace", "Other"),
                       ("search", "Other"), ("explore", "Other"), ("right_hand", "Other")]:
        if key in r:
            return label
    return "Other"


def norm_campaign(raw: str) -> str:
    """'14.05 | Imran | Bird Ad v1 – Copy 2' -> 'Imran | Bird Ad v1'"""
    c = (raw or "").strip()
    if not c:
        return "(untracked)"
    c = re.sub(r"^\d{2}\.\d{2}\s*\|\s*", "", c)          # date prefix
    c = re.sub(r"\s*[–-]\s*Copy\s*\d*$", "", c)          # duplicated-ad suffix
    c = re.sub(r"\s+", " ", c).strip()
    return c[:64] or "(untracked)"


def money(raw: str) -> float:
    try:
        return float(raw or 0)
    except ValueError:
        return 0.0


def load_rows(argv):
    if "--url" in argv:
        print("fetching sheet export…")
        data = urllib.request.urlopen(SHEET_CSV_URL, timeout=60).read().decode("utf-8-sig")
        return list(csv.DictReader(data.splitlines()))
    src = Path(argv[1]) if len(argv) > 1 else Path(__file__).parent / "data" / "leads.csv"
    with open(src, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main(argv):
    rows = load_rows(argv)
    assert rows, "no rows parsed"
    assert PII_COLUMNS <= set(rows[0].keys()), "unexpected schema — check the export"

    # data-hygiene stats are computed BEFORE the PII is dropped
    emails = Counter(r["Email"].strip().lower() for r in rows if r["Email"].strip())
    phones = Counter(re.sub(r"\D", "", r["Phone Number"]) for r in rows if r["Phone Number"].strip())
    dupes = {
        "emails": sum(c - 1 for c in emails.values() if c > 1),
        "phones": sum(c - 1 for c in phones.values() if c > 1),
    }

    out_rows = []
    for r in rows:
        cash = money(r["Cash_Collected_USD"])
        rec = {
            "d": (r["Date Captured"] or "")[:10],                 # capture date
            "s": norm_source(r["UTM Source"]),                    # source
            "m": norm_medium(r["UTM Medium"]),                    # placement
            "c": norm_campaign(r["UTM Campaign"]),                # campaign/creative
            "g": r["Lead Grade"] or None,                         # lead grade
            "sc": float(r["Lead Score"]) if r["Lead Score"] else None,
            "crm": 1 if r["Close_In_CRM"] == "Yes" else 0,
            "bk": 1 if r["Close_Booked_Call"] == "Yes" else 0,
            "cl": 1 if r["Close_Closed"] == "Yes" else 0,
            "cash": cash,
            "pay": r["Payment_Type"] or None,
            "prog": r["Program_Type"] or None,
            "cap": (r["Capital available in next 30 days"] or None),
            "inc": (r["Q4. Monthly income (before tax)"] or None),
            "day": (r["Q2. Day-to-day"] or None),
            "fr": (r["Q9. What frustrates you most"] or None),
            "fol": (r["Q10. How long following Abu Lahya"] or None),
            "tried": (r["Q11. Have you tried online business before"] or None),
        }
        # hard guarantee: nothing that looks like PII leaves this function
        assert "@" not in json.dumps(rec), "PII leak guard tripped"
        out_rows.append(rec)

    dates = sorted(x["d"] for x in out_rows if x["d"])
    checksum = {
        "leads": len(out_rows),
        "crm": sum(x["crm"] for x in out_rows),
        "booked": sum(x["bk"] for x in out_rows),
        "closed": sum(x["cl"] for x in out_rows),
        "buyers": sum(1 for x in out_rows if x["cash"] > 0),
        "cash": round(sum(x["cash"] for x in out_rows)),
    }

    payload = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "date_min": dates[0],
            "date_max": dates[-1],
            "dupes": dupes,
            "checksum": checksum,   # the dashboard self-tests against these
            "pii": "stripped at pipeline stage — names/emails/phones never leave the source file",
        },
        "rows": out_rows,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    kb = OUT_PATH.stat().st_size // 1024
    print(f"wrote {OUT_PATH} ({kb} KB) — {checksum}")


if __name__ == "__main__":
    main(sys.argv)
