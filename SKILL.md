---
name: Smart Pantry & Expiry Reminder
description: Maintain a household grocery ledger, compute the effective expiry date from package date and after-opening limits, and send tiered daily alerts (expiring soon, due today, expired) with safe disposal and reuse suggestions. Supports instant capture during a scan, batch colloquial entry, and deterministic local calculation. Use for fridge clean-out, "what should I eat today", reducing food waste, replenishment lists, and grocery inventory. 触发词：food expiry, expiration reminder, best before, use-by date, shelf life, expiring soon, fridge check, what to eat today, clear the fridge, grocery inventory, food ledger, restock, replenishment, expired food, food waste, 食品过期, 临期提醒, 保质期, 冰箱整理, 今天吃什么, 补录, 刚买了.
---

# Smart Pantry & Expiry Reminder

## Overview

Help users track groceries, calculate effective expiry dates (including the earlier after-opening deadline), run tiered daily scans, capture items instantly during a scan, and give safe handling/reuse advice. The goal is less food waste and safer eating, while producing structured inventory data that can drive replenishment and shopping decisions.

## Target users

- Households, renters and students who stock food and forget dates.
- People who want "eat this first" guidance and less waste.
- Shopping-agent workflows that need an inventory/replenishment layer.

## Capabilities

| Capability | Description |
|---|---|
| Entry & maintenance | Single or batch colloquial entry; name, category, quantity, location, dates, opening info |
| Fast calculation | Prefer `scripts/expiry_calc.py` for dates, grading and sorting — no LLM arithmetic |
| Tiered alerts | expired / due today / soon / normal, sorted by urgency |
| Instant capture | Add or update during a scan, recompute, report only the changed item |
| Handling advice | Safety judgment, discard vs reuse, waste sorting |
| Archive & stats | Record actual handling method for later waste analytics |

## Trigger phrases

- Entry: add food, log groceries, batch entry, just bought, restock, 录入食品, 补录, 刚买了, 批量录入.
- Query: what to eat today, eat first, what is in the fridge, clear the fridge, 今天吃什么, 清冰箱, 冰箱整理.
- Alert: expiring soon, use-by, shelf life, expiry reminder, 临期, 保质期, 过期提醒.
- Handling: is it still edible, what to do with expired food, reuse, 过期了怎么办, 废物利用.

## Workflow

### 1. Enter items (single or batch)

1. Extract one or more items from the utterance. For each: name, category, package expiry (or production date + shelf-life days); optional quantity, location, opened date and after-opening limit.
2. For multiple items, merge all missing required fields into **one** follow-up question; do not interrogate item by item.
3. Write exactly the 13 columns in `templates/food_inventory_template.csv`; verify column count and CSV escaping.
4. After writing, run `expiry_calc.py --focus "<name>"` to confirm the computed date.

Example:
> User: Just got a 1L milk, keep chilled, expires Nov 25, and a loaf of bread.
> Assistant: Logged fresh milk (fridge, effective 2026-11-25). What is the bread's expiry date or shelf life?

### 2. Daily scan (scheduled or manual)

Prefer the deterministic script:

```bash
python3 scripts/expiry_calc.py --csv <ledger>/food_inventory.csv --format md
```

- Use `--date YYYY-MM-DD` to reproduce a day; `--focus "<keyword>"` for one item; default output is JSON.
- Only fall back to the formulas in `references/workflow_detail.md` if Python is unavailable, and tell the user it may be slower.
- A daily scheduled run (e.g. 08:00) is recommended. Without scheduling, "what should I eat" triggers the same scan manually.

### 3. Tiered list + capture prompt

Output order: expired → due today → soon → normal (the script already sorts). Each line has name, category, location, days left/expired and suggested action.

Always end with:
> "Anything you just bought or forgot to log? Tell me and I'll add it and refresh the list."

### 4. Instant capture & incremental refresh (key loop)

When the user remembers an item during or after the scan:

1. Decide **update vs add**: match by normalized name, quantity and location. If the same item gets an expiry date, opening info, quantity or location, update it; otherwise append. Ask the user to disambiguate when unsure.
2. Write the CSV, rerun the script (use `--focus` to verify).
3. Report **only the added/changed item**, its effective date and its group; explicitly call out a status jump (e.g. normal → soon). Do not re-dump the unchanged list.
4. If data is still insufficient, state exactly which field is missing.

Goal: within one turn, "report groceries → saved → latest alert visible", without asking the user to restart the scan.

### 5. Handling & reuse

For expired or soon items, apply the safety judgment first. Red lines, category reuse and waste sorting live in `references/disposal_reuse_guide.md`.

### 6. Archive & analytics

After the user handles an item, fill `disposal_method` (eaten / discarded / reused) and set status `processed`; the scanner skips rows with a disposal method. Archived rows can feed a monthly waste report.

## Performance & model routing

Most operations are deterministic; default to a Lite model.

| Task | How | Tier |
|---|---|---|
| Date math, days, grading, sorting, counts | `expiry_calc.py` | no reasoning / Lite |
| CSV read/write, alignment, escaping, templates, fixed phrasing | rules | Lite |
| Single-item extraction, date confirmation | simple extraction | Lite |
| Batch colloquial parsing, merged missing-field question | light semantics | Lite |
| Fuzzy disambiguation, multi-turn correction | on demand | stronger |
| Recipes, waste attribution reports, purchase analysis | generation/analysis | stronger |

Speed rules: do not reprint the whole ledger; collapse normal items; on capture, recompute and report only changes; read only needed columns.

> The skill can prescribe efficient behavior but **cannot force the host platform to switch models**. If the host exposes a default model or conditional workflow routing, set simple nodes to Lite and reserve a stronger model for recipes/reports. If it still feels slow, check whether the script is actually used and whether a strong model is doing arithmetic.

## Data storage

- Ledger: `food_inventory.csv` (13 columns; see template). English or Chinese headers are both accepted by the script.
- Daily list: `daily_reminder_YYYYMMDD.md`; optional monthly report `waste_report_YYYYMM.md`.
- UTF-8 (with BOM for Excel); formula-injection defense and escaping in `references/workflow_detail.md`.
- Shelf-life defaults: `references/shelf_life_knowledge.md`; the package label always wins.

## Scheduling

Recommend a daily 08:00 scan. Confirm scheduling support before promising push notifications; otherwise degrade honestly to manual trigger.

## Edge cases

Missing/contradictory dates, opened items without a limit, duplicates, expired-but-kept rows, empty/missing ledger, unavailable runtime, and partial batch entry are covered in `references/workflow_detail.md`.

## Privacy & safety

- Only food data the user actively enters; no identity fields.
- No platform credentials, no web scraping, no simulated login, no automated payment.
- Data stays in the local authorized directory and can be deleted anytime.
- Food advice is general; moldy, swollen, foul-smelling or high-risk food should be discarded.

## Do not

1. Scrape e-commerce/food platforms, simulate logins, or handle credentials/payments.
2. Do date arithmetic by hand when the script exists; never invent dates — mark insufficient info.
3. Suggest eating moldy/swollen/off-smelling/high-risk expired food.
4. Create duplicate rows on capture; update when it is the same item.
5. Read files outside the authorized directory or modify anything except the ledger.

## Acceptance criteria

1. Single and batch entry write correct, aligned, escaped rows and confirm.
2. Effective date, remaining days, grading and sorting are correct (earlier after-opening date; processed skipped).
3. Daily list has no missing groups and no duplicated normal block.
4. **In-scan capture writes, recomputes and inserts the changed item without a restart.**
5. Handling advice follows the safety guide and is traceable.
6. Routine scans use the script/Lite; CSV opens cleanly in Excel.
7. Processed rows archive correctly; duplicates update instead of append.
