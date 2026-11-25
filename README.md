# Smart Pantry AI — Expiry-Aware Grocery Copilot

> A conversational **Agent Skill** that turns a household grocery ledger into timely *use-first* and *replenish* decisions — and the inventory/expiry engine for a shopping copilot.

![python](https://img.shields.io/badge/Python-3.8%2B-blue) ![skill](https://img.shields.io/badge/Agent-Skill-7c3aed) ![license](https://img.shields.io/badge/License-MIT-green) ![data](https://img.shields.io/badge/data-local%20CSV-success)

---

## 1. Why this exists

People do not waste food on purpose — they lose track of it. Three things make expiry hard to manage mentally:

1. The **real deadline is often earlier than the package date** once a product is opened (e.g. milk lasts 2–3 days after opening even if the carton date is next month).
2. Warning windows differ by category: fresh milk needs a 2-day heads-up; a bottle of soy sauce does not.
3. "**What should I eat today?**" and "**What do I need to rebuy?**" are daily decisions that depend on what is actually in the fridge.

For a shopping agent, the same data matters: recommending products without knowing current inventory causes duplicate purchases and misses the right replenishment moment. Smart Pantry AI is the **inventory layer** that connects *buying* to *using*.

## 2. What it does today

- Maintains a 13-field grocery ledger in plain CSV (works with Excel).
- Computes the **effective expiry date**:
  `effective = min(package_expiry, opened_date + days_after_opening)`.
- Applies **category-aware warning windows** (short / medium / long / extra-long shelf life).
- Runs a daily scan sorted by urgency: **expired → due today → expiring soon → normal**.
- Supports **in-scan capture**: add or update an item the moment the user remembers it, recompute, and insert only the changed item into the list — no need to restart the scan.
- Parses **batch colloquial entry** ("bought apples, cucumbers and orange juice…") and asks all missing questions in one turn.
- Provides a safety-first **disposal & reuse guide** (red lines, composting/cleaning reuse, waste sorting).
- Logs how each item was handled (eaten / discarded / reused) for later waste analytics.
- Ships a **deterministic local calculator** (`scripts/expiry_calc.py`) so date math, grading and sorting do not consume LLM tokens or depend on the model's arithmetic. A documented **Lite-model routing table** keeps the agent fast and cheap.

## 3. How it fits a shopping copilot

The long-term product loop this project is designed to support:

```text
 Current stock & expiry
        │
        ▼
 Use-first meals + replenishment list
        │
        ▼
 Compare options (user-provided / public info only)
        │
        ▼
 User decides & checks out  ── (agent never handles login or payment)
        │
        ▼
 Stock-in new items → expiry tracking starts again
```

The current release implements the **left side (stock, expiry, use-first)**. The shopping side is intentionally designed around compliance: no account login, no scraping behind login walls, no automated checkout. Price-tracking and multi-criteria comparison can be added as a companion module using the same CSV-state pattern (see Roadmap).

## 4. Quick start

No dependencies beyond the Python standard library.

```bash
# Markdown reminder list for a fixed date (reproducible demo)
python3 scripts/expiry_calc.py \
  --csv examples/sample_inventory.csv \
  --date 2026-11-24 \
  --format md

# Structured JSON (default), useful for agents
python3 scripts/expiry_calc.py --csv examples/sample_inventory.csv --date 2026-11-24

# Recompute just one item right after the user adds/updates it
python3 scripts/expiry_calc.py --csv my_pantry.csv --focus "milk"
```

Example output (from the bundled sample, base date 2026-11-24):

```markdown
# Food Expiry Reminder (2026-11-24)

## Expired (2) | handle soon
- Spinach (produce, fridge): expired 2 day(s) ago, effective date 2026-11-22
- Canned luncheon meat (deli/soy, ambient): expired 1 day(s) ago, effective date 2026-11-23

## Due today (1) | eat today
- Whole-wheat bread (bakery, ambient): due today (2026-11-24)

## Expiring soon (2) | prioritize
- Fresh milk (dairy, fridge): 1 day left, effective date 2026-11-25
- Plain yogurt (dairy, fridge): 1 day left, effective date 2026-11-25
```

The archived "processed" row (discarded spoiled milk) is automatically excluded.

## 5. Repository structure

```text
smart-pantry-ai/
├── SKILL.md                              # Agent skill definition: triggers, workflow, routing, safety
├── README.md
├── LICENSE
├── .gitignore
├── templates/
│   └── food_inventory_template.csv       # 13-column empty ledger (English headers)
├── examples/
│   ├── sample_inventory.csv              # 8 rows covering every status
│   └── test_scenario.md                  # 6 positive / 3 negative test cases
├── references/
│   ├── shelf_life_knowledge.md           # category shelf life, after-opening limits, windows
│   ├── disposal_reuse_guide.md           # safety red lines, reuse, sorting, disclaimer
│   └── workflow_detail.md                # formulas, incremental update, CSV safety, edge cases
└── scripts/
    └── expiry_calc.py                    # deterministic scanner (EN/CN headers, JSON/Markdown)
```

## 6. Core rules

**Effective expiry**

```text
package_expiry  = package date, or production_date + shelf_life_days
opened_expiry   = opened_date + days_after_opening
effective_expiry = min(package_expiry, opened_expiry)   # only when opened
remaining_days  = effective_expiry - today
```

**Status**

| Condition | Status |
|---|---|
| marked processed / disposal method filled | `processed` (excluded from alerts) |
| `remaining < 0` | `expired` |
| `remaining = 0` | `due_today` |
| `0 < remaining <= warning_window` | `soon` |
| `remaining > warning_window` | `normal` |
| no computable date | `insufficient_info` |

Default windows by total shelf life: ≤7 days → 2; ≤30 → 3; ≤365 → 7; longer → 14. Category fallbacks are in `references/shelf_life_knowledge.md`.

## 7. AI-product thinking & evaluation

- **Scenario-first**: built for households, renters and students who over-buy and lose track, not as a generic chatbot.
- **Deterministic core**: date math and sorting are code, which makes outputs testable and cheap; the LLM handles language, extraction and ambiguity.
- **Model routing**: simple extraction/CSV work stays on a Lite model; only disambiguation, recipe generation and waste reports escalate. See `SKILL.md`.
- **Regression scenarios**: `examples/test_scenario.md` defines 6 positive cases (entry, scan, disposal advice, **in-scan capture**, batch entry, script regression) and 3 negative cases (no login/scraping, out-of-scope, unsafe food advice).
- **Failure handling**: missing/contradictory dates, opened items without a limit, duplicate entries, CSV column misalignment and unavailable runtimes all have explicit fallbacks.

## 8. Privacy, safety and boundaries

- Only food information actively entered by the user is stored; no name, phone, address or identity fields.
- Data stays in a local user-authorized CSV; nothing is uploaded to a third party.
- The skill never asks for shopping-platform credentials, never scrapes behind login, and never automates payment.
- Food-safety output is general guidance, not a substitute for professional judgment. Moldy, swollen, foul-smelling or high-risk expired food should be discarded; when in doubt, throw it out.

## 9. Roadmap

- [ ] Replenishment list generated from low stock + use-first items
- [ ] Recipe matching for ingredients that are expiring soon
- [ ] Optional price-tracking module (threshold-based CSV state, user-provided prices)
- [ ] Monthly waste & savings report
- [ ] Barcode / receipt import (user-initiated, local parsing)
- [ ] More languages and regional food-sorting rules

## 10. License

[MIT](LICENSE). Food-safety guidance is provided as-is; use judgment for vulnerable groups (children, pregnant people, older adults, immunocompromised users).
