#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Pantry expiry scanner (standard library only, deterministic).

Computes effective expiry, remaining days and urgency groups from a grocery
ledger CSV. The LLM handles language, extraction and CSV writes; this script
handles date math so results are fast, cheap and testable.

Supports both English and original Chinese headers.

Usage:
  python3 expiry_calc.py --csv food_inventory.csv
  python3 expiry_calc.py --csv food_inventory.csv --date 2026-11-24 --format md
  python3 expiry_calc.py --csv food_inventory.csv --focus milk

Output: JSON by default, or Markdown with --format md. Read-only.
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta

# Canonical 13 columns and accepted aliases (alias keys are lower-cased).
REQUIRED_COLUMNS = [
    "name", "category", "quantity", "storage_location", "production_date",
    "shelf_life_days", "package_expiry", "opened_date", "days_after_opening",
    "recorded_date", "status", "disposal_method", "notes",
]

HEADER_ALIASES = {
    # English
    "name": "name", "food": "name", "item": "name", "food_name": "name",
    "category": "category", "type": "category",
    "quantity": "quantity", "spec": "quantity", "spec_quantity": "quantity",
    "storage_location": "storage_location", "location": "storage_location",
    "production_date": "production_date", "manufacture_date": "production_date",
    "shelf_life_days": "shelf_life_days", "shelf_life": "shelf_life_days",
    "package_expiry": "package_expiry", "expiry_date": "package_expiry",
    "expiry": "package_expiry", "best_before": "package_expiry",
    "use_by": "package_expiry",
    "opened_date": "opened_date", "date_opened": "opened_date",
    "days_after_opening": "days_after_opening",
    "after_opening_days": "days_after_opening", "open_limit": "days_after_opening",
    "recorded_date": "recorded_date", "entry_date": "recorded_date",
    "status": "status", "state": "status",
    "disposal_method": "disposal_method", "handling": "disposal_method",
    "handled_by": "disposal_method",
    "notes": "notes", "note": "notes", "remark": "notes",
    # Chinese
    "食品名称": "name", "名称": "name",
    "分类": "category",
    "规格数量": "quantity", "规格": "quantity", "数量": "quantity",
    "存放位置": "storage_location", "位置": "storage_location",
    "生产日期": "production_date",
    "保质期天数": "shelf_life_days", "保质期": "shelf_life_days",
    "包装到期日": "package_expiry", "到期日": "package_expiry",
    "开封日期": "opened_date",
    "开封后建议期限": "days_after_opening", "开封期限": "days_after_opening",
    "录入日期": "recorded_date",
    "状态": "status",
    "处理方式": "disposal_method",
    "备注": "notes",
}

# Fallback warning windows by category (used when total shelf life is unknown).
CATEGORY_WARN_DAYS = {
    "dairy": 2, "乳制品": 2,
    "meat & eggs": 2, "meat": 2, "eggs": 2, "肉蛋": 2,
    "seafood": 2, "水产": 2,
    "deli & soy": 2, "deli": 2, "cooked food": 2, "熟食豆制品": 2,
    "熟食": 2, "豆制品": 2,
    "produce": 3, "vegetables": 3, "fruit": 3, "蔬果": 3, "蔬菜": 3, "水果": 3,
    "bakery & staples": 3, "bakery": 3, "staples": 3,
    "主食烘焙": 3, "主食": 3, "烘焙": 3,
    "snacks": 30, "零食": 30,
    "condiments": 30, "调味品": 30,
    "frozen": 90, "frozen food": 90, "冷冻食品": 90,
    "beverages": 30, "drinks": 30, "饮料": 30,
}

GROUPS = ["expired", "due_today", "soon", "normal", "insufficient_info", "processed"]


def parse_date(value):
    """Parse common date formats; empty -> None; invalid -> ValueError."""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {value!r} (expected YYYY-MM-DD)")


def parse_duration_days(value):
    """'7', '7 days', '12 months', '1 year' -> days; None if unparseable."""
    value = (value or "").strip().lower()
    if not value:
        return None
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(days?|d|天|日|months?|月|个月|years?|y|年)?$", value)
    if not match:
        try:
            return int(float(value))
        except ValueError:
            return None
    number = float(match.group(1))
    unit = match.group(2) or "days"
    if unit in ("month", "months", "月", "个月"):
        return int(round(number * 30))
    if unit in ("year", "years", "y", "年"):
        return int(round(number * 365))
    return int(round(number))


def warn_days(shelf_days, category):
    """Prefer total-shelf-life tiers; fall back to category, then 3."""
    if isinstance(shelf_days, int) and shelf_days > 0:
        if shelf_days <= 7:
            return 2
        if shelf_days <= 30:
            return 3
        if shelf_days <= 365:
            return 7
        return 14
    return CATEGORY_WARN_DAYS.get((category or "").strip().lower(), 3)


def normalize_row(raw):
    """Map original headers (EN/CN) to canonical keys; keep overflow fields."""
    normalized = {key: "" for key in REQUIRED_COLUMNS}
    for original_key, value in raw.items():
        if original_key is None:
            continue
        canonical = HEADER_ALIASES.get(str(original_key).strip().lower())
        if canonical:
            normalized[canonical] = (value or "").strip()
    normalized["_extra_fields"] = raw.get(None) or []
    return normalized


def compute_row(row, today):
    name = row.get("name", "").strip()
    category = row.get("category", "").strip()
    location = row.get("storage_location", "").strip()
    raw_status = row.get("status", "").strip().lower()
    method = row.get("disposal_method", "").strip()

    result = {
        "name": name,
        "category": category,
        "location": location,
        "package_expiry": None,
        "opened_expiry": None,
        "effective_expiry": None,
        "remaining_days": None,
        "state": None,
        "warnings": [],
        "processed": ("processed" in raw_status) or ("已处理" in raw_status) or bool(method),
        "disposal_method": method,
        "notes": row.get("notes", "").strip(),
    }

    extra = row.get("_extra_fields") or []
    if extra:
        result["warnings"].append(
            f"row has {len(extra)} extra field(s); possible unescaped comma or column shift: {extra}"
        )

    if not name:
        result["state"] = "invalid_row"
        return result

    if result["processed"]:
        result["state"] = "processed"
        return result

    try:
        package_expiry = parse_date(row.get("package_expiry"))
        production_date = parse_date(row.get("production_date"))
        shelf_days = parse_duration_days(row.get("shelf_life_days"))
        opened_date = parse_date(row.get("opened_date"))
        open_limit = parse_duration_days(row.get("days_after_opening"))
    except ValueError as exc:
        result["state"] = "insufficient_info"
        result["warnings"].append(str(exc))
        return result

    if package_expiry is None and production_date and shelf_days:
        package_expiry = production_date + timedelta(days=shelf_days)
    result["package_expiry"] = package_expiry.isoformat() if package_expiry else None

    opened_expiry = None
    if opened_date:
        if open_limit:
            opened_expiry = opened_date + timedelta(days=open_limit)
        else:
            result["warnings"].append(
                "opened without an after-opening limit; using package date for now"
            )
    result["opened_expiry"] = opened_expiry.isoformat() if opened_expiry else None

    candidates = [d for d in (package_expiry, opened_expiry) if d is not None]
    if not candidates:
        result["state"] = "insufficient_info"
        result["warnings"].append("no package expiry and cannot derive from production date + shelf life")
        return result

    effective = min(candidates)
    result["effective_expiry"] = effective.isoformat()
    remaining = (effective - today).days
    result["remaining_days"] = remaining

    window = warn_days(shelf_days, category)
    if remaining < 0:
        state = "expired"
    elif remaining == 0:
        state = "due_today"
    elif remaining <= window:
        state = "soon"
    else:
        state = "normal"

    result["state"] = state
    result["warn_within_days"] = window
    return result


def group_items(items):
    groups = {key: [] for key in GROUPS}
    for item in items:
        groups.setdefault(item["state"], []).append(item)
    for key in ("expired", "due_today", "soon", "normal"):
        groups[key].sort(key=lambda x: (x["remaining_days"] is None, x["remaining_days"]))
    return groups


def render_markdown(today, groups):
    title_map = [
        ("expired", "Expired", "handle soon"),
        ("due_today", "Due today", "eat today"),
        ("soon", "Expiring soon", "prioritize"),
        ("normal", "Normal", "later"),
        ("insufficient_info", "Insufficient information", "date needed"),
    ]
    lines = [f"# Food Expiry Reminder ({today.isoformat()})", ""]

    warnings = []
    for group in groups.values():
        for item in group:
            for message in item.get("warnings", []):
                warnings.append(f"- {item.get('name') or 'unnamed row'}: {message}")
    if warnings:
        lines += ["## Data validation warnings"] + warnings + [""]

    for key, label, hint in title_map:
        rows = groups.get(key, [])
        if not rows:
            continue
        lines.append(f"## {label} ({len(rows)}) | {hint}")
        for it in rows:
            loc = f", {it['location']}" if it["location"] else ""
            if it["remaining_days"] is None:
                lines.append(f"- {it['name']} ({it['category']}{loc}): date/shelf-life missing")
            elif key == "expired":
                lines.append(
                    f"- {it['name']} ({it['category']}{loc}): expired "
                    f"{abs(it['remaining_days'])} day(s) ago, effective {it['effective_expiry']}"
                )
            elif key == "due_today":
                lines.append(
                    f"- {it['name']} ({it['category']}{loc}): due today ({it['effective_expiry']})"
                )
            else:
                lines.append(
                    f"- {it['name']} ({it['category']}{loc}): {it['remaining_days']} day(s) left, "
                    f"effective {it['effective_expiry']}"
                )
        lines.append("")

    if groups.get("insufficient_info"):
        lines.append("> Add the expiry date, or production date + shelf-life days, for accurate alerts.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="Smart Pantry expiry scanner")
    parser.add_argument("--csv", required=True, help="path to the ledger CSV")
    parser.add_argument("--date", help="scan base date YYYY-MM-DD (default: today)")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--focus", help="keep only items whose name contains this keyword")
    args = parser.parse_args()

    try:
        today = parse_date(args.date) if args.date else datetime.now().date()
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    try:
        with open(args.csv, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("CSV is empty or missing a header row")

            mapped = set()
            for field in reader.fieldnames:
                if field is None:
                    continue
                canonical = HEADER_ALIASES.get(field.strip().lower())
                if canonical:
                    mapped.add(canonical)
            missing = [col for col in REQUIRED_COLUMNS if col not in mapped]
            if missing:
                raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

            raw_rows = list(reader)
    except FileNotFoundError:
        print(json.dumps({"error": f"ledger not found: {args.csv}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError, csv.Error) as exc:
        print(json.dumps({"error": f"failed to read ledger: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 2

    rows = [normalize_row(raw) for raw in raw_rows]
    items = [compute_row(row, today) for row in rows]

    if args.focus:
        keyword = args.focus.strip().lower()
        items = [it for it in items if keyword in it["name"].lower()]

    groups = group_items(items)

    if args.format == "md":
        sys.stdout.write(render_markdown(today, groups))
        return 0

    summary = {key: len(groups.get(key, [])) for key in GROUPS}
    print(json.dumps(
        {"today": today.isoformat(), "summary": summary, "groups": groups},
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
