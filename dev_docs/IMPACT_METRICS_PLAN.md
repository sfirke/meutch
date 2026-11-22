# Impact metrics for Meutch

## 1. Goal and context

Report the money and CO2 that Meutch saves:
- **per member:** what they saved, and what they helped others save;
- **site-wide:** totals on the logged-out homepage;
- **per year:** for a later "year in review".

The estimates come from Sam's package `item-appraiser` (PyPI 0.1.0; source at `/home/sam/git/item-appraiser`; read its `README.md` and `src/item_appraiser/{models,policy,climate,claude,deepseek}.py`).

**What the package does:**
- `Listing(name, description, image_urls, item_id)` goes into `appraiser.appraise(listing)`, which returns an `Appraisal`.
- An `Appraisal` stores raw facts: `new_price_usd`, `condition`, `resale_demand`, `confidence`, `assumption`, `quantity`, `unit_new_price_usd`, `footprint_category`, `impacts`, `fingerprint`, `model_version`, `estimated_at`.
- Derived values come from policy functions, so history can be recomputed without re-appraising:
  - `buy_value(new_price_usd, condition, resale_demand)` and `loan_value(buy_value_usd)`
  - `new_item_kg_co2e(new_price_usd, category, quantity)`
  - `giveaway_kg_co2e(new_item_kg, condition)` and `loan_kg_co2e(new_item_kg)`, which is 25% of the new footprint per loan
- Pass `impacts` including `Impact.climate` or no CO2 is computed.
- `appraiser.fingerprint(listing)` vs the stored `appraisal.fingerprint` tells you when an item needs re-appraising.
- Each call takes several seconds and costs about $0.003 (Claude Sonnet) or $0.0003 (DeepSeek Flash). It raises `AppraisalError` on retryable failures. Use a client with `timeout=60`.
- Report the figures as "estimated avoided emissions", never subtracted from anyone's footprint.

**Facts about Meutch that the design depends on** (verified):
- Items are **hard-deleted**, and the delete takes their `LoanRequest`s with them (`app/services/item_service.py:471` `delete_item_with_cleanup`). Account deletion hard-deletes the user's items too (`app/services/account_service.py:76-109`). Users themselves are soft-deleted (`is_deleted`).
- Items have no price or condition fields. Images are in `ItemImage.url`. The category is `Item.category` (required).
- All completions go through three service functions, which both the web views and `app/api/v1` call:
  - `loan_service.complete_loan` (`app/services/loan_service.py:157`)
  - `giveaway_service.confirm_handoff` (`app/services/giveaway_service.py:401`)
  - `giveaway_service.mark_given_away` (`app/services/giveaway_service.py:417`; given away outside the app, `claimed_by_id=None`)
  - A claimed giveaway can't be un-claimed.
- `LoanRequest` has no `completed_at`. `Item.claimed_at` is set on handoff.
- There is no task queue. Scheduled work is a Click command run as a DigitalOcean scheduled job (example: `flask check-loan-reminders`, `app/cli.py:1724`; documented in `DEPLOYMENT.md:246-300`). CLI commands are registered at `app/__init__.py:123-128`.
- The landing page is the `/` route (`app/main/views/browse.py:19`), template `app/templates/main/landing.html`, static, with no stats.
- Migrations use Flask-Migrate/Alembic with date-named revision ids (e.g. `20260925_widen_password_hash.py`), checked by `scripts/check_alembic_revision_ids.py`.

## 2. Decisions already made (don't revisit)
1. **Two tables.**
   - `ItemAppraisal`: one current estimate per item, cascades with the item.
   - `ImpactEvent`: an append-only ledger, one row per completed loan or giveaway. It survives deletion of items, loans and users.
2. **Appraise in a scheduled CLI job**, never inside a web request. Completion hooks only write ledger rows (DB only, no API calls).
3. **Provider:** chosen by env var `IMPACT_APPRAISER_PROVIDER` (`claude` default, or `deepseek`).
4. **No CO2 cap.** Every completed loan counts `loan_kg_co2e`. A future per-pair cap (A lending to B 10x) is out of scope; the ledger keeps `provider_id`/`beneficiary_id` so it can be added later.
5. **No personal totals on profiles yet.** Phase 3 shows site totals only. Per-user queries exist in the service for the later year-in-review.

### Counting rules
| Event | Beneficiary (saved) | Provider (helped others save) | $ | kg CO2e |
|---|---|---|---|---|
| Loan completed | borrower | lender | `loan_value_usd` | `loan_kg_co2e` |
| Giveaway handoff (`confirm_handoff`) | recipient | giver | `buy_value_usd` | `giveaway_kg_co2e` |
| `mark_given_away` (outside the app) | none (NULL) | giver | `buy_value_usd` | `giveaway_kg_co2e` |

Site totals are sums over events, so each event counts once.

## Phase 1: Item appraisals (PR 1)

### Task 1.1: Plan doc (Difficulty: Low)
- Copy this plan to `dev_docs/IMPACT_METRICS_PLAN.md` (dropping sections 3 and 4, which are orchestrator-only).
- Self-check: the file renders; pre-commit passes on it.
- Orchestrator verification: the decisions and counting rules match section 2 exactly.

### Task 1.2: Dependency and config (Difficulty: Low; parallel with 1.3)
- Add `item-appraiser[claude,deepseek]==0.1.0` to `requirements.txt`.
- In `config.py`, add:
  - `IMPACT_APPRAISER_PROVIDER` (default `"claude"`)
  - `ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY` (default None)
  - `IMPACT_APPRAISER_MODEL` (optional override)
- Add the new env vars to `.env.example` if one exists, and to `DEPLOYMENT.md`'s env var list. Don't include any production infrastructure details.
- Self-check: `pip install -r requirements.txt` in the venv succeeds; `python -c "import item_appraiser"` works.
- Orchestrator verification:
  - No key values are committed.
  - The version is pinned.
  - The test config doesn't need a key.

### Task 1.3: `ItemAppraisal` model and migration (Difficulty: High; parallel with 1.2)
- Add to `app/models.py`:
  - `item_id`: FK to `item.id`, unique, `ondelete="CASCADE"`, with an `Item.appraisal` one-to-one relationship.
  - Raw fields: `new_price_usd` (Numeric), `unit_new_price_usd`, `quantity` (Integer).
  - Enum values as short strings: `condition`, `resale_demand`, `confidence`, `footprint_category`.
  - `assumption` (Text), `impacts` (String), `fingerprint` (String, indexed), `model_version` (String), `estimated_at` (DateTime tz-aware, matching the file's convention), `created_at` / `updated_at`.
  - A method `to_appraisal()` that rebuilds an `item_appraiser.Appraisal` through `Appraisal.from_dict(...)`, so derived values always come from the library.
- Write a date-named migration. Upgrade and downgrade must both work.
- Self-check:
  - `flask db upgrade` then `flask db downgrade -1` then `flask db upgrade` on the dev DB.
  - Run `scripts/check_alembic_revision_ids.py`.
  - Add a unit test that round-trips a stub `Appraisal` through the model.
- Orchestrator verification:
  - The migration only touches the new table.
  - Deleting an item removes its appraisal, and the ORM cascade doesn't conflict with `delete_item_with_cleanup`.
  - Enum string lengths fit every `FootprintCategory` value.

### Task 1.4: `impact_service`, appraisal side (Difficulty: Medium; after 1.2 and 1.3)
- New `app/services/impact_service.py` with:
  - `build_appraiser()`: chooses `ClaudeAppraiser` or `DeepSeekAppraiser` from config, `impacts` set to money + climate, and an SDK client with `timeout=60`. Unknown provider → `ValueError`.
  - `listing_for(item) -> Listing`:
    - `name=item.name`
    - `description=f"{item.description}\n\nCategory: {item.category.name}"`
    - `image_urls` = the item's `ItemImage.url`s in order
    - `item_id=str(item.id)`
  - `needs_appraisal(item, appraiser) -> bool`: true if there's no appraisal or its fingerprint differs.
  - `appraise_item(item, appraiser) -> ItemAppraisal`: upserts the row.
  - `appraise_pending(limit, appraiser, dry_run=False) -> summary`:
    - Iterates items needing appraisal, oldest first.
    - Catches `AppraisalError`, logs it, and keeps going.
    - Commits after each item, so partial progress sticks.
    - Dry run returns the count and `appraiser.estimate_cost(listings)` without calling the API.
- Tests: use a stub object that matches the `Appraiser` protocol (returns fixed `Appraisal`s, or raises `AppraisalError` for chosen items). Cover:
  - a new item gets appraised;
  - an unchanged item is skipped;
  - an edited item (new fingerprint) is re-appraised;
  - an error on one item doesn't stop the others;
  - the limit is respected.
- Self-check: targeted tests plus pre-commit.
- Orchestrator verification:
  - No network in tests (grep for real client construction in tests).
  - Fingerprint comparison uses the library's `fingerprint`, not a homemade hash.

### Task 1.5: CLI command and deploy notes (Difficulty: Low; after 1.4)
- Add a `flask impact appraise [--limit N=200] [--dry-run]` Click group/command in `app/cli.py`, registered beside the existing commands. It prints a summary: appraised, skipped, failed, cost.
- Add a `DEPLOYMENT.md` section: a DO scheduled job running `flask impact appraise` hourly, plus the required env vars. Include one-time backfill instructions (`--dry-run` first, then run).
- Tests: a CLI test in `tests/unit/` with the stub appraiser patched into `build_appraiser`, following `tests/unit/test_cli_loan_reminders.py`.
- Orchestrator verification: run `flask impact appraise --dry-run --limit 5` against seeded dev data (`flask seed data`) and check the printed cost estimate looks sane.

**Phase 1 gate:**
- The orchestrator reruns all new and touched test files plus pre-commit on the phase diff.
- With Sam's key set locally, run one real `flask impact appraise --limit 3` and inspect the rows.
- Ask Sam before spending on the API if no key is present.

---

## Phase 2: Impact ledger (PR 2)

### Task 2.1: `ImpactEvent` model and migration (Difficulty: High)
Fields:
- `id`, `kind` (`loan` / `giveaway`), `occurred_at` (indexed)
- FKs, all **nullable, `ondelete="SET NULL"`**:
  - `item_id`
  - `loan_request_id` (unique when not null)
  - `beneficiary_id` and `provider_id` (both indexed)
- Snapshots: `item_name`, `category_name`
- Copied appraisal inputs: `new_price_usd`, `quantity`, `condition`, `resale_demand`, `footprint_category`, `model_version`
- Derived values: `usd_saved`, `kg_co2e_avoided` (Numeric; NULL while pending), `policy_version` (string; set it from the library version)
- For giveaways: a unique constraint on `item_id` where `kind='giveaway'`, so the same handoff can't be recorded twice. Implement it as a partial unique index.

ORM relationships must use `passive_deletes=True` (or no backref cascade), so that `delete_item_with_cleanup` and account deletion leave events in place with NULL FKs. Check that deleting `LoanRequest`s inside `delete_item_with_cleanup` doesn't try to delete events.

- Self-check:
  - upgrade, downgrade, upgrade;
  - revision id check;
  - unit tests: delete an item that has a completed loan and a giveaway event → events remain with `item_id` NULL; soft-delete a user → events remain.
- Orchestrator verification: read the generated SQL (`flask db upgrade --sql`) to confirm `ON DELETE SET NULL` and the partial index are really there.

### Task 2.2: Recording events at completion (Difficulty: High; after 2.1)
- In `impact_service`, add:
  - `record_loan_completed(loan)`
  - `record_giveaway_completed(item, recipient_id)` (recipient may be None)
  - `fill_event(event, appraisal)`: copies the raw fields and computes `usd_saved` / `kg_co2e_avoided` with the library's policy functions per the counting rules.
- If the item has an appraisal, fill the event immediately; otherwise leave it pending.
- Call these from `loan_service.complete_loan`, `giveaway_service.confirm_handoff` and `giveaway_service.mark_given_away`, in the same transaction as the status change. A failure here must never block completion: catch and log `SQLAlchemyError` only around the event insert, using a savepoint (`db.session.begin_nested()`).
- `occurred_at` is the current UTC time. The service functions' existing timestamp style is the convention to match.
- Tests (integration, via both web route and API route for at least one path each):
  - each of the 3 paths creates exactly one event with the correct beneficiary and provider;
  - pending when no appraisal;
  - filled with the correct numbers when there is one (compute the expected values with the same policy functions);
  - completing twice doesn't duplicate.
- Orchestrator verification:
  - Diff the three service functions; the only change is the hook call.
  - Run `tests/integration/test_api_loans.py`, `tests/integration/test_api_giveaways.py`, `tests/functional/test_giveaway_routes.py` (or wherever they live) plus the new tests.

### Task 2.3: Job fills pending events, plus history backfill (Difficulty: Medium; after 2.2)
- Extend `appraise_pending` (or add `fill_pending_events`, called by `flask impact appraise` after appraising) to fill pending events whose item now has an appraisal.
- Events whose item is gone stay pending forever. That's acceptable; they're excluded from totals.
- Add `flask impact backfill-events [--dry-run]`. It creates events for:
  - completed `LoanRequest`s with no event (`occurred_at` = loan `end_date` at noon UTC);
  - claimed giveaways with no event (`occurred_at` = `claimed_at`, or `created_at` if NULL).
  - Running it twice must change nothing.
- Add the totals queries to `impact_service`:
  - `site_totals()` → `(usd, kg, event_count)`, counting only filled events;
  - `user_totals(user_id, start=None, end=None)` → saved / helped-others amounts for $ and kg.
- Tests:
  - pending → filled;
  - the backfill is idempotent;
  - totals math, including an event with a NULL beneficiary, which counts in site and provider totals only.
- Orchestrator verification: run the backfill against seeded dev data, then check `site_totals()` by hand against a SQL SUM.

**Phase 2 gate:** same as Phase 1. Also, by hand on dev:
- complete a loan and hand off a giveaway in the running app (use the `run-meutch` skill), confirm the events appear;
- delete the item, confirm the events survive.

---

## Phase 3: Site totals on the homepage (PR 3)

### Task 3.1: Landing page totals (Difficulty: Medium)
- In the `/` view (`app/main/views/browse.py:19`), pass `site_totals()` to `landing.html`.
- Cache the result for about 1 hour. Use the app's existing caching if there is one; otherwise a small module-level TTL cache in `impact_service`. With 2 gunicorn workers, per-process caching is fine.
- Display: a short band showing "≈ $X saved" and "≈ Y kg CO2e of estimated avoided emissions", with a one-line "how we estimate this" link or tooltip that names the method (estimates from item descriptions; avoided emissions vs buying new). Round sensibly. Hide the band when `event_count` is below a threshold, e.g. 10. Follow `STYLE_GUIDE.md`.
- Tests:
  - the view renders with and without data;
  - the threshold hides the band.
  - Assert on context or visible numbers, not markup structure.
- Orchestrator verification:
  - Screenshot the landing page on phone and desktop with the `run-meutch` skill, before and after.
  - Check it against `STYLE_GUIDE.md`.
  - Attach the screenshots to the PR with `gh pr edit --attach`.
  - Add the CHANGELOG entry with the PR link.

**Phase 3 gate:** tests plus pre-commit; screenshots reviewed; CHANGELOG entry present.

---

## Phase 4 (later, not in this run): year in review
Build it on `user_totals(user_id, start, end)` and `ImpactEvent.occurred_at`. This will be the first place members see their personal numbers. Plan it separately.

## Out of scope
- CO2 caps of any kind, including the per-pair cap.
- Personal totals on `/profile` or `/user/<id>`.
- Mobile app changes.
- Task queues.
