# Workflow Details, Formulas and Edge Cases

## 1. Effective expiry calculation

### Package expiry
- Use `package_expiry` directly when present.
- Otherwise, when `production_date` and `shelf_life_days` exist:
  `package_expiry = production_date + shelf_life_days`.
- If both exist and disagree, prefer the printed package date and flag the mismatch in `notes`.
- `shelf_life_days` accepts `7`, `7 days`, `12 months` (30 days/month) and `1 year` (365 days).

### After-opening expiry
- When `opened_date` and `days_after_opening` exist:
  `opened_expiry = opened_date + days_after_opening`.
- If opened but the limit is missing, use the category default in `shelf_life_knowledge.md`; if none, ask the user and temporarily judge by package date.

### Effective expiry
- Unopened: `effective_expiry = package_expiry`.
- Opened: `effective_expiry = min(package_expiry, opened_expiry)` — the earlier, more conservative date.

## 2. Remaining days and status

`remaining_days = effective_expiry - scan_date` (whole calendar days).

| Condition | Status |
|---|---|
| status contains `processed` OR `disposal_method` is non-empty | `processed` (excluded) |
| `remaining < 0` | `expired` |
| `remaining = 0` | `due_today` |
| `0 < remaining <= w` | `soon` |
| `remaining > w` | `normal` |
| no computable date | `insufficient_info` |

Window `w` by total shelf life: ≤7d → 2; ≤30d → 3; ≤365d → 7; longer → 14. Fallback to category defaults, then 3 days.

## 3. Scan flow (script first)

1. Locate the latest ledger CSV (default `food_inventory.csv`) in the authorized directory.
2. Run:

```bash
python3 scripts/expiry_calc.py --csv <path>/food_inventory.csv --format md
```

JSON is the default; `--date` fixes the base date and `--focus <keyword>` filters by name. The script is read-only.
3. If Python cannot run, fall back to Sections 1–2 manually and disclose the slower path.
4. Order: expired (longest overdue first) → due today → soon (fewest days first) → normal. Collapse normal items in chat if long.
5. Attach disposal advice for expired items.
6. End by asking for missed/new items (Section 4).

## 4. Instant capture and incremental refresh

Goal: after a report, a user add/update is saved, recomputed and reflected in one turn — no restart and no full re-dump.

### Add vs update
- Match normalized name (ignore spec words), quantity and location to an existing unprocessed row.
- Update when supplying an expiry date, opening date/limit, quantity, location, or changing unopened→opened.
- Append only when no match. If ambiguous (same name, different size), list candidates and ask.

### Write
- Keep the fixed 13-column order; dates as `YYYY-MM-DD`; leave unknown fields empty, never invent.
- Preserve the original `recorded_date` on update; use today for new rows.

### Recompute and report only the delta
- Rerun the script; `--focus` verifies the item.
- Report effective date, remaining days and group; explicitly announce a group jump (e.g. normal → soon).
- If still uncomputable, name the exact missing field.

Example:
> User: There's also a box of strawberries I missed, chilled, package expiry Nov 26, opened today.
> Assistant: Added strawberries. Without an after-opening limit I'm using the package date for now: 2 days left, in "soon". How many days after opening should they be eaten?

## 5. Batch colloquial entry

1. Split one utterance into items using commas, "and", "also", "another", etc.
2. Extract name, quantity/spec, location, date/shelf life and opening state per item.
3. Build an "item — known fields — missing required fields" table and ask **all** missing questions once.
4. Write all rows after the answer, validate column count/escaping, then recompute together.
5. Resolve relative dates ("next Wednesday", "early December") against today; confirm ambiguous numeric dates such as `11/12`.

## 6. Model routing and performance

| Type | Tasks | Execution / tier |
|---|---|---|
| Deterministic | date math, days, grading, sorting, counts | script, no reasoning |
| Rule-based | CSV append/update, alignment, escaping, templates, fixed phrasing | Lite |
| Light semantics | extraction, date normalization, merged follow-up | Lite |
| Judgment | duplicate disambiguation, contradictory info, intent switches | stronger as needed |
| Generation/analysis | recipes, waste attribution, purchase reports | stronger |

Speed: no mental arithmetic; report only deltas on capture; collapse normal items; avoid rereading the whole table; scheduled runs output only the day's list.

> Automatic model routing is configured in the host agent/workflow, not guaranteed by this file. Set the default node to Lite and use conditional branches for complex generation.

## 7. Output files

| File | Purpose | Format |
|---|---|---|
| `food_inventory.csv` | living ledger | UTF-8 (BOM for Excel) |
| `daily_reminder_YYYYMMDD.md` | daily list | Markdown |
| `waste_report_YYYYMM.md` (optional) | monthly waste stats | Markdown/CSV |

## 8. CSV safety, encoding and column validation

1. Exactly **13 columns** in header order. Read back with a CSV parser after writes; a missing/extra comma shifts dates, status and method (this happened in an early sample: one extra empty column after package expiry moved `status`/`disposal_method`, causing a processed row to alert).
2. Formula injection: prefix cells beginning with `=`, `+`, `-`, `@` with a single quote; apply to negative computed values if the script ever writes them.
3. Quote fields containing commas; double internal quotes (`"` → `""`).
4. Dates `YYYY-MM-DD`; integer day counts; keep units inside the free-text quantity field rather than mixing into numbers.
5. UTF-8; UTF-8 with BOM for Excel-facing files.
6. Use a standard CSV library; do not concatenate rows by hand.

### Canonical headers (English)

`name,category,quantity,storage_location,production_date,shelf_life_days,package_expiry,opened_date,days_after_opening,recorded_date,status,disposal_method,notes`

The scanner also accepts the original Chinese headers and common status aliases (`processed` / `已处理`).

## 9. Edge cases

| Situation | Handling |
|---|---|
| No package date and no production date | `insufficient_info`; ask, never guess |
| Unparseable date | reject the value with a `YYYY-MM-DD` example; script names the row |
| Column count mismatch | warn about shift/unescaped comma; fix before computing |
| Opening date before production date | flag contradiction and ask to verify |
| Opened but no after-opening limit | category default, else ask; temporarily use package date |
| Duplicate entry | show candidates; update or add after confirmation |
| Capture/reschedule during scan | write, recompute, report only the changed group |
| Partial batch info | write complete items; merge missing questions once |
| Expired but still kept | keep alerting with cumulative overdue days |
| Disposal method filled | archive as processed and skip alerts |
| Empty/missing ledger | prompt first entry and template path; script exits clearly |
| Item fully eaten | method `eaten` and archive, or delete after confirmation |
| Missing location | compute normally and prompt for location |
| Python unavailable | manual formulas; disclose speed/accuracy risk |
