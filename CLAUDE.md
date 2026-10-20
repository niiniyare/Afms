# CLAUDE.md: Forecourt Management System (FMS) on Frappe/ERPNext

This file is the standing brief for Claude Code and for human developers working in this repository. Read it before every task. It replaces the Odoo-era CLAUDE.md, which belongs to the old `fms` prototype repository.

---

## 1. What this project is

A forecourt (fuel station) management app, `forecourt`, built on **Frappe Framework v16 + ERPNext v16** (HRMS v16 optional). It serves many stations owned by different companies, dealers and investors. Station managers post each shift after it ends. The system checks that fuel and money are all there, then turns the shift into ordinary ERPNext accounting and stock entries that directors can see across stations.

The three questions every feature serves:

1. **Is the fuel all there?** (wetstock: tanks, dips, deliveries, meters)
2. **Is the money all there?** (shift and cashier reconciliation)
3. **What did we earn, owe and are owed?** (ERPNext accounting, group reporting)

## 2. Documents (read in this order)

| Document | Use it for |
|---|---|
| `docs/FMS_ERPNext_Design_Guide.md` | Behaviour, business rules, formulas, gates, error codes |
| `docs/FMS_DocType_Catalogue.md` | Exact DocTypes, fields, naming, permissions, custom fields, workspaces. **Authoritative for names.** |
| `docs/FMS_Development_Tasks.md` | The task list and the project's progress. Work only on tasks listed there. |
| `CLAUDE.md` | These rules |

If the design guide and the catalogue disagree on a **name**, the catalogue wins. If they disagree on **behaviour**, the design guide wins. If a task needs something neither covers, stop and ask the owner. Do not invent behaviour.

## 3. Stack and versions

| Component | Version |
|---|---|
| Frappe Framework, ERPNext, HRMS | `version-16` branches |
| Python | 3.14+ |
| Node.js | 24+ |
| Database | MariaDB (as required by v16) |
| Dev site / test site | `fms.localhost` / `test_fms` |

## 4. Skills: use the Frappe Claude Skill Package

The project skills in `.claude/skills/` come from the Frappe Claude Skill Package (Impertio-Studio / OpenAEC-Foundation, version pinned in `.claude/skills/VERSION`). **Load the skills a task lists before writing code.** When a task lists none, pick from this table:

| Work | Skills |
|---|---|
| Unclear requirement | `frappe-agent-interpreter` |
| App structure, modules, fixtures, patches | `frappe-impl-customapp`, `frappe-syntax-customapp` |
| DocType JSON | `frappe-syntax-doctypes` |
| Python controllers | `frappe-syntax-controllers`, `frappe-impl-controllers`, `frappe-errors-controllers` |
| hooks.py, doc_events on ERPNext DocTypes | `frappe-syntax-hooks`, `frappe-syntax-hooks-events`, `frappe-impl-hooks`, `frappe-errors-hooks` |
| Form JavaScript | `frappe-syntax-clientscripts`, `frappe-impl-clientscripts`, `frappe-errors-clientscripts` |
| Whitelisted methods and API | `frappe-syntax-whitelisted`, `frappe-impl-whitelisted`, `frappe-core-api`, `frappe-errors-api` |
| Database and queries | `frappe-core-database`, `frappe-syntax-query-builder`, `frappe-errors-database` |
| Permissions | `frappe-core-permissions`, `frappe-errors-permissions` |
| Workflows | `frappe-core-workflow`, `frappe-impl-workflow` |
| Reports, number cards, charts | `frappe-syntax-reports`, `frappe-impl-reports` |
| Workspaces | `frappe-impl-workspace` |
| Print formats | `frappe-syntax-print`, `frappe-syntax-jinja`, `frappe-impl-jinja` |
| Background jobs, scheduler | `frappe-syntax-scheduler`, `frappe-impl-scheduler` |
| Integrations | `frappe-impl-integrations`, `frappe-core-api` |
| Tests | `frappe-testing-unit`; CI: `frappe-testing-cicd` |
| Debugging | `frappe-agent-debugger`, then the matching `frappe-errors-*` skill |
| Review before commit | `frappe-agent-validator` |
| Deployment and ops | `frappe-ops-*` |

**Do not use Server Scripts or Client Scripts stored in the database.** All code lives in the app (controllers, `hooks.py`, form JS files) so it is versioned and tested.

## 5. Architecture rules (non-negotiable)

1. **One app, no core overrides.** Never use `override_doctype_class` or `extend_doctype_class` on ERPNext DocTypes, and never patch ERPNext code. Extend ERPNext with custom fields (fixtures) and `doc_events` in `hooks.py`.
2. **Standard documents for money and stock.** Every money or stock movement is a native ERPNext document (Sales Invoice, Payment Entry, Journal Entry, Stock Entry, Stock Reconciliation, Purchase Receipt). No custom GL or stock posting. No parallel bookkeeping.
3. **Pure calculations.** All arithmetic lives in `forecourt/calc/` with **no `frappe` imports**, tested with unit tests. Controllers call `calc`, never re-implement formulas.
4. **One place for posting.** Native documents are built only in `forecourt/posting/` (one function per generated document). Corrections live in `forecourt/corrections/`.
5. **Atomic close.** Shift close posts everything in one transaction (or one background job transaction for large shifts). **Never call `frappe.db.commit()`** in controllers, hooks or posting code; v16 forbids commits in document hooks anyway.
6. **Append-only ledgers.** Wetstock, Nozzle, Sales and Cashier Ledger Entries are written only by `posting/ledgers.py` and correction code. They are never edited. Cancellation sets `is_cancelled`; corrections set `superseded_by` and write new rows.
7. **Closed shifts are corrected, never edited.** All fixes go through Shift Correction with director approval (design guide 6.8). Generated documents refuse direct cancellation unless `frappe.flags.fms_correction` is set by correction code.
8. **Every variance is cleared before close.** No "pending" states, no "close anyway". Gates live in `before_submit` and raise coded errors from `forecourt/errors.py`.
9. **Enter once.** Anything the system knows (openings, roster, prices, GRNs, own use, POS sales, imported payments) is pulled in, never typed again.
10. **Every record carries `company` and `station`.** Documents generated by a shift also carry `fms_forecourt_shift`. No tenant field: Company is the tenant.
11. **Jurisdiction-neutral core.** No country names, tax rates or provider names in core code. Countries and providers live in settings, fixtures and adapters (`forecourt_integrations/payment_adapters/`, `fiscal_adapters/`).
12. **Manual GRNs.** The FMS never creates Purchase Receipts. It adds delivery dips to the GRN form, validates them, and reads submitted GRNs.

## 6. Conventions

| Topic | Rule |
|---|---|
| Custom fields on ERPNext DocTypes | Prefix `fms_`, shipped as fixtures filtered by FMS modules |
| DocType names | As in the catalogue; never rename without updating the catalogue in the same pull request |
| Document names | Include the station code (`SH-KE-NBO-WSTL-2026-00042`) |
| Error messages | Coded (`FMS-S105`), plain language, with the fix. Add new codes to `forecourt/errors.py` **and** the design guide's error catalogue |
| Translations | Wrap every user-facing string: `_()` in Python, `__()` in JavaScript |
| Types | Type annotations on new Python functions (v16 practice) |
| Permissions | `has_permission` hooks return explicit `True`/`False` (v16) |
| Sorting | v16 lists sort by `creation` by default; set `sort_field` explicitly where the catalogue says |
| SQL | Prefer `frappe.qb` or `frappe.get_all`; never format user input into SQL strings |
| `ignore_permissions` | Only for ledger writes and system-generated documents in `posting/` and `corrections/` |
| Money and quantities | `flt(value, precision)` with the field's precision; never compare floats without rounding |
| Time | Shift windows in the station's time zone; store datetimes in system time zone as Frappe does |

## 7. Working on a task

1. Pick the next unticked task from `docs/FMS_Development_Tasks.md` whose dependencies are ticked, or the one the owner names.
2. Create the branch `task/FMS-X00-short-name`.
3. Load the listed skills. Re-read the relevant design guide and catalogue sections.
4. Implement the smallest change that meets the task's **Expectation**. Do not widen the task. Log anything else you notice in the Bug log.
5. Write or update tests in the same change.
6. Run the checks below. Run every CLI step in the task's **Verify** that you can run, and list the UI steps the owner must check.
7. Run a `frappe-agent-validator` review of the changed files and fix errors.
8. Tick the task's checkbox and update the Progress table in the same commit.
9. Commit with the task format, push, open a pull request whose description lists the Verify steps and their results.

Never tick a task whose Verify steps have not been run. If a UI step is still waiting for the owner, say so in the pull request and leave the box unticked.

## 8. Commands

```bash
# run the dev server
bench start

# apply DocType/fixture changes
bench --site fms.localhost migrate
bench --site fms.localhost clear-cache

# export fixtures after changing custom fields, roles, workflows, workspaces
bench --site fms.localhost export-fixtures --app forecourt

# tests (test site has allow_tests = true)
bench --site test_fms run-tests --app forecourt
bench --site test_fms run-tests --app forecourt --doctype "Forecourt Shift"
bench --site test_fms run-tests --app forecourt --module forecourt.tests.test_shift_scenarios

# lint and format
pre-commit run --all-files

# build assets after JS/CSS changes
bench build --app forecourt

# inspect
bench --site fms.localhost console
bench --site fms.localhost mariadb
bench --site fms.localhost execute forecourt.path.to.function
```

Logs: `logs/` in the bench (`web.error.log`, `worker.error.log`, `frappe.log`) and the *Error Log* DocType.

## 9. Testing rules

- `calc/` has unit tests for every function, including edge cases (rollover, zero sales, tolerance boundaries, rounding).
- Each DocType has an integration test (`IntegrationTestCase`) built on `forecourt/tests/factories.py`. Never depend on data left by another test.
- Posting tests assert **balances**, not just document counts: till equals counted cash, receivables equal credit slips, tank stock equals dips, ledger totals equal report totals.
- A bug fix starts with a failing test that reproduces it.
- The golden-month scenario (task K01) must pass before any release.

## 10. Domain terms

| Term | Meaning in this codebase |
|---|---|
| Station | A physical site; an Accounting Dimension |
| Fuel Tank | A tank; one ERPNext Warehouse per tank |
| Dispenser / Nozzle | Pump / hose; a nozzle draws from one tank |
| E-cash, E-vol, M-vol | Electronic cash, electronic volume and manual (mechanical) volume meters |
| Sales basis | The meter that drives sales (default E-cash; may be *Highest*) |
| Drift | Difference between meters on the same nozzle |
| Price segment | Part of a shift with one price for an item |
| Cashier | The person accountable for money (UI label may be *Salesperson*) |
| Collection | One payment transaction or cash movement on a cashier |
| Resolution | The line that clears a cash difference or tank variance |
| GRN | ERPNext Purchase Receipt for a fuel delivery, posted manually, carrying delivery dips |
| Fuel Own Use | Stock Entry type for the station's own fuel consumption |
| Shift Correction | The only way to change a closed shift; needs director approval |

## 11. Owner decisions in force

- Accountability is per cashier; sales and payments are also reported per product, tank, pump, nozzle and shift (payment attribution is marked Exact or Attributed).
- Every variance is cleared before close.
- Fuel GRNs are posted manually.
- Dip entry: calibration chart or litres entered directly, per station and tank.
- Meters: default E-cash only; stations may record all three and choose the basis, including *Highest*.
- Prices: latest posted price applies immediately, with price segments in the shift (or between shifts only, by setting).
- Own use is a *Fuel Own Use* Stock Entry with narration, reference, shift and attendant.
- Corrections: targeted, director-approved; native documents are cancelled and amended individually; FMS data is superseded, never edited.
- Mobile money and card payments are posted one transaction per Payment Entry, with the provider reference.
- Shift link on the native documents the FMS posts or reads; Station as accounting dimension; no tenant field.
- **Still open:** deployment model (one shared site, separate sites with a group site, or a mix). Keep code compatible with both (design guide 4.2a).

## 12. Do not

- Do not modify files under `apps/frappe`, `apps/erpnext` or `apps/hrms`.
- Do not create DocTypes, fields or reports that are not in the catalogue without updating the catalogue in the same pull request and getting the owner's approval.
- Do not store secrets in the repository or in fixtures. Provider credentials go in site config or encrypted Password fields.
- Do not use `frappe.db.sql` with string formatting, `frappe.db.commit()` in request code, or `ignore_permissions` outside `posting/` and `corrections/`.
- Do not tick tasks for work that was not verified.

