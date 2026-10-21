# Fixes made on top of your v3 (all verified by tests/functional_test.py)

| # | Problem found | Fix |
|---|---------------|-----|
| 1 | Reports trend chart showed revenue 2.3x too high (a JOIN repeated each bill's total once per item) | Three separate queries merged in Python; chart sums now equal the real revenue |
| 2 | Itemized profit ignored the bill discount, so it did not match the Net Profit card | Product revenue is now after discount; table adds up to the headline numbers |
| 3 | Net profit double-penalised returns (refund AND full cost) | profit = revenue - refunds - (cost - cost of returned goods) |
| 4 | App CRASHED when clearing the Products form after choosing a picture | Safe `theme.set_label_image()` helper |
| 5 | Upgrade script reset every cost price of 0 on EVERY launch (and rewrote old cost snapshots) | One-time upgrade, remembered in the settings table |
| 6 | Dashboard refresh timers multiplied each time you opened the page | Only one timer is kept |
| 7 | Idle auto-logout of 0 minutes logged you out every 10 seconds | 0 now means "never" |
| 8 | Non-admins saw placeholder text instead of the real shop settings | Fields are filled even while disabled |
| 9 | "Settings saved" was shown even when MySQL rejected the save | Real success/failure reported; input validated (currency, discount <= 100, ...) |
| 10 | Bangla mode only changed the sidebar and needed a restart | Every label/button/title is translated; window rebuilds instantly; wording fixed |
| 11 | Refund could exceed what the customer actually paid (bill discount ignored) | Default refund = discounted price; larger refunds blocked; deleted products skipped |
| 12 | Purchases: blank dropdowns, product names cut off | "Select" shown, product gets its own full-width row |
| 13 | Reports charts clipped on small windows; "Sold" showed 7.00 | Charts fit the real height, labels use ellipsis, whole numbers |
| 14 | Text cut mid-word on the dashboard (Kawsar Hoq, Electric Kettl); Revenue card clipped | Ellipsis helper, smaller stat-card font |
| 15 | No tests folder | Added unit tests, 64-check functional suite, screenshot script |
