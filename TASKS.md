# FMS Development Tasks

**This file is the progress indicator of the project.** Every piece of work is a task with a checkbox. A task is ticked only when its deliverable has been verified (through the UI or the CLI, as stated in the task) and committed.

**Version:** 1.1 (documentation review: repository, forward links, approval workflow, proposed decisions) · **Date:** 2026-10-20
**Stack:** Frappe Framework v16, ERPNext v16, HRMS v16 (optional), app `forecourt`
**Repository:** [niiniyare/Afms](https://github.com/niiniyare/Afms), which is also the app repository (the `forecourt` app sits at its root)
**Specs:** [docs/fms.md](docs/fms.md) (design guide: behaviour) · [docs/catalogue.md](docs/catalogue.md) (DocTypes, fields, workspaces) · [CLAUDE.md](CLAUDE.md) (rules for developers and agents)
**Agent skills:** [Frappe Claude Skill Package](https://github.com/Impertio-Studio/Frappe_Claude_Skill_Package) (now published as `OpenAEC-Foundation/Frappe_Claude_Skill_Package`), installed as project skills in `.claude/skills/`

---

## Progress

| Section | Tasks | Done |
|---|---|---|
| A. Environment | 9 | 9 |
| B. Repository and app scaffold | 9 | 8 |
| C. Foundation masters (Phase 0) | 14 | 13 |
| D. Calculation core | 8 | 0 |
| E. Station movements | 10 | 0 |
| F. Forecourt Shift (Phase 1 core) | 18 | 0 |
| G. Shift Correction | 6 | 0 |
| H. Reports and workspaces | 12 | 0 |
| I. Approvals, roles and permissions | 6 | 0 |
| J. Payment import and integrations | 8 | 0 |
| K. Quality, scenarios and UAT | 7 | 0 |
| L. CI/CD | 4 | 0 |
| M. Deployment and operations | 8 | 0 |
| N. Pilot and go-live | 5 | 0 |
| **Total (Phases 0–3)** | **124** | **30** |
| P. Later phases (backlog) | 8 epics | — |

Update the *Done* column in the same commit that ticks a task.

---

## How to use this file

### Task format

```
- [ ] **FMS-X00 · Type · Title** · Size · Depends on
  - **Skills:** frappe-… skills Claude Code must load before starting
  - **Description:** what to build
  - **Expectation:** the behaviour that must be true when done
  - **Deliverables:** files and records produced
  - **Verify:** the UI steps or CLI commands that prove it (you run these)
  - **Commit:** the commit message subject
```

**Types:** Initialize · Configure · Prototyping · Writing Feature · Writing Test · Fixture · Refactor · Bug fix · Documentation · Review · Deploy.

**Sizes:** S (up to 2 hours) · M (up to 1 day) · L (up to 3 days). Anything bigger is split before starting.

### Definition of done (every task)

1. The *Verify* steps pass, in the UI or CLI as written.
2. `bench --site fms.localhost migrate` runs clean, and the app's tests pass: `bench --site test_fms run-tests --app forecourt`.
3. `pre-commit run --all-files` is clean (ruff, eslint, prettier).
4. The `frappe-agent-validator` skill review of the changed files reports no errors.
5. Committed on a feature branch with the task ID in the message, then merged by pull request.
6. The checkbox is ticked and the Progress table updated in the same commit.

### Working with Claude Code

- Start each task by saying: *"Do task FMS-X00 from TASKS.md."* Claude Code reads [CLAUDE.md](CLAUDE.md), loads the listed skills, implements, runs the Verify CLI steps it can run, and reports which UI steps you need to check.
- One task per branch: `task/FMS-X00-short-name` (unless the session names another branch). One task per pull request, unless tasks are marked as a pair.
- When a task builds a decision marked **Proposed** in design guide section 19, say so in the pull request.
- When a task reveals a bug in earlier work, add a **Bug fix** task to the [Bug log](#bug-log) at the bottom rather than silently widening the current task.

### Commit format

```
<type>(<module>): <subject>

Task: FMS-X00
Verify: <what you checked>
```

Types: `feat`, `fix`, `test`, `chore`, `docs`, `refactor`, `ci`. Modules: `setup`, `wetstock`, `shift`, `finance`, `integrations`, `reports`, `env`, `ci`, `deploy`.

---

## A. Environment

- [x] **FMS-A01 · Initialize · Install system prerequisites** · S · —
  - **Skills:** `frappe-ops-bench`, `frappe-ops-upgrades` (version requirements)
  - **Description:** On the development machine (Ubuntu 24.04 or newer, macOS, or WSL2), install the versions Frappe v16 requires: Python 3.14+, Node.js 24+, Yarn, MariaDB (the version listed in the v16 install notes), Redis, git, and the PDF prerequisites listed for v16. Use `uv` or `pyenv` for Python and `nvm` for Node so other projects are not affected.
  - **Expectation:** All tools report the required versions.
  - **Deliverables:** A short `docs/dev-setup.md` in this repository (added in B03) listing exact versions installed.
  - **Verify:** `python3.14 --version`, `node --version` (v24.x), `yarn --version`, `mariadb --version`, `redis-server --version`.
  - **Commit:** none (documented in B03).

- [x] **FMS-A02 · Configure · Configure MariaDB for Frappe** · S · A01
  - **Skills:** `frappe-ops-bench`, `frappe-ops-performance`
  - **Description:** Set `character-set-server = utf8mb4`, `collation-server = utf8mb4_unicode_ci`, and the `[mysql] default-character-set = utf8mb4` client setting. Set a root password.
  - **Expectation:** MariaDB restarts with utf8mb4 defaults.
  - **Verify:** `mariadb -uroot -p -e "SHOW VARIABLES LIKE 'character_set_server';"` → `utf8mb4`.
  - **Commit:** none.

- [x] **FMS-A03 · Initialize · Install bench CLI** · S · A01
  - **Skills:** `frappe-ops-bench`
  - **Description:** Install `frappe-bench` with `uv tool install frappe-bench` (or `pipx`).
  - **Verify:** `bench --version` prints a version.
  - **Commit:** none.

- [x] **FMS-A04 · Initialize · Create the v16 bench** · S · A02, A03
  - **Skills:** `frappe-ops-bench`
  - **Description:** `bench init --frappe-branch version-16 frappe-bench`, then inside it `bench get-app --branch version-16 erpnext` and `bench get-app --branch version-16 hrms`.
  - **Expectation:** Bench builds assets without errors.
  - **Verify:** `ls apps` → `frappe erpnext hrms`; `bench version` shows 16.x for all three.
  - **Commit:** none.

- [x] **FMS-A05 · Initialize · Create the development site** · S · A04
  - **Skills:** `frappe-ops-bench`
  - **Description:** `bench new-site fms.localhost --db-root-password … --admin-password …`, then `bench --site fms.localhost install-app erpnext hrms`, `bench --site fms.localhost set-config developer_mode 1`, `bench use fms.localhost`.
  - **Expectation:** The site opens and the ERPNext setup wizard appears.
  - **Verify (UI):** `bench start`, open http://fms.localhost:8000, log in as Administrator.
  - **Commit:** none.

- [x] **FMS-A06 · Configure · Complete the ERPNext setup wizard with test data** · S · A05
  - **Description:** Company *Demo Petroleum Ltd* (Kenya, KES, standard chart of accounts), fiscal year, one admin user. Do not create demo data.
  - **Verify (UI):** Desk opens with the Accounting, Stock and Selling workspaces; Chart of Accounts shows the company.
  - **Commit:** none.

- [x] **FMS-A07 · Initialize · Create the test site** · S · A05
  - **Skills:** `frappe-testing-unit`
  - **Description:** `bench new-site test_fms …`, install erpnext and hrms, `bench --site test_fms set-config allow_tests true`. This site is only for automated tests.
  - **Verify:** `bench --site test_fms run-tests --app erpnext --module erpnext.accounts.doctype.account.test_account` passes (smoke test of the test runner).
  - **Commit:** none.

- [x] **FMS-A08 · Initialize · Install Claude Code and the Frappe skill package** · S · A04
  - **Description:** Install Claude Code. Clone the skill package into a scratch folder: `git clone https://github.com/OpenAEC-Foundation/Frappe_Claude_Skill_Package.git`. The skills are copied into the app repository in B04 so every session uses the same version.
  - **Verify:** `ls Frappe_Claude_Skill_Package/skills/source/*/` lists 61 skill folders (syntax, core, impl, errors, ops, agents, testing).
  - **Commit:** none.

- [x] **FMS-A09 · Configure · Editor and debugging setup** · S · A05
  - **Skills:** `frappe-agent-debugger`
  - **Description:** VS Code (or similar) with Python and ESLint extensions, debug configuration for `bench serve` (web) and `bench worker`. Learn `bench --site fms.localhost console` and `bench --site fms.localhost mariadb`.
  - **Verify:** Breakpoint in a whitelisted method hits when called from the browser.
  - **Commit:** none.

---

## B. Repository and app scaffold

- [ ] **FMS-B01 · Configure · Protect the app repository** · S · —
  - **Description:** The app repository is the existing [niiniyare/Afms](https://github.com/niiniyare/Afms) (it already holds the documents and `.claude/skills/`). The old `fms` repository holds the Odoo prototype and stays as reference. Protect `main`: pull requests required, CI must pass (after L01).
  - **Verify (UI):** Branch protection on `main` of `niiniyare/Afms`.
  - **Commit:** none.

- [x] **FMS-B02 · Initialize · Scaffold the app** · S · A05, B01
  - **Skills:** `frappe-impl-customapp`, `frappe-syntax-customapp`, `frappe-ops-app-lifecycle`
  - **Description:** `bench new-app forecourt` (title "Forecourt Management", publisher, email, licence MIT or as the owner chooses, GitHub workflow yes, pre-commit yes). Then join it to the existing repository, keeping its history: in `apps/forecourt`, `git remote add origin https://github.com/niiniyare/Afms`, `git fetch origin`, `git merge origin/main --allow-unrelated-histories`, keep the repository's `README.md` (add the generated app description to it), and push on a feature branch. `bench --site fms.localhost install-app forecourt`. HRMS is not a required app (design guide D16).
  - **Expectation:** App installs on the dev site; `required_apps = ["erpnext"]` in hooks; the repository root holds the app, the documents and `.claude/skills/`.
  - **Deliverables:** App skeleton merged into the repository.
  - **Verify:** `bench --site fms.localhost list-apps` shows `forecourt`; `git log` shows the scaffold commit on top of the documentation history.
  - **Commit:** `chore(env): scaffold forecourt app`

- [x] **FMS-B03 · Documentation · Development setup notes** · S · B02
  - **Description:** The design guide (`docs/fms.md`), the catalogue (`docs/catalogue.md`), this file and `CLAUDE.md` are already in the repository. Add `docs/dev-setup.md` from A01 and check that the scaffold from B02 did not overwrite any of them.
  - **Verify:** `docs/dev-setup.md`, `docs/fms.md`, `docs/catalogue.md`, `TASKS.md` and `CLAUDE.md` visible on GitHub.
  - **Commit:** `docs: add development setup notes`

- [x] **FMS-B04 · Configure · Install the skill package as project skills** · S · A08, B02
  - **Description:** The 61 skills are already flattened into `.claude/skills/` (repository commit `7e4b3b0`). Check them against the package clone from A08 (`cp -r <package>/skills/source/*/* .claude/skills/` if they differ) and record the package commit hash in `.claude/skills/VERSION`, which is still missing.
  - **Expectation:** Claude Code started in the repo lists the frappe-* skills.
  - **Verify:** In Claude Code, ask "List the Frappe skills you have" → 61 `frappe-*` skills.
  - **Commit:** `chore(env): add Frappe Claude skill package <hash>`

- [x] **FMS-B05 · Configure · Define the modules** · S · B02
  - **Skills:** `frappe-syntax-customapp`
  - **Description:** Replace the default module in `forecourt/modules.txt` with: Forecourt Setup, Wetstock, Forecourt Shift, Forecourt Finance, Forecourt Integrations (catalogue 2.1). Create each module folder with `__init__.py`. Create the non-DocType packages: `calc/`, `posting/`, `corrections/`, `setup/`, `api/`, `tests/` with `__init__.py`, and `errors.py` with the code ranges of design guide 15.3.
  - **Verify:** `bench --site fms.localhost migrate` clean; in Desk, *Module Def* list shows the five modules with app `forecourt`.
  - **Commit:** `chore(setup): define modules and package layout`

- [x] **FMS-B06 · Configure · Pre-commit and code style** · S · B02
  - **Skills:** `frappe-testing-cicd`
  - **Description:** Keep the pre-commit config generated by `new-app` (ruff, eslint, prettier); set ruff line length and target Python 3.14 in `pyproject.toml`. Run `pre-commit install`.
  - **Verify:** `pre-commit run --all-files` passes.
  - **Commit:** `chore(env): configure pre-commit`

- [x] **FMS-B07 · Writing Test · Test scaffolding and factories** · M · B05, A07
  - **Skills:** `frappe-testing-unit`
  - **Description:** Create `forecourt/tests/factories.py` with functions that build a complete test station (company, accounts, warehouses, items PMS and AGO, one station, two tanks with charts, two dispensers with four nozzles, two cashiers, one shift template). Factories are idempotent and used by every integration test. Add one smoke `IntegrationTestCase` that calls the factory.
  - **Expectation:** Factories create a usable station in a fresh test site. (They fail until C-tasks exist; build them up as C-tasks land, and keep the smoke test green from C14 on.)
  - **Verify:** `bench --site test_fms run-tests --app forecourt --module forecourt.tests.test_factories` passes (from C14).
  - **Commit:** `test(setup): add station factories`

- [x] **FMS-B08 · Configure · Fixtures configuration** · S · B05
  - **Skills:** `frappe-impl-customapp`, `frappe-syntax-hooks`
  - **Description:** In `hooks.py`, declare `fixtures` for Custom Field and Property Setter filtered by `module` in the FMS modules, and for Role, Workflow, Workflow State, Workflow Action Master, Stock Entry Type, Accounting Dimension, Variance Reason, Own Use Purpose filtered by name lists (or by the FMS modules where the DocType has a module field).
  - **Verify:** `bench --site fms.localhost export-fixtures --app forecourt` runs without error.
  - **Commit:** `chore(setup): declare fixtures`

- [x] **FMS-B09 · Review · Architecture review checkpoint** · S · B01–B08
  - **Skills:** `frappe-agent-architect`, `frappe-agent-validator`
  - **Description:** Ask Claude Code to review the scaffold against CLAUDE.md and the catalogue: one app, no core overrides, module layout, pure `calc/`, `ignore_permissions` only in `posting/`, `corrections/` and `setup/`.
  - **Deliverables:** Review notes appended to the Bug log (if any findings).
  - **Verify:** Review report has no errors.
  - **Commit:** none, or `docs: architecture review notes`.

---

## C. Foundation masters (Phase 0)

Build in catalogue order. Each DocType task includes its JSON, controller, a test file, list or form settings and the role permissions from the catalogue (so every DocType task depends on C01). Fields that link forward to a later DocType are added by the later task (catalogue 3.1). Validation errors use the codes in design guide 15.3 (FMS-M6xx for masters).

- [x] **FMS-C01 · Writing Feature · Roles** · S · B08
  - **Skills:** `frappe-core-permissions`
  - **Description:** Create the seven roles (catalogue 2.2). Export as fixtures.
  - **Verify (UI):** Role list shows them; `bench export-fixtures` writes `fixtures/role.json`.
  - **Commit:** `feat(setup): add FMS roles`

- [x] **FMS-C02 · Writing Feature · Forecourt Settings** · S · C01
  - **Skills:** `frappe-syntax-doctypes`, `frappe-impl-controllers`
  - **Description:** Single DocType per catalogue 4.1 with the meter validation.
  - **Expectation:** Saving with sales basis *E-vol* while E-vol is not recorded is refused.
  - **Verify (UI):** Open Forecourt Settings, try the invalid combination → error; save valid defaults.
  - **Verify (CLI):** Its test passes.
  - **Commit:** `feat(setup): add Forecourt Settings`

- [x] **FMS-C03 · Writing Feature · Forecourt Company Settings** · S · C02
  - **Skills:** `frappe-syntax-doctypes`, `frappe-core-database`
  - **Description:** Catalogue 4.2, with account validation (company, root type, account type) and the *Create default accounts* action (design guide 8.1, code in `forecourt/setup/`). Confirm which account type ERPNext accepts with party type *Employee* for the Staff Shortage Receivable account, and record the result in design guide D17 and catalogue 4.2 in the same pull request.
  - **Verify (UI):** Create one for Demo Petroleum; *Create default accounts* creates the missing accounts and fills the mapping; choosing an account from another company or of the wrong type is refused.
  - **Verify (CLI):** A Journal Entry test posts a shortage to the chosen account with party type Employee.
  - **Commit:** `feat(setup): add Forecourt Company Settings`

- [x] **FMS-C04 · Writing Feature · Station Group tree** · S · C01
  - **Skills:** `frappe-syntax-doctypes` (tree)
  - **Description:** Catalogue 4.3, root record as fixture.
  - **Verify (UI):** Tree view shows *All Station Groups*; add Brand → Region → Area groups.
  - **Commit:** `feat(setup): add Station Group tree`

- [x] **FMS-C05 · Writing Feature · Reference masters** · M · C01
  - **Skills:** `frappe-syntax-doctypes`
  - **Description:** Variance Reason, Expense Type (+ Expense Type Account), Own Use Purpose (+ Own Use Purpose Account) per catalogue 4.4–4.6, with default records as fixtures.
  - **Verify (UI):** The three lists show the default records; quick entry works for Variance Reason.
  - **Commit:** `feat(setup): add variance reasons, expense types, own use purposes`

- [x] **FMS-C06 · Writing Feature · Payment Provider** · S · C01
  - **Skills:** `frappe-syntax-doctypes`
  - **Description:** Catalogue 4.7 (import mapping JSON is used in J01).
  - **Verify (UI):** Create *M-Pesa* (Mobile Money) linked to a Mode of Payment *M-Pesa* whose company account is *Mobile Money Clearing*.
  - **Commit:** `feat(integrations): add Payment Provider`

- [x] **FMS-C07 · Writing Feature · Custom fields on Item, Employee, Customer** · S · B08
  - **Skills:** `frappe-impl-customapp` (fixtures)
  - **Description:** `fms_is_fuel`, `fms_is_forecourt_cashier`, `fms_default_station`, `fms_is_walk_in`, `fms_station` (catalogue 12). Export fixtures.
  - **Verify (UI):** Item form shows *Is Fuel*; Employee shows *Is Forecourt Cashier*.
  - **Commit:** `feat(setup): add custom fields on Item, Employee, Customer`

- [x] **FMS-C08 · Writing Feature · Station** · M · C03, C04, C06, C07
  - **Skills:** `frappe-syntax-doctypes`, `frappe-impl-controllers`
  - **Description:** Station with Station Till Account and Station Payment Terminal (catalogue 5.1). Code pattern validation, company consistency, tolerance overrides, walk-in customer creation on insert (in `forecourt/setup/`).
  - **Expectation:** Creating station `KE-NBO-WSTL` creates customer *Walk-in – Westlands*.
  - **Verify (UI):** Create the station; invalid code `westlands` is refused; walk-in customer exists and is flagged.
  - **Commit:** `feat(setup): add Station`

- [x] **FMS-C09 · Writing Feature · Station accounting dimension** · S · C08
  - **Skills:** `frappe-impl-customapp`, `frappe-core-database`
  - **Description:** Ship the Accounting Dimension *Station* as a fixture (or create it in `after_install`), document type Station.
  - **Expectation:** Sales Invoice, Payment Entry, Journal Entry, Stock Entry forms show a *Station* field; GL Entry has a `station` column.
  - **Verify (UI):** Open a new Journal Entry → *Station* field present. **(CLI)** `bench --site fms.localhost mariadb -e "SHOW COLUMNS FROM \`tabGL Entry\` LIKE 'station'"` returns one row.
  - **Commit:** `feat(setup): add Station accounting dimension`

- [x] **FMS-C10 · Writing Feature · Fuel Tank** · M · C08
  - **Skills:** `frappe-syntax-doctypes`, `frappe-impl-controllers`
  - **Description:** Catalogue 6.1, creating the tank Warehouse on insert and blocking deletion once stock exists.
  - **Verify (UI):** Create T1 (PMS, 30,000 L) → warehouse *T1 - KE-NBO-WSTL - DPL* (ERPNext adds the company abbreviation) exists under the station's group warehouse.
  - **Commit:** `feat(wetstock): add Fuel Tank`

- [x] **FMS-C11 · Writing Feature · Dispenser** · S · C08
  - **Skills:** `frappe-syntax-doctypes`
  - **Description:** Catalogue 6.2, including the meter and sales basis override.
  - **Verify (UI):** Create D01 (Island 1) and D02; an override with basis E-vol and E-vol not recorded is refused.
  - **Commit:** `feat(wetstock): add Dispenser`

- [x] **FMS-C12 · Writing Feature · Tank Calibration Chart** · M · C10, D02
  - **Skills:** `frappe-syntax-doctypes`, `frappe-impl-clientscripts`
  - **Description:** Catalogue 7.1 with validation; uses `calc/calibration.py` for max depth and volume. Client script: paste rows from a spreadsheet; preview chart.
  - **Verify (UI):** Upload a 300-row chart from CSV; non-increasing volume is refused.
  - **Commit:** `feat(wetstock): add Tank Calibration Chart`

- [x] **FMS-C13 · Writing Feature · Nozzle** · S · C10, C11
  - **Skills:** `frappe-syntax-doctypes`
  - **Description:** Catalogue 7.2 without `last_reading_shift` (added in F01); tank must belong to the same station.
  - **Verify (UI):** Create D01-N1 (T1) and D01-N2 (T2); linking a tank from another station is refused.
  - **Commit:** `feat(wetstock): add Nozzle`

- [x] **FMS-C14 · Writing Test · Station setup end to end** · S · C01–C13, B07
  - **Skills:** `frappe-testing-unit`
  - **Description:** Complete the factories; integration test that creates a full station and checks warehouses, walk-in customer and dimension.
  - **Verify:** `bench --site test_fms run-tests --app forecourt` passes.
  - **Commit:** `test(setup): station setup end to end`

---

## D. Calculation core (pure Python)

No Frappe imports in `forecourt/calc/`. Tests use `UnitTestCase` (or plain pytest) and run in milliseconds.

- [x] **FMS-D01 · Prototyping · Calculation API sketch** · S · B05
  - **Skills:** `frappe-agent-interpreter`
  - **Description:** Write function signatures and docstrings for every calculation in the design guide (sections 5.3, 5.5, 5.6, 6.5a, 7.2, 10.4) using plain dataclasses for inputs and outputs. Review with the owner before implementing.
  - **Deliverables:** `calc/*.py` with signatures and `NotImplementedError`.
  - **Verify:** Owner approves the sketch in the pull request.
  - **Commit:** `feat(calc): sketch calculation API`

- [x] **FMS-D02 · Writing Feature · Calibration interpolation** · S · D01
  - **Description:** Depth → litres with linear interpolation, out-of-range errors, water deduction.
  - **Verify:** Unit tests cover exact rows, midpoints, below zero, above max.
  - **Commit:** `feat(calc): calibration interpolation`

- [x] **FMS-D03 · Writing Feature · Meter deltas, rollover and basis** · M · D01
  - **Description:** Per-meter delta with rollover; litres from E-cash per price segment; basis selection including *Highest* with the winning meter recorded.
  - **Verify:** Unit tests include rollover on each meter and *Highest* picking each meter in turn.
  - **Commit:** `feat(calc): meter deltas, rollover and sales basis`

- [x] **FMS-D04 · Writing Feature · Meter drift** · S · D03
  - **Description:** The three drift formulas and tolerance check (litres or %, whichever is larger).
  - **Verify:** Unit tests for each pair and the tolerance edge.
  - **Commit:** `feat(calc): meter drift`

- [x] **FMS-D05 · Writing Feature · Tank reconciliation and tolerances** · S · D01
  - **Description:** Expected closing, variance, variance %, tolerance and approval thresholds, manifold groups.
  - **Verify:** Unit tests reproduce the design guide example numbers.
  - **Commit:** `feat(calc): tank reconciliation`

- [x] **FMS-D06 · Writing Feature · Cashier balance** · S · D01
  - **Description:** Expected, accounted, difference (design guide 7.2), multi-currency cash with exchange rates.
  - **Verify:** Unit test reproduces the worked example in design guide 8.2 (difference −500).
  - **Commit:** `feat(calc): cashier balance`

- [x] **FMS-D07 · Writing Feature · Payment attribution** · S · D06
  - **Description:** Exact rows for credit and POS; attributed rows spreading remaining payments by value (design guide 10.4), with rounding so totals match exactly.
  - **Verify:** Unit test: 180,000 mobile over 60/40 PMS/AGO → 108,000 / 72,000; totals equal input to the cent.
  - **Commit:** `feat(calc): payment attribution`

- [x] **FMS-D08 · Writing Test · Property tests for the calculation core** · S · D02–D07
  - **Skills:** `frappe-testing-unit`
  - **Description:** Randomised tests: totals always balance; attribution sums equal inputs; interpolation monotonic.
  - **Verify:** Tests pass 100 runs.
  - **Commit:** `test(calc): property tests`

---

## E. Station movements

- [x] **FMS-E01 · Writing Feature · Customer Vehicle** · S · C07
  - **Skills:** `frappe-syntax-doctypes`
  - **Description:** Catalogue 6.3 with plate normalisation.
  - **Verify (UI):** Create *Coast Haulage* vehicle `KDA 123A` → stored as `KDA123A`; duplicate refused.
  - **Commit:** `feat(finance): add Customer Vehicle`

- [x] **FMS-E02 · Writing Feature · Forecourt Shift Template** · S · C13
  - **Skills:** `frappe-syntax-doctypes`
  - **Description:** Catalogue 8.1 with roster child tables.
  - **Verify (UI):** Create *Day* 06:00–18:00 with two cashiers and nozzle assignments.
  - **Commit:** `feat(shift): add Forecourt Shift Template`

- [x] **FMS-E03 · Writing Feature · GRN delivery dips on Purchase Receipt** · L · C12, D02, D05
  - **Skills:** `frappe-syntax-hooks-events`, `frappe-impl-hooks`, `frappe-syntax-doctypes`
  - **Description:** GRN Delivery Dip child DocType (catalogue 8.6); custom fields on Purchase Receipt (catalogue 12); `doc_events` for validate and submit; both dip entry modes; tolerance check with mandatory reason.
  - **Expectation:** A manually created GRN for 10,000 L PMS into T1 with dips before and after computes received volume and variance. Without dips (when required) it cannot be submitted.
  - **Verify (UI):** Post a GRN with a −0.5% variance → reason required (FMS-T205); submit → the GRN's dip fields are stored. The Wetstock Ledger Entry of type *Delivery* is wired and checked in F15.
  - **Commit:** `feat(wetstock): delivery dips on GRN`

- [x] **FMS-E04 · Writing Feature · Record delivery shortage** · S · E03
  - **Skills:** `frappe-impl-clientscripts`, `frappe-impl-whitelisted`
  - **Description:** Button on submitted GRNs with a shortage beyond tolerance that prepares a draft Stock Entry (Material Issue, account Delivery Shortage Claims) linked to the GRN.
  - **Verify (UI):** Button creates a draft; submitting it reduces T1 book stock by the shortage.
  - **Commit:** `feat(wetstock): record delivery shortage`

- [x] **FMS-E05 · Writing Feature · Fuel Own Use stock entry type** · M · C05, C13
  - **Skills:** `frappe-syntax-hooks-events`, `frappe-impl-clientscripts`
  - **Description:** Stock Entry Type fixture; custom fields on Stock Entry except `fms_forecourt_shift` (added in F01); validation (narration, purpose, nozzle, vehicle when required); expense account from purpose. Defaulting the shift to the open shift at the station is done in F06.
  - **Verify (UI):** Post 40 L generator use from D01-N2 → T2 stock −40 L; GL shows the generator expense account with station dimension.
  - **Commit:** `feat(wetstock): fuel own use`

- [x] **FMS-E06 · Writing Feature · Tank Dip (spot dip)** · S · C12, D02
  - **Skills:** `frappe-syntax-doctypes`
  - **Description:** Catalogue 8.4; computes book volume at the dip time from the stock ledger. The *Spot Dip* ledger row is wired in F15.
  - **Verify (UI):** Spot dip on T1 shows book volume and difference; no stock posted.
  - **Commit:** `feat(wetstock): spot dips`

- [x] **FMS-E07 · Writing Feature · Tank Transfer** · S · C10
  - **Skills:** `frappe-impl-controllers`
  - **Description:** Catalogue 8.5, creating a Material Transfer Stock Entry on submit.
  - **Verify (UI):** Transfer 500 L T2 → T3 (same product); stock balance report shows the move.
  - **Commit:** `feat(wetstock): tank transfer`

- [x] **FMS-E08 · Writing Feature · Meter Change** · S · C13
  - **Skills:** `frappe-impl-controllers`
  - **Description:** Catalogue 8.3; updates nozzle last readings. The *Meter Change* ledger row is wired in F15.
  - **Verify (UI):** Meter Change on D01-N1 → Nozzle shows new last readings.
  - **Commit:** `feat(wetstock): meter change`

- [x] **FMS-E09 · Writing Feature · Fuel Price Change** · M · C08
  - **Skills:** `frappe-impl-controllers`, `frappe-core-workflow`
  - **Description:** Catalogue 8.2 without the shift segment part and `applied_to_shift` (added in F07). Workflow Draft → Pending Approval → Approved. `effective_at` may not be in the future. Writes Item Price on the station price list, and the Sales Invoice / POS Invoice `validate` hook that sets fuel rates from the change in force at the posting time (design guide 6.5a, D24).
  - **Verify (UI):** Station Manager creates PMS 180 → 182 at 14:00; Area Manager approves; Item Price shows 182 from the effective date; a Sales Invoice posted at 13:00 the same day keeps 180, one at 15:00 gets 182.
  - **Commit:** `feat(shift): fuel price change`

- [x] **FMS-E10 · Writing Test · Station movements tests** · M · E01–E09
  - **Skills:** `frappe-testing-unit`
  - **Description:** Integration tests for E03–E09 using the factories.
  - **Verify:** `bench --site test_fms run-tests --app forecourt` passes.
  - **Commit:** `test(wetstock): station movements`

---

## F. Forecourt Shift (Phase 1 core)

- [x] **FMS-F01 · Writing Feature · Shift DocType and child tables** · L · E02
  - **Skills:** `frappe-syntax-doctypes`, `frappe-syntax-controllers`
  - **Description:** Forecourt Shift and its nine child tables exactly as catalogue 9.1–9.2, no logic yet beyond required fields. Tabs in the specified order. Shift Collection's `feed_entry` and `import_batch` are left out (added in J04 and J01). Also add the forward links that target Forecourt Shift (catalogue 3.1): `Nozzle.last_reading_shift` and the `fms_forecourt_shift` custom fields on the eight native DocTypes.
  - **Verify (UI):** New Forecourt Shift form shows all tabs and grids; saves a draft.
  - **Commit:** `feat(shift): add Forecourt Shift structure`

- [x] **FMS-F02 · Writing Feature · Shift creation pre-fill** · M · F01, D01
  - **Skills:** `frappe-impl-controllers`
  - **Description:** `before_insert`: previous shift, roster, reading rows with locked openings (from Nozzle last readings) and each row's meters and sales basis (dispenser override, else station), tank rows with opening stock and dip entry mode (tank override, else station), first price segment, settings snapshot, shift window in station time zone, `shift_date` = date of `shift_start` in station time (D20).
  - **Expectation:** A new shift for the test station is ready with 4 reading rows, 2 tank rows, prices, and no typing.
  - **Verify (UI):** Create a shift → all rows present; opening fields read-only.
  - **Commit:** `feat(shift): pre-fill new shift`

- [x] **FMS-F03 · Writing Feature · Live calculations in the form** · M · F02, D03–D06
  - **Skills:** `frappe-impl-clientscripts`, `frappe-syntax-clientscripts`
  - **Description:** Server-side `validate` recomputes everything through `calc/`; client script refreshes totals and the reconciliation summary on change (calling a whitelisted `preview` method, debounced). Enter-to-next-row on the meter and tank grids.
  - **Verify (UI):** Typing closing readings updates litres, amounts and cashier expected immediately.
  - **Commit:** `feat(shift): live calculations`

- [x] **FMS-F04 · Writing Feature · Meter modes and drift in the shift** · M · F03, D04
  - **Description:** Show only the recorded meters (per row, from the dispenser override or the station); compute basis and drift; drift reason required beyond tolerance when configured.
  - **Verify (UI):** Switch the station to all three meters → three columns appear; a dispenser with an M-vol-only override requires only M-vol on its rows; a 2% drift asks for a reason.
  - **Commit:** `feat(shift): meter modes and drift`

- [x] **FMS-F05 · Writing Feature · Tank dips in the shift** · S · F03, D05
  - **Description:** Both dip entry modes; receipts pulled from submitted GRNs in the window; own use pulled; variance and tolerance status.
  - **Verify (UI):** With a GRN posted mid-shift, the tank row shows the receipt automatically.
  - **Commit:** `feat(shift): tank dips with pulled receipts`

- [x] **FMS-F06 · Writing Feature · Own use pull-in** · S · F05, E05
  - **Description:** A new Fuel Own Use entry defaults its shift to the open shift at the station; submitted entries in the window reduce the nozzle's net litres; drafts block close (FMS-S113).
  - **Verify (UI):** 40 L generator use appears on D01-N2's row.
  - **Commit:** `feat(shift): pull own use into shift`

- [x] **FMS-F07 · Writing Feature · Price segments** · M · F02, E09
  - **Skills:** `frappe-impl-controllers`
  - **Description:** Add `Fuel Price Change.applied_to_shift`. On Fuel Price Change submit in *Latest price with segments* mode, add a segment to the open shift and split the affected reading rows; manager enters change-time readings; FMS-S112 gate.
  - **Verify (UI):** Approve a PMS change at 14:00 → the shift shows two PMS segments; closing without the 14:00 readings is refused.
  - **Commit:** `feat(shift): mid-shift price segments`

- [x] **FMS-F08 · Writing Feature · Credit sales** · M · F03, E01
  - **Description:** Credit Sale grid with vehicle filter, price from the segment at `sold_at`, slip uniqueness, vehicle belongs to customer and allows the product, credit limit and vehicle monthly litre limit checks with over-limit approval (FMS-S107).
  - **Verify (UI):** A slip over Coast Haulage's limit shows the limit warning and requires approval.
  - **Commit:** `feat(shift): credit sales`

- [x] **FMS-F09 · Writing Feature · Item sales and POS pull-in** · S · F03
  - **Description:** Manual item sales; submitted POS Invoices and POS-created Sales Invoices (`is_pos`) for each cashier in the window pulled in as read-only lines (excluded from posting) (D25); POS cashier defaulted from `Employee.user_id`.
  - **Verify (UI):** A POS Invoice by cashier Amina during the shift appears under Items.
  - **Commit:** `feat(shift): item sales and POS pull-in`

- [x] **FMS-F10 · Writing Feature · Cashier counts and collections** · M · F03, C06
  - **Description:** Cash count grid per cashier and currency; collections grid for mobile money, card, voucher, expense, drop, debt receipt (with `paid_by`, design guide 7.2, D21); reference mandatory and unique per provider (FMS-S114); expense limits and receipts.
  - **Verify (UI):** Entering the same M-Pesa reference twice is refused.
  - **Commit:** `feat(shift): cashier counts and collections`

- [x] **FMS-F11 · Writing Feature · Resolutions** · M · F10, F05
  - **Description:** Shift Resolution grid: *Resolve* buttons on each cashier and tank row create a resolution line pre-filled with the policy default; write-offs above the small limit and tank variances above the approval threshold need approval.
  - **Verify (UI):** A −500 shortage cannot be submitted until a resolution line is confirmed.
  - **Commit:** `feat(shift): resolution lines`

- [x] **FMS-F12 · Writing Feature · Gates** · M · F04–F11
  - **Skills:** `frappe-errors-controllers`
  - **Description:** All gates in design guide 6.6 (including FMS-S115) in `before_submit`, each raising its coded message from one `forecourt/errors.py` catalogue. Gate failures are listed together, not one at a time. FMS-S110 is skipped when the company allows overlapping shifts.
  - **Verify (UI):** A shift with three problems shows all three codes in one message.
  - **Commit:** `feat(shift): close gates`

- [x] **FMS-F13 · Writing Feature · Posting: sales and payments** · L · F12
  - **Skills:** `frappe-impl-controllers`, `frappe-core-database`
  - **Description:** `posting/sales.py`: credit Sales Invoices per customer (or Delivery Notes when the company invoices monthly, D26); walk-in Sales Invoice (update_stock from tank warehouses). `posting/payments.py`: one Payment Entry per mobile money and card collection (reference_no = provider reference), one cash Payment Entry per cashier, voucher and debt receipt entries (cash into the till, non-cash into the clearing account). All carry `fms_forecourt_shift`, `fms_cashier` and the station dimension, and use the posting times of design guide 6.7 (D35).
  - **Expectation:** After submit, the walk-in invoice is fully paid and every mobile money transaction has its own Payment Entry.
  - **Verify (UI):** Shift Connections tab lists the invoices and payment entries; Accounts Receivable shows walk-in at zero.
  - **Commit:** `feat(shift): post sales and payments`

- [ ] **FMS-F14 · Writing Feature · Posting: journals and stock** · M · F13
  - **Description:** `posting/journals.py`: expenses and resolutions; `posting/stock.py`: Stock Reconciliation per tank (according to the company setting), drops as internal transfers, and the float transfer to the safe when the company returns floats (D27).
  - **Verify (UI):** General Ledger filtered by the shift's vouchers: till balance equals counted cash; Fuel Stock Variance shows the tank variance value.
  - **Commit:** `feat(shift): post journals and stock reconciliation`

- [ ] **FMS-F15 · Writing Feature · Ledgers** · M · F13, D07
  - **Skills:** `frappe-syntax-doctypes`, `frappe-core-database`
  - **Description:** The four ledger DocTypes (catalogue 10.1–10.4, without `superseded_by` and `correction`, added in G01) with composite indexes in `on_doctype_update`; `posting/ledgers.py` writes them on submit; Nozzle `last_*` updated. Also wire the ledger rows of E03 (*Delivery*), E06 (*Spot Dip*) and E08 (*Meter Change*) through `posting/ledgers.py`.
  - **Verify (CLI):** `bench --site fms.localhost mariadb -e "SHOW INDEX FROM \`tabSales Ledger Entry\`"` shows the composite indexes. **(UI)** Report view of each ledger shows the shift's rows; submitting a GRN, a spot dip and a meter change each writes its ledger row.
  - **Commit:** `feat(finance): FMS ledgers`

- [ ] **FMS-F16 · Writing Feature · Background close for large shifts** · S · F13
  - **Skills:** `frappe-impl-scheduler`, `frappe-syntax-scheduler`
  - **Description:** Above `background_close_threshold` payment rows, *Close* enqueues a job (queue `long`, deduplicated by shift) that submits the shift in one transaction; status *Closing*; on failure, back to *Reconciled* with the error in a comment and an Error Log.
  - **Verify (UI):** A shift with 250 imported mobile rows closes via the job; the form refreshes to *Closed* through realtime.
  - **Commit:** `feat(shift): background close`

- [ ] **FMS-F17 · Writing Feature · Shift form layout and print format** · M · F12
  - **Skills:** `frappe-impl-jinja`, `frappe-syntax-print`
  - **Description:** Final form layout (catalogue 9.1 tabs, reconciliation summary HTML on Review); *Shift Report* print format (one page).
  - **Verify (UI):** Print preview fits one A4 page for the test station.
  - **Commit:** `feat(shift): form layout and Shift Report`

- [ ] **FMS-F18 · Writing Test · Shift integration tests** · L · F01–F17
  - **Skills:** `frappe-testing-unit`
  - **Description:** Scenarios: normal shift; shortage charged; excess; rollover; delivery mid-shift; own use; price change mid-shift; three-meter drift; over-limit credit; multi-currency cash; debt receipt by mobile money; overnight shift; background close. Each asserts GL balances, stock per tank and ledger rows.
  - **Verify:** `bench --site test_fms run-tests --app forecourt --module forecourt.tests.test_shift_scenarios` passes.
  - **Commit:** `test(shift): scenario tests`

---

## G. Shift Correction

- [ ] **FMS-G01 · Writing Feature · Shift Correction DocType and workflow** · M · F15
  - **Skills:** `frappe-syntax-doctypes`, `frappe-core-workflow`, `frappe-impl-workflow`
  - **Description:** Catalogue 10.5 with workflow Draft → Pending Director Approval → Approved → Applied / Rejected. Add the ledgers' `superseded_by` and `correction` links (catalogue 3.1). Cancel guards on generated documents (catalogue 12 hooks, FMS-C502) that allow cancellation only from a correction.
  - **Verify (UI):** Cancelling a shift's Payment Entry directly is refused with a message pointing to Shift Correction.
  - **Commit:** `feat(shift): Shift Correction workflow`

- [ ] **FMS-G02 · Writing Feature · Native document corrections** · M · G01
  - **Description:** `corrections/native.py`: cancel and amend one target document (Sales Invoice, Payment Entry, Journal Entry) with the new values.
  - **Verify (UI):** Correct a mobile money reference → old Payment Entry cancelled, amended one submitted, shift banner lists the correction.
  - **Commit:** `feat(shift): native document corrections`

- [ ] **FMS-G03 · Writing Feature · Meter reading corrections** · L · G01
  - **Description:** `corrections/meter.py`: move litres between the shift and the next one; superseding Nozzle and Sales Ledger rows; Credit Note or additional invoice for walk-in sales; new differences go to resolution lines in the correction.
  - **Verify (UI):** Correct a closing reading by +90 L → both shifts' reports show the corrected litres; audit view shows superseded rows.
  - **Commit:** `feat(shift): meter reading corrections`

- [ ] **FMS-G04 · Writing Feature · Dip, cashier and reclassification corrections** · M · G01
  - **Description:** `corrections/dip.py`, `cashier.py`, `reclassify.py` per design guide 6.8. A dip correction also re-bases the next shift's opening and variance (D22).
  - **Verify (UI):** Correct a dip → new Stock Reconciliation dated at the original time; stock balance updated after reposting; the next shift's tank row and Wetstock Ledger show the corrected opening.
  - **Commit:** `feat(shift): dip, cashier and reclassification corrections`

- [ ] **FMS-G05 · Writing Feature · Whole-shift cancellation (exception)** · S · G01
  - **Description:** Only for the latest shift, System Manager + director approval, cancels generated documents in reverse order (FMS-C503). No FMS role has Cancel on Forecourt Shift.
  - **Verify (UI):** Attempt on an older shift is refused; on the latest shift with approval it succeeds.
  - **Commit:** `feat(shift): exceptional whole-shift cancellation`

- [ ] **FMS-G06 · Writing Test · Correction tests** · M · G02–G05
  - **Skills:** `frappe-testing-unit`
  - **Verify:** `bench --site test_fms run-tests --app forecourt --module forecourt.tests.test_corrections` passes, including ledger totals before and after.
  - **Commit:** `test(shift): corrections`

---

## H. Reports and workspaces

- [ ] **FMS-H01 · Writing Feature · Daily Station Report** · M · F15
  - **Skills:** `frappe-impl-reports`, `frappe-syntax-reports`
  - **Verify (UI):** For one day with two shifts, totals by product and payment type match the shifts.
  - **Commit:** `feat(reports): Daily Station Report`

- [ ] **FMS-H02 · Writing Feature · Sales by Product, Tank, Pump and Nozzle, Shift, Cashier** · L · F15
  - **Skills:** `frappe-impl-reports`, `frappe-syntax-query-builder`
  - **Description:** Five script reports over the Sales and Nozzle Ledgers with the Exact/Attributed basis column.
  - **Verify (UI):** Each report's grand total equals the Daily Station Report for the same period.
  - **Commit:** `feat(reports): sales by product, tank, pump, shift, cashier`

- [ ] **FMS-H03 · Writing Feature · Payment Mix Matrix** · M · H02
  - **Verify (UI):** Pivot product × payment type sums to the same total as H02.
  - **Commit:** `feat(reports): payment mix matrix`

- [ ] **FMS-H04 · Writing Feature · Wetstock reports** · L · F15
  - **Description:** Tank Stock Position, Wetstock Variance (shift, daily, cumulative %), Delivery Variance, Meter Drift, Run-out Forecast.
  - **Verify (UI):** Cumulative variance % for T1 over the test data matches a manual calculation in a spreadsheet.
  - **Commit:** `feat(reports): wetstock reports`

- [ ] **FMS-H05 · Writing Feature · Cashier and finance reports** · M · F15
  - **Description:** Cashier Statement, Cashier Variance Ranking, Credit Slips Register (with slip gaps), Clearing Account Ageing, Cash Position by Station.
  - **Verify (UI):** Cashier Statement balance for Amina equals the Staff Shortage Receivable GL balance for her.
  - **Commit:** `feat(reports): cashier and finance reports`

- [ ] **FMS-H06 · Writing Feature · Exception Register, Open Items, Station Comparison** · M · F15, G01
  - **Verify (UI):** A shift with a write-off and a correction appears in the Exception Register.
  - **Commit:** `feat(reports): exceptions, open items, station comparison`

- [ ] **FMS-H07 · Writing Feature · Number cards and charts** · M · H01–H06
  - **Skills:** `frappe-impl-reports`, `frappe-impl-workspace`
  - **Description:** Catalogue 13.2 and 13.3, shipped as fixtures.
  - **Verify (UI):** Cards show values for the test station; a station manager sees only their station.
  - **Commit:** `feat(reports): number cards and charts`

- [ ] **FMS-H08 · Writing Feature · Workspaces and sidebar** · M · H07
  - **Skills:** `frappe-impl-workspace`
  - **Description:** The seven workspaces in catalogue 14 with `app`, `module`, `roles`, `parent_page`, `sequence_id`; exported to the app.
  - **Verify (UI):** Log in as each role → only the right workspaces appear in the sidebar; shortcuts open the right forms.
  - **Commit:** `feat(setup): workspaces and navigation`

- [ ] **FMS-H09 · Writing Feature · Setup onboarding** · S · H08
  - **Skills:** `frappe-impl-workspace`
  - **Description:** Module Onboarding steps for Forecourt Setup (catalogue 14.2).
  - **Verify (UI):** A fresh site shows the onboarding checklist; each step opens the right form.
  - **Commit:** `feat(setup): onboarding`

- [ ] **FMS-H10 · Writing Feature · FMS Health report and daily email** · M · H06
  - **Skills:** `frappe-impl-scheduler`, `frappe-core-notifications`
  - **Description:** Design guide 15.4 checks; scheduled daily, emailed to administrators and area managers.
  - **Verify (CLI):** `bench --site fms.localhost execute forecourt.forecourt_setup.report.fms_health.fms_health.send_daily` sends an email visible in the Email Queue.
  - **Commit:** `feat(reports): FMS health check`

- [ ] **FMS-H11 · Writing Test · Report totals tests** · M · H01–H06
  - **Description:** Tests that every report's totals agree with each other and with the GL for the scenario data.
  - **Verify:** Report tests pass.
  - **Commit:** `test(reports): totals agree`

- [ ] **FMS-H12 · Review · Query performance check** · S · H11
  - **Skills:** `frappe-ops-performance`, `frappe-core-database`
  - **Description:** Generate 2 years of synthetic ledger rows for 20 stations (script in `tests/perf/`); time each report.
  - **Verify (CLI):** Each report returns in under 3 seconds for a station-month and under 10 seconds for a group-year; `EXPLAIN` shows index use.
  - **Commit:** `test(reports): performance baseline`

---

## I. Approvals, roles and permissions

- [ ] **FMS-I01 · Writing Feature · Role permissions on all DocTypes** · M · F15
  - **Skills:** `frappe-core-permissions`
  - **Description:** Apply the catalogue permission tables to every DocType JSON.
  - **Verify (UI):** Role Permissions Manager matches the catalogue for five sampled DocTypes.
  - **Commit:** `feat(setup): role permissions`

- [ ] **FMS-I02 · Writing Feature · Station and Station Group user permissions** · M · I01
  - **Skills:** `frappe-core-permissions`, `frappe-errors-permissions`
  - **Description:** `permission_query_conditions` and `has_permission` (returning explicit `True` in v16) expanding Station Group permissions to descendant stations, applied to FMS DocTypes and ledgers.
  - **Verify (UI):** Area manager with permission on *Region Nairobi* sees Westlands and Karen but not Mombasa stations.
  - **Commit:** `feat(setup): station group permissions`

- [ ] **FMS-I03 · Writing Feature · Shift approval workflow** · M · F11
  - **Skills:** `frappe-impl-workflow`, `frappe-core-workflow`
  - **Description:** Workflow *Forecourt Shift Approval* on `approval_state` only (design guide 6.2, D19): the controller sets *Pending Approval* for write-offs above the limit and large variances; the area manager approves or rejects; approver cannot be the preparer; a change after approval resets it to *Pending Approval*. `status` stays controller-driven.
  - **Verify (UI):** A shift with a large write-off shows *Pending Approval*; area manager approves; manager closes; the manager cannot approve their own shift.
  - **Commit:** `feat(shift): approval workflow`

- [ ] **FMS-I04 · Writing Feature · Notifications for approvals** · S · I03
  - **Skills:** `frappe-core-notifications`
  - **Description:** Email and system notifications for shifts awaiting approval, corrections awaiting the director, and price changes awaiting approval.
  - **Verify (UI):** Area manager receives a notification when a shift is sent for approval.
  - **Commit:** `feat(shift): approval notifications`

- [ ] **FMS-I05 · Writing Test · Permission tests** · M · I01–I04
  - **Verify:** Tests log in as each role and assert allowed and refused actions.
  - **Commit:** `test(setup): permissions`

- [ ] **FMS-I06 · Review · Security review** · S · I05
  - **Skills:** `frappe-agent-validator`
  - **Description:** Review whitelisted methods for permission checks, `ignore_permissions` use limited to ledger writes, no SQL built from user input.
  - **Verify:** Review report has no errors.
  - **Commit:** fixes as `fix(...)`, or none.

---

## J. Payment import and integrations

- [ ] **FMS-J01 · Writing Feature · Payment Import Batch (Phase 1)** · L · F10
  - **Skills:** `frappe-impl-whitelisted`, `frappe-core-files`
  - **Description:** Catalogue 11.3, and add `Shift Collection.import_batch`. Mapping-driven CSV and Excel parser; creates collection rows on the shift; duplicates skipped by reference; row log. **Import transactions** button on the shift.
  - **Expectation:** Importing a 300-row M-Pesa statement takes under 10 seconds and assigns rows by till.
  - **Verify (UI):** Import a sample statement → rows appear on the right cashiers; re-import creates zero rows.
  - **Commit:** `feat(integrations): payment statement import`

- [ ] **FMS-J02 · Writing Test · Import tests with sample files** · S · J01
  - **Deliverables:** Anonymised sample files in `tests/fixtures/` (M-Pesa, EVC Plus, one card terminal batch report).
  - **Verify:** Import tests pass.
  - **Commit:** `test(integrations): statement import`

- [ ] **FMS-J03 · Writing Feature · Integration Inbox** · M · C06
  - **Skills:** `frappe-impl-integrations`, `frappe-core-logging`
  - **Description:** Catalogue 11.1 with unique (provider, external_id), processing job with retry and backoff, *Retry* button.
  - **Verify (UI):** A malformed message shows *Failed* with the error; *Retry* after fixing mapping processes it.
  - **Commit:** `feat(integrations): integration inbox`

- [ ] **FMS-J04 · Writing Feature · Payment Feed Entry and shift matching** · M · J03, F10
  - **Description:** Catalogue 11.2, and add `Shift Collection.feed_entry`; at shift creation and refresh, matched feed entries become collection rows; unmatched block close (FMS-S111).
  - **Verify (UI):** A feed entry for the station's till during the shift appears on the cashier automatically.
  - **Commit:** `feat(integrations): payment feed matching`

- [ ] **FMS-J05 · Writing Feature · First mobile money adapter** · L · J04
  - **Skills:** `frappe-impl-integrations`, `frappe-impl-whitelisted`, `frappe-core-api`
  - **Description:** Adapter for the owner's first market (default M-Pesa C2B confirmation callback), validated endpoint, credentials in site config, idempotent.
  - **Verify (CLI):** Posting a sample callback to the endpoint with `curl` creates one inbox row and one feed entry; posting it again creates none.
  - **Commit:** `feat(integrations): M-Pesa adapter`

- [ ] **FMS-J06 · Writing Feature · Bank statement import and reconciliation setup** · M · F13
  - **Skills:** `frappe-impl-integrations`
  - **Description:** Configure ERPNext Bank Statement Import mappings for the owner's banks; document matching per Payment Entry reference in a short guide.
  - **Verify (UI):** Import a sample statement; Bank Reconciliation Tool matches Payment Entries by reference.
  - **Commit:** `docs(finance): bank reconciliation setup`

- [ ] **FMS-J07 · Writing Feature · First fiscal adapter** · L · F13
  - **Skills:** `frappe-impl-integrations`
  - **Description:** Fiscal Adapter interface (`submit`, `status`, `cancel`) and the first country implementation (default Kenya eTIMS) on Sales Invoice submit, via the Integration Inbox (direction Out).
  - **Verify (UI):** Submitting the shift's walk-in invoice in sandbox mode stores the fiscal receipt number on the invoice.
  - **Commit:** `feat(integrations): fiscal adapter`

- [ ] **FMS-J08 · Writing Test · Integration tests with mocked providers** · M · J03–J07
  - **Verify:** Integration tests pass without network access.
  - **Commit:** `test(integrations): mocked providers`

---

## K. Quality, scenarios and UAT

- [ ] **FMS-K01 · Writing Test · Golden-month scenario** · L · F18, G06, H11
  - **Description:** A script that loads a realistic month for two stations (90 shifts, deliveries, price changes, corrections) and checks that GL, stock and every report agree.
  - **Verify (CLI):** `bench --site test_fms execute forecourt.tests.golden.run` prints "all checks passed".
  - **Commit:** `test: golden-month scenario`

- [ ] **FMS-K02 · Review · Shift close timing test** · S · F17
  - **Description:** Owner or a station manager closes a typical shift (8 nozzles, 3 tanks, 2 cashiers, 5 slips, one import) from a paper sheet.
  - **Verify (UI):** Close completed in under 10 minutes; note every slow step in the Bug log.
  - **Commit:** none.

- [ ] **FMS-K03 · Review · Tablet and small-screen check** · S · F17
  - **Description:** Shift close on a 10-inch tablet and a phone browser.
  - **Verify (UI):** All tabs usable; grids scroll; no horizontal page scroll outside grids.
  - **Commit:** fixes as Bug log tasks.

- [ ] **FMS-K04 · Review · Code validation pass** · M · K01
  - **Skills:** `frappe-agent-validator`
  - **Description:** Validator review over the whole app; fix errors.
  - **Verify:** Validator report has no errors.
  - **Commit:** `refactor: validator findings`

- [ ] **FMS-K05 · Documentation · User guides** · M · K02
  - **Description:** Short guides with screenshots: station setup, closing a shift, posting a GRN, own use, price change, corrections, reading the reports. Stored in `docs/user/`.
  - **Verify:** A new manager follows the shift guide without help.
  - **Commit:** `docs: user guides`

- [ ] **FMS-K06 · Review · UAT with the owner** · M · K05
  - **Description:** Run the UAT script: setup a station, 3 days of shifts including one shortage, one delivery shortage, one mid-shift price change, one correction; reports reviewed by the owner and an accountant.
  - **Verify (UI):** Signed UAT checklist in `docs/uat/`.
  - **Commit:** `docs: UAT sign-off`

- [ ] **FMS-K07 · Bug fix · UAT fixes** · M · K06
  - **Description:** Fix every UAT finding logged in the Bug log, each as its own small task and commit.
  - **Verify:** All UAT findings closed.
  - **Commit:** per fix.

---

## L. CI/CD

- [ ] **FMS-L01 · Configure · GitHub Actions test workflow** · M · B07
  - **Skills:** `frappe-testing-cicd`
  - **Description:** Workflow that sets up MariaDB and Redis services, Python 3.14 and Node 24, a bench with frappe, erpnext (and hrms) version-16, installs the app, runs `bench run-tests --app forecourt` and the calc unit tests.
  - **Verify (UI):** A pull request shows the CI check green.
  - **Commit:** `ci: test workflow`

- [ ] **FMS-L02 · Configure · Lint and security checks in CI** · S · L01, B06
  - **Skills:** `frappe-testing-cicd`
  - **Description:** pre-commit in CI; a Python security linter (e.g. bandit or semgrep rules) on the app code.
  - **Verify (UI):** CI fails on a deliberately bad commit in a test branch, then passes after revert.
  - **Commit:** `ci: lint and security`

- [ ] **FMS-L03 · Configure · Release process** · S · L01
  - **Skills:** `frappe-ops-app-lifecycle`
  - **Description:** Semantic version in `forecourt/__init__.py`, CHANGELOG, tags `v0.x.y`, release notes from merged pull requests.
  - **Verify (UI):** Tag `v0.1.0` and its GitHub release exist.
  - **Commit:** `chore: release process`

- [ ] **FMS-L04 · Configure · Migration and patch discipline** · S · L01
  - **Skills:** `frappe-impl-customapp`, `frappe-ops-upgrades`
  - **Description:** `patches.txt` with pre- and post-model sections; CI job that installs the previous release, adds data, upgrades to the branch and runs `bench migrate`.
  - **Verify (UI):** Upgrade job green on a pull request that adds a field with a patch.
  - **Commit:** `ci: upgrade test`

---

## M. Deployment and operations

- [ ] **FMS-M01 · Prototyping · Choose the hosting model** · S · —
  - **Skills:** `frappe-ops-deployment`, `frappe-ops-cloud`
  - **Description:** Compare Frappe Cloud, a VPS with `bench setup production`, and Docker (`frappe_docker`). Record the choice and the deployment decision D1 (shared site or separate sites) in `docs/decisions.md`.
  - **Verify:** Owner signs off the decision in the pull request.
  - **Commit:** `docs: hosting decision`

- [ ] **FMS-M02 · Deploy · Staging server** · M · M01, L03
  - **Skills:** `frappe-ops-deployment`, `frappe-ops-bench`
  - **Description:** Staging site with the same versions as production, SSL, the app installed from a tag.
  - **Verify (UI):** https://staging… opens; *About* shows the tagged version.
  - **Commit:** `docs: staging runbook`

- [ ] **FMS-M03 · Deploy · Production server** · M · M02
  - **Skills:** `frappe-ops-deployment`
  - **Description:** Production with nginx, supervisor (or Docker), SSL, firewall, separate DB credentials, `developer_mode` off, scheduler on, email account configured.
  - **Verify (CLI):** `bench doctor` reports workers and scheduler healthy; **(UI)** login over HTTPS.
  - **Commit:** `docs: production runbook`

- [ ] **FMS-M04 · Configure · Backups and restore drill** · S · M03
  - **Skills:** `frappe-ops-backup`
  - **Description:** Daily `bench backup --with-files` with encryption and off-site copy (offsite backups app in v16 or provider snapshots); weekly retention.
  - **Verify (CLI):** Restore last night's backup to a scratch site with `bench --site restore-test restore …`; shift counts match.
  - **Commit:** `docs: backup and restore runbook`

- [ ] **FMS-M05 · Configure · Monitoring and alerts** · S · M03
  - **Skills:** `frappe-core-logging`, `frappe-ops-performance`
  - **Description:** Uptime check, disk and DB size alerts, Error Log digest, failed job alerts, FMS Health email.
  - **Verify:** A test alert reaches the owner.
  - **Commit:** `docs: monitoring`

- [ ] **FMS-M06 · Configure · Performance settings** · S · M03
  - **Skills:** `frappe-ops-performance`
  - **Description:** Gunicorn workers, background workers for `long` queue, MariaDB buffer pool, Redis memory per expected load.
  - **Verify (CLI):** Background close of a 250-row shift finishes under 60 seconds on production hardware.
  - **Commit:** `docs: performance settings`

- [ ] **FMS-M07 · Deploy · Deployment pipeline** · M · M03, L03
  - **Skills:** `frappe-ops-app-lifecycle`, `frappe-ops-deployment`
  - **Description:** Scripted deploy of a tag: backup, `bench get-app`/`git pull` the tag, `bench migrate`, `bench build --app forecourt`, restart; rollback steps documented.
  - **Verify (CLI):** Deploying `v0.1.1` to staging takes one command and keeps data.
  - **Commit:** `chore(deploy): deployment script`

- [ ] **FMS-M08 · Configure · Upgrade policy** · S · M07
  - **Skills:** `frappe-ops-upgrades`
  - **Description:** Monthly minor upgrades of frappe, erpnext and hrms on staging first, with the golden-month scenario as a regression test.
  - **Verify:** First monthly upgrade done on staging with K01 passing.
  - **Commit:** `docs: upgrade policy`

---

## N. Pilot and go-live

- [ ] **FMS-N01 · Configure · Pilot station master data** · M · M03, K06
  - **Description:** Real company, accounts, station, tanks, calibration charts (or litres mode), dispensers, nozzles, meter readings, cashiers, credit customers and vehicles, price list, opening balances. Where the pilot ran on the Odoo prototype, take masters, meter positions and closing dips from its last closed shift; no transactional history is migrated, and the Odoo database is kept read-only (design guide D33).
  - **Verify (UI):** Onboarding checklist complete; opening stock posted with Stock Reconciliation matching a physical dip.
  - **Commit:** none (data).

- [ ] **FMS-N02 · Deploy · Parallel run** · L · N01
  - **Description:** Two weeks of shifts in the FMS alongside the current process.
  - **Verify:** Daily comparison sheet: litres, cash and stock agree; differences explained.
  - **Commit:** none.

- [ ] **FMS-N03 · Bug fix · Pilot fixes** · M · N02
  - **Description:** Fix pilot findings, each as a Bug log task.
  - **Verify:** No open blocker in the Bug log.
  - **Commit:** per fix.

- [ ] **FMS-N04 · Deploy · Go-live** · S · N03
  - **Description:** Stop the old process at the pilot station; FMS is the record.
  - **Verify:** First month-end closed with FMS reports and ERPNext financial statements.
  - **Commit:** `chore: go-live v1.0.0` (tag).

- [ ] **FMS-N05 · Documentation · Rollout playbook for further stations** · S · N04
  - **Description:** Checklist and timings learned from the pilot for onboarding each additional station.
  - **Verify:** Second station onboarded with the playbook in one day.
  - **Commit:** `docs: rollout playbook`

---

## P. Later phases (backlog)

Each epic is split into tasks in this file when it is scheduled.

| Epic | Phase | Scope (design guide) |
|---|---|---|
| P1. Group sync for separate-site deployment | when D1 requires | Section 4.2a: ledger and trial balance sync to a group site |
| P2. More payment and fiscal adapters | 3 | Airtel, MTN MoMo, EVC Plus, Zaad, card acquirer APIs; ZATCA, VFD, EFRIS… |
| P3. Handheld POS app | 4 | Section 12.4: cashier app, credit at the pump, STK push, per-transaction receipts, offline sync |
| P4. Dedicated Shift Close page | 4 | Section 16.4: mobile-first Frappe UI page over the same server methods |
| P5. Edge bridge, ATG and FCC drivers | 5 | Section 12.5 |
| P6. Loyalty and fleet cards | later | Section 17.3 |
| P7. Temperature compensation | when a market needs it | Section 5.8: standard volumes at 15 °C from ASTM D1250 / API MPMS 11.1 tables (D30) |
| P8. Scheduled price changes | when needed | Section 6.5a: approve a Fuel Price Change in advance and apply it at `effective_at` (D24) |

---

## Bug log

Add bugs here as they are found. Each bug becomes a task with the same format.

| ID | Found in | Description | Task | Status |
|---|---|---|---|---|
| | | | | |

Template:

```
- [ ] **FMS-BUG-001 · Bug fix · <short title>** · S · <task where found>
  - **Skills:** frappe-agent-debugger, <relevant errors-* skill>
  - **Description:** steps to reproduce, expected, actual
  - **Expectation:** the bug no longer reproduces and a test covers it
  - **Verify:** <UI steps or test command>
  - **Commit:** fix(<module>): <subject>
```

