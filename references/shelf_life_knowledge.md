# Shelf-Life, After-Opening Limits and Warning Windows

> Generic household reference only. **The package label and storage instructions always win.** When a product says "consume within X days after opening" or "keep refrigerated after opening", use that value.

## 1. Warning windows by total shelf life

The scanner picks the window `w` from total shelf life; category fallbacks are used when the total cannot be inferred.

| Shelf-life tier | Typical foods | Warn ahead `w` | Urgent threshold |
|---|---|---|---|
| Short (≤7 days) | fresh milk, bread, cooked food, leafy greens, fresh meat/fish | 2 days | 1 day |
| Medium (7–30 days) | yogurt, eggs, some fruit, chilled deli | 3 days | 1 day |
| Long (1–12 months) | UHT milk, snacks, condiments, frozen meals, drinks | 7 days | 2 days |
| Extra-long (>1 year) | dried staples, canned goods, honey, salt/sugar | 14 days | 7 days |

The "urgent threshold" is conversational guidance (say "eat today / very soon"); the numeric status is still computed from `remaining_days` and `w`.

## 2. Common categories (unopened / after opening)

Storage: `fridge` (0–4°C), `freezer` (≤-18°C), `ambient` (cool dry place).

| Category | Examples | Unopened guidance | After opening | Storage notes |
|---|---|---|---|---|
| Dairy | fresh/pasteurized milk | by package date (often within days) | 2–3 days, refrigerated | keep sealed; don't return drunk-from cartons long |
| Dairy | yogurt | by package date (~2–3 weeks) | 2–3 days | whey separation is normal; mold/off smell is not |
| Dairy | UHT/sterilized milk | ~6 months ambient | 2–3 days refrigerated | refrigerate after opening |
| Dairy | hard cheese | weeks–months | ~2–4 weeks wrapped | dense cheese may allow cutting mold ≥2 cm around; soft cheese discard if moldy |
| Meat & eggs | eggs | ~30–45 days refrigerated | — (use by date) | store blunt end up; do not wash before storage |
| Meat & eggs | raw poultry/meat | 1–2 days fridge | use same/next day | freeze for longer; thaw once, do not refreeze raw |
| Seafood | fish/shrimp | ~1 day fridge | use same day | freeze for 2–6 months depending on type |
| Deli & soy | cooked meat, braised food, tofu | 1–3 days fridge | same guidance | high risk; reheat thoroughly; discard if slimy/sour |
| Cooked leftovers | rice, dishes | ≤24–48 h fridge (aim 24 h) | — | cool quickly, shallow containers; reheat once to piping hot |
| Produce | leafy greens | 3–5 days fridge | — | wilted is usable if not rotten/slimy |
| Produce | root/tuber (potato, carrot, onion) | weeks in cool dark place | — | potatoes/onions prefer cool dark ambient, not the fridge; discard sprouted/rotten potato |
| Bakery | bread, buns | 3–7 days ambient | seal promptly; freeze for 2–3 months | moldy soft bread: discard whole loaf |
| Staples | rice, flour, dried noodles | 6–18 months dry | reseal; watch for insects/moisture | cool, dry, airtight |
| Snacks | chips, biscuits, nuts | by package (months) | 1–2 months sealed | rancid (oxidized) nuts/oil should be discarded |
| Condiments | soy sauce, vinegar | long ambient | ~1–3 months; refrigerate if label says | high salt/acid; still watch mold/off taste |
| Condiments | oyster sauce, sauces with egg/dairy | by package | **refrigerate after opening**, ~1 month | follow label; do not leave ambient |
| Condiments | peanut/sesame paste | months | ~1–3 months | oil separation is normal; rancid smell means discard |
| Frozen | frozen meals, dumplings | by package (often 3–12 months) | — | keep frozen; avoid repeated thaw cycles and freezer burn |
| Beverages | juice, soft drinks, beer | by package | 1–3 days fridge after opening | carbonation loss and fermentation are signs of decline |
| Canned | meat/fish/fruit cans | 1–3 years | transfer to another container, refrigerate, ~1–3 days | discard if swollen, deeply rusted, dented at seam, or leaking |

These are conservative general values, not safety guarantees. When package instructions differ, follow the package.

## 3. How defaults are applied

1. If the user provides `days_after_opening`, use it.
2. Else use the table above by category/subtype.
3. If no default exists, leave it blank and ask the user; do not invent a precise number.
4. The effective date always takes the earlier of package expiry and after-opening expiry (see `workflow_detail.md`).

## 4. High-risk foods (do not gamble after expiry)

Meat, poultry, seafood, eggs, cooked food, dairy, cut fruit, infant food and anything requiring cold chain can grow pathogens without obvious spoilage signs. For vulnerable groups (infants, pregnant people, older adults, immunocompromised users), use only fresh, correctly stored, in-date food.
