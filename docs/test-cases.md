# AFMS Test Case Catalogue

**Version:** 1.0 (draft for review)
**Date:** 2026-11-06
**Applies to:** the `forecourt` app (AFMS) on Frappe Framework v16 and ERPNext v16 (HRMS v16 optional)
**Companion documents:** [fms.md](fms.md) v1.3 (behaviour; 16.3 testing) · [catalogue.md](catalogue.md) v1.2 (DocTypes, fields) · [TASKS.md](../TASKS.md) v1.1 (sections I, K, L, N) · [reporting-catalogue.md](reporting-catalogue.md) v1.0 (section 29, report tests) · [ui-ux-design-guide.md](ui-ux-design-guide.md) v1.0 · [fms-nonfuel.md](fms-nonfuel.md) v0.2 (proposed)
**Audience:** developers, AI coding agents writing tests, QA, the owner, auditors

AFMS posts money and stock. A wrong number is not a cosmetic bug: it is a missing shilling in a cashier's balance, a litre of diesel that disappears from the books, or a fraud that goes unseen. This catalogue therefore tests **every corner**, including situations that rarely or never happen at a well-run station: power cuts in the middle of a close, a provider sending the same payment three times, a meter rolling over to exactly the opening value, a correction made after the next shift has closed.

It defines what is tested, how, with what data, and what "passing" means before a release, a pilot or a go-live.

---

## How to read this catalogue

### Test case format

Each area has a table with one row per test case:

| Column | Meaning |
|---|---|
| **ID** | `TC-<AREA>-nnn`. Never reused, never renumbered. |
| **Case** | The situation: given what, when what |
| **Expected** | What must happen. A coded message is written as its code (for example FMS-S101); its wording is in fms.md 15.3. |
| **Pri** | Priority (below) |
| **Lyr** | Test layer (below) |
| **Ref** | The specification it checks (fms.md section unless stated: *cat* = catalogue.md, *nf* = fms-nonfuel.md, *ux* = UI/UX guide, *rc* = reporting catalogue) |

### Priorities

| Pri | Meaning | Release rule |
|---|---|---|
| **P0** | Money, stock or accounting could be wrong, lost or duplicated; a security breach; a fraud control bypassed | Must pass on every build. No waivers. |
| **P1** | A control or validation is missing, a report is wrong, a workflow can be bypassed by a user | Must pass for a release; a waiver needs the owner's signature |
| **P2** | Wrong or unclear message, poor recovery, minor report presentation | Should pass; tracked |
| **P3** | Cosmetic | Tracked |

### Layers

| Lyr | Layer | Tool |
|---|---|---|
| **U** | Pure calculation (no database) | pytest / Frappe `UnitTestCase`, Hypothesis for properties |
| **D** | Document behaviour (validate, gates, submit) | Frappe `IntegrationTestCase` |
| **A** | Accounting integrity (GL, Stock Ledger, balances) | Integration tests with invariant checks (section 4) |
| **E** | End-to-end scenario | Fixture-driven scenario runner (golden month, FMS-K01) |
| **C** | Concurrency and race conditions | Parallel workers against a test site |
| **R** | Resilience: faults injected, recovery | Fault injection (monkeypatching, killed workers, stopped services) |
| **S** | Security | Integration tests, API calls as other users, scanners |
| **P** | Performance and volume | Load data sets, timing, `EXPLAIN` |
| **M** | Manual or UI | Test scripts, Playwright later |

### Expected results that the specs do not define

Some worst cases are not covered by the specifications. Such cases are marked **Open** in the *Expected* column, with a *proposed* behaviour in italics. They are collected in [section 39](#39-open-questions) and must be decided before the test is written. A test is never written against a behaviour nobody decided.

### Status

This catalogue specifies tests; it does not report results. TASKS.md shows FMS-I05 (permission tests) done and FMS-K01 (golden month) not started. Unit and document tests written inside the F, G and H tasks are not itemised in TASKS.md. Task FMS-T01 (section 37) maps existing tests to these IDs.

---

## Table of contents

1. [Purpose and quality bar](#1-purpose-and-quality-bar)
2. [Test strategy](#2-test-strategy)
3. [Test data and fixtures](#3-test-data-and-fixtures)
4. [Invariants: what must always be true](#4-invariants-what-must-always-be-true)
5. [Property-based and fuzz testing](#5-property-based-and-fuzz-testing)
6. [Calculations](#6-calculations)
7. [Masters and settings](#7-masters-and-settings)
8. [Shift creation and continuity](#8-shift-creation-and-continuity)
9. [Meter readings](#9-meter-readings)
10. [Dips and tank reconciliation](#10-dips-and-tank-reconciliation)
11. [Deliveries](#11-deliveries)
12. [Own use, pump tests, transfers and meter changes](#12-own-use-pump-tests-transfers-and-meter-changes)
13. [Prices and price segments](#13-prices-and-price-segments)
14. [Cashiers, cash, floats and drops](#14-cashiers-cash-floats-and-drops)
15. [Mobile money, cards and payment imports](#15-mobile-money-cards-and-payment-imports)
16. [Credit customers and vehicles](#16-credit-customers-and-vehicles)
17. [Expenses](#17-expenses)
18. [Shift gates](#18-shift-gates)
19. [Posting and accounting integrity](#19-posting-and-accounting-integrity)
20. [Approvals and workflow](#20-approvals-and-workflow)
21. [Corrections](#21-corrections)
22. [Cancellation and immutability](#22-cancellation-and-immutability)
23. [Period close and back-dating](#23-period-close-and-back-dating)
24. [Ledgers and reports](#24-ledgers-and-reports)
25. [Integrations](#25-integrations)
26. [Concurrency and race conditions](#26-concurrency-and-race-conditions)
27. [Failure, recovery and chaos](#27-failure-recovery-and-chaos)
28. [Time, dates and time zones](#28-time-dates-and-time-zones)
29. [Numbers, precision and rounding](#29-numbers-precision-and-rounding)
30. [Security](#30-security)
31. [Fraud scenarios](#31-fraud-scenarios)
32. [Multi-company, multi-currency, multi-jurisdiction](#32-multi-company-multi-currency-multi-jurisdiction)
33. [Upgrades, migration and go-live](#33-upgrades-migration-and-go-live)
34. [Performance and volume](#34-performance-and-volume)
35. [User interface and messages](#35-user-interface-and-messages)
36. [Non-fuel and Mode B (proposed)](#36-non-fuel-and-mode-b-proposed)
37. [Release gates, exit criteria and test management](#37-release-gates-exit-criteria-and-test-management)
38. [Traceability: error codes to tests](#38-traceability-error-codes-to-tests)
39. [Open questions](#39-open-questions)

---

## 1. Purpose and quality bar

### 1.1 What "battle-tested" means for AFMS

| Property | Meaning | How it is proven |
|---|---|---|
| **Correct** | Every posted figure equals what the readings, dips, counts and payments say | Invariants (section 4) checked after every test that posts |
| **Complete** | Nothing is lost: every litre, every payment, every message | Conservation invariants; inbox replay; atomic close |
| **Exactly once** | Nothing is posted twice: no duplicate payment, invoice or ledger row | Idempotency and concurrency tests |
| **Atomic** | A close or a correction either fully happens or not at all | Fault injection at every step (section 27) |
| **Immutable** | Closed data never changes in place; history is preserved | Immutability tests (section 22) |
| **Controlled** | No user can bypass a gate, an approval or a permission | Gate, workflow and security tests |
| **Explainable** | Every failure tells the user what to do; no traceback | Message tests (section 35) |
| **Robust** | Wrong, extreme, malicious and out-of-order inputs are rejected cleanly | Fuzz, numeric, time and security tests |
| **Fast enough** | Targets of FMS-H12 and the 10-minute close | Performance tests (section 34) |

### 1.2 Out of scope

- ERPNext's own correctness (GL engine, stock valuation algorithms) is trusted; AFMS tests check that AFMS **uses** them correctly and that the results agree with AFMS's own figures.
- Provider systems (M-Pesa, acquirers, fiscal authorities) are simulated; their real sandboxes are used in the integration acceptance runs only (section 25.5).

---

## 2. Test strategy

### 2.1 The test pyramid for AFMS

| Layer | Share of cases | Runs | Speed target |
|---|---|---|---|
| U: calculations, properties | Many (fast, exhaustive) | Every commit | Under 1 minute total |
| D: documents and gates | Many | Every commit | Under 10 minutes |
| A: accounting integrity | Every posting test also runs the invariant checker | Every commit | Included in D |
| E: scenarios, golden month | One golden month plus about 40 scenario scripts | Every merge to main, nightly | Under 30 minutes |
| C, R: concurrency and resilience | About 60 cases | Nightly and before release | Under 1 hour |
| S: security | About 50 cases plus scanners | Nightly and before release | |
| P: performance | Volume set | Weekly and before release | Section 34 targets |
| M: manual and UI | Scripts | Before release, UAT | |

### 2.2 Environments

| Environment | Purpose | Data |
|---|---|---|
| CI site (`test_fms`) | U, D, A, E on every pull request (FMS-L01) | Fixtures only, rebuilt each run |
| Nightly site | C, R, S, golden month, property runs with more examples | Fixtures, larger random sets |
| Performance site | P | Generated volume set (section 34) |
| Staging | Release candidate, manual tests, provider sandboxes | Anonymised copy or fixtures |
| Pilot | Parallel run (FMS-N02) | Real station data |

Every environment runs the same Frappe, ERPNext and HRMS versions, Python 3.14 and Node 24 (FMS-L01).

### 2.3 Principles

| # | Principle |
|---|---|
| T1 | **Every test that posts checks the invariants.** A shared `assert_invariants(shift)` runs after every submit, correction and cancel (section 4). |
| T2 | **Exact amounts.** Money and litres are compared exactly (as stored, at their precision), never with a tolerance, unless the specification states one. |
| T3 | **Deterministic.** Time is frozen (`freezegun` / Frappe's time helpers), random seeds are fixed and printed, test data has fixed names. |
| T4 | **Independent.** Each test creates its own data or rolls back; order does not matter. |
| T5 | **One reason to fail.** A test checks one behaviour; scenario tests check many but report each check separately. |
| T6 | **The code is cited.** Every negative test asserts the FMS error code, not just that something failed. |
| T7 | **Failures are atomic.** Every negative posting test also asserts that nothing was written (document and ledger counts unchanged). |
| T8 | **Real stack.** D, A and E tests run against MariaDB and Redis as in production, not mocks; only external providers are simulated. |

---

## 3. Test data and fixtures

### 3.1 Canonical stations

| Station | Code | Company | Currency | Time zone | Purpose |
|---|---|---|---|---|---|
| Westlands | `KE-NBO-WSTL` | Anika Test Ltd (KE) | KES | Africa/Nairobi | Main station: 2 islands, 4 pumps, 8 nozzles, 3 tanks (PMS 30,000 L, AGO 30,000 L, AGO 15,000 L sharing one product), E-cash only, chart mode |
| Thika Road | `KE-NBO-THKA` | Anika Test Ltd (KE) | KES | Africa/Nairobi | Second station in the same company; three meters recorded, basis *Highest*, litres-direct dip mode on one tank |
| Mogadishu Airport Road | `SO-MGQ-AIRP` | Horn Test Co (SO) | USD | Africa/Mogadishu | Multi-currency cash (USD and SOS), different company, different chart of accounts |
| DST test | `XX-DST-TEST` | Anika Test Ltd (KE) | KES | Europe/Berlin | Time-zone and daylight-saving cases only (section 28) |
| Zero-decimal | `UG-KLA-ZERO` | Kampala Test Ltd | UGX | Africa/Kampala | Currency without decimals (section 29) |

### 3.2 Canonical masters

| Master | Fixture content |
|---|---|
| Items | PMS (petrol), AGO (diesel), DPK (kerosene) as fuel items; Engine oil 4 L, Brake fluid 500 ml as non-fuel |
| Tanks | Each with a calibration chart (rows every 10 mm), a second chart version valid from the 15th of the golden month for one tank |
| Nozzles | Meter maximum 999,999.99 on most; 99,999.99 on one nozzle (rollover tests); test limit 20 L on two nozzles |
| Shift templates | Day 06:00–18:00 and Night 18:00–06:00 (overnight); Westlands also has a three-shift template set for one test |
| Cashiers | Amina, John, Fatuma, Peter (Westlands); Abdi, Hodan (Mogadishu); one disabled Employee |
| Customers | Coast Haulage (credit limit 500,000, three vehicles, one limited to AGO), Rift Movers (frozen), Walk-in per station |
| Payment providers | M-Pesa (till 123456 Westlands, 654321 Thika), card acquirer (terminals T-01, T-02), EVC Plus (Mogadishu) |
| Users | One per role per station: station manager, assistant, supervisor, cashier, accountant, area manager (group Nairobi), director, investor (company KE only), administrator, System Manager, integration user |
| Settings | Tolerances at the defaults of fms.md 5.6; drift tolerance 0.5% or 2 L; `allow_backdated_shift_days` = 2; background close above 200 payment rows |

### 3.3 Factories

Test code builds data through factories in `forecourt/tests/factories.py`, never by hand: `make_station()`, `make_shift(station, template, date, readings=…, dips=…, cashiers=…)`, `make_grn(tank, invoiced, dip_before, dip_after, at=…)`, `make_feed(provider, till, amount, ref, at=…)`, `close(shift)`, `correct(shift, type, …)`. Factories use the real controllers (no direct SQL inserts), so tests exercise the same path as users.

### 3.4 The golden month (FMS-K01)

Two stations, 30 days, Day and Night shifts (about 120 shifts), with a known answer for every figure:

| Ingredient | Count |
|---|---|
| Normal shifts | ~100 |
| Shortages (charged, written off, approved) | 8 |
| Excesses | 3 |
| Deliveries (normal, short beyond tolerance, during a shift, two in one shift) | 14 |
| Mid-shift price changes | 2 |
| Cashier handovers | 6 |
| Rollovers | 2 |
| Meter change | 1 |
| Own use entries | 10 |
| Pump tests | 15 |
| Credit slips (including one over-limit approved) | 120 |
| Mobile money transactions (including duplicates and late callbacks) | 4,000 |
| Card transactions | 600 |
| Corrections (one of each type) | 5 |
| Month-end close of the accounting period | 1 |

**Expected answers** are stored in `tests/golden/expected.json`: per shift (litres, amounts, differences), per tank (closing book, variance), per cashier (statement closing), per account (GL closing), per report (totals). The run passes when every figure matches exactly.

### 3.5 Simulators

| Simulator | Behaviour it can produce |
|---|---|
| Mobile money provider | Normal callback; duplicate callback; callback out of order; late callback (hours, days); reversal; malformed payload; wrong till; wrong signature; timeout on outbound STK push |
| Card acquirer | Settlement file with fees; missing transaction; extra transaction; split batch; file in a new format |
| Bank | Statement with matching and non-matching lines; duplicate statement import |
| Fiscal authority | Accept; reject with a code; timeout; accept after retry; down for hours |
| Clock | Frozen time; jumps; device clock skew (Mode B) |
| Faults | Exception at a named step of posting; database connection lost; worker killed; Redis stopped; disk full (section 27) |

---

## 4. Invariants: what must always be true

The invariant checker `forecourt.tests.invariants.assert_invariants(scope)` runs after every test that posts or corrects anything. A failing invariant is always **P0**.

| # | Invariant | Check |
|---|---|---|
| INV-01 | **Till equals counted cash.** For every cashier and currency, the till account movement from the shift equals cash counted − float (plus the float transfer when *Returned to safe*, D27) − drops posted | GL Entries of the shift's vouchers on the till account |
| INV-02 | **Book stock equals the dip.** For every tank with a closing dip, the tank warehouse quantity at the shift's last posting time equals the dip volume | Stock Ledger Entry balance |
| INV-03 | **Sales equal metered value.** Σ grand totals of the shift's Sales Invoices and Delivery Notes = Σ fuel amount (net litres × segment price) + Σ non-POS item amounts | Documents vs Nozzle Ledger |
| INV-04 | **Accounted equals posted.** For every cashier: mobile + card + credit + voucher + cash + expenses + drops = the sum of the corresponding Payment Entries, invoice values and Journal Entry lines | Cashier Ledger vs documents |
| INV-05 | **Balanced.** Every voucher's debits equal its credits; the trial balance is balanced | GL |
| INV-06 | **No unresolved difference.** Every submitted shift: Σ cashier differences − Σ resolutions = 0 | Shift Cashier, Shift Resolution |
| INV-07 | **Continuity.** For every nozzle and meter, the opening of each shift equals the closing of the previous submitted shift (or the Meter Change start value), and `Nozzle.last_*` equals the latest closing | Nozzle Ledger, Nozzle |
| INV-08 | **Litres conserved.** For every tank and shift: opening + receipts − net sales − own use ± transfers − variance = closing dip, exactly | Wetstock Ledger |
| INV-09 | **Ledger equals ERPNext.** Σ Nozzle Ledger `net_l` of a shift per tank = stock issued from that tank by the shift's sales documents; Σ Wetstock `variance_l` = Stock Reconciliation quantity difference | Ledgers vs Stock Ledger |
| INV-10 | **Linked.** Every document a close or correction creates carries `fms_forecourt_shift` and the Station dimension | Documents |
| INV-11 | **Ledgers are append-only.** No ledger row was updated after insert except `is_cancelled`, `superseded_by` | `modified` vs `creation`, audit log |
| INV-12 | **Exactly once.** No external id appears twice in Integration Inbox per provider; no provider reference appears on two submitted collections; no FCC transaction on two invoices (Mode B) | Unique checks |
| INV-13 | **Atomic.** After any failed close or correction, no document, GL Entry, Stock Ledger Entry or ledger row exists for it | Counts before and after |
| INV-14 | **Clearing equals unsettled.** Each clearing account balance equals Σ of its Payment Entries not yet transferred to the bank | GL vs Payment Entry |
| INV-15 | **Receivable equals statements.** Staff Shortage Receivable per Employee equals the closing of CSH-01; customer receivable equals the customer statement | GL vs reports |
| INV-16 | **Never negative.** No tank warehouse has negative stock at any posting time | Stock Ledger |
| INV-17 | **Corrections are consistent.** After a correction, non-superseded ledger rows of the corrected shift and the next shift satisfy INV-01 to INV-09 | Re-run checker on both shifts |
| INV-18 | **Splits add up.** Every allocation (attribution of payment types, split resolutions, currency conversions) sums exactly to its total, with the rounding remainder on one defined line | Sales Ledger, resolutions |
| INV-19 | **Valuation settles.** After all Repost Item Valuation entries finish, GL stock accounts equal the Stock Ledger value per warehouse | ERPNext stock vs GL |
| INV-20 | **Scoped.** No report or API response contains rows of stations or companies outside the user's permissions | Permission tests |

---

## 5. Property-based and fuzz testing

Hand-written cases cover what people think of. Generated cases find what nobody thought of.

### 5.1 Property tests (Hypothesis)

| ID | Property | Generator | Examples per run |
|---|---|---|---|
| TC-PBT-001 | For any valid shift, close succeeds and INV-01 to INV-11 hold | 1–40 nozzles, 1–3 meters, readings with optional rollover, 1–3 price segments, 1–6 cashiers with handovers, 0–500 payments, 0–3 deliveries, random dips within ±2% of expected | 200 (CI), 10,000 (nightly) |
| TC-PBT-002 | For any valid shift and any single typing error corrected by a Shift Correction, INV-17 holds | TC-PBT-001 plus a random correction of a random type | 100 / 2,000 |
| TC-PBT-003 | Calculation functions are total and consistent: rollover sold ≥ 0; drift symmetric (A−B = −(B−A)); variance % sign follows variance | Random numbers incl. extremes | 10,000 / 100,000 |
| TC-PBT-004 | Calibration interpolation is monotonic: deeper dip → more litres; exact chart points return the chart value | Random strictly increasing charts, random depths | 10,000 |
| TC-PBT-005 | Attribution of payment types sums exactly to the cashier's collections per type (INV-18) | Random sales lines and collections | 10,000 |
| TC-PBT-006 | Closing a sequence of N shifts and correcting a random one never breaks continuity (INV-07) | Sequences of 2–20 shifts | 100 / 1,000 |
| TC-PBT-007 | Any order of arrival of the same set of feed entries (shuffled, duplicated) yields the same matched set | Permutations with duplicates | 500 |

Shrunk failing examples are saved as regression tests automatically (Hypothesis database committed for the nightly site).

### 5.2 Fuzzing invalid input

| ID | Target | Input | Expected |
|---|---|---|---|
| TC-FUZ-001 | Every editable shift field | Random strings, huge numbers, negative numbers, NaN, Infinity, empty, Unicode, SQL and HTML fragments | Rejected with a coded message or stored safely; never a traceback (HTTP 500) to the user; INV-13 |
| TC-FUZ-002 | Every whitelisted FMS method | Random arguments, missing arguments, wrong types, names of other stations' documents | Coded message or PermissionError; never a traceback |
| TC-FUZ-003 | Payment import files | Random CSV and Excel files: wrong columns, encodings, BOM, empty, 1 million rows, binary data | Rejected with a coded message; no partial rows created |
| TC-FUZ-004 | Webhook endpoints | Random JSON, oversized bodies, wrong content type, missing signature | 4xx response; nothing processed; malformed messages stored as Failed or rejected per 25.1 |
| TC-FUZ-005 | Calibration chart import | Random rows, duplicates, decreasing values, gaps | FMS-M605 naming the row |

### 5.3 Mutation testing

`forecourt/calc/` (pure calculations) is mutation-tested (`mutmut` or `cosmic-ray`) weekly. Target: **mutation score ≥ 90%**; each surviving mutant gets a test or a documented reason.

---

## 6. Calculations

Pure functions in `forecourt/calc/`. Every case is a unit test (U) with exact values.

### 6.1 Meters

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CAL-001 | Normal: opening 1,000.00, closing 1,250.50 | Sold 250.50 | P0 | U | 5.3 |
| TC-CAL-002 | Closing equals opening | Sold 0.00 | P0 | U | 5.3 |
| TC-CAL-003 | Closing < opening, no rollover tick | Error FMS-S101 | P0 | U | 5.3 |
| TC-CAL-004 | Rollover: max 999,999.99, opening 999,900.00, closing 50.00, ticked | Sold = (max − opening) + closing = 150.00 (with the meter's own definition of max: confirm whether the counter passes through 0.00, giving +0.01) | P0 | U | 5.3 |
| TC-CAL-005 | Rollover ticked but closing ≥ opening | **Open Q-01:** is a tick with no rollover an error? *Proposed: refuse the tick (coded message); sold = closing − opening.* | P0 | U | 5.3 |
| TC-CAL-006 | Rollover ticked and closing exactly equals opening | **Open Q-02:** a full cycle (≈1 million litres in a shift) is implausible. *Proposed: refuse; a nozzle cannot sell its full meter range in one shift.* | P0 | U | 5.3 |
| TC-CAL-007 | Value above meter maximum | FMS-W102 | P0 | U | 5.3 |
| TC-CAL-008 | Rollover on one meter only (E-cash rolls, E-vol does not) | Each meter computed independently; drift uses each meter's own sold value | P0 | U | 5.3 |
| TC-CAL-009 | Basis E-cash: Δ E-cash 18,000.00 at price 180.00 | Litres 100.00 | P0 | U | 5.3 |
| TC-CAL-010 | Basis E-cash with a price that does not divide evenly: Δ 1,000.00 at 183.47 | Litres rounded to the litre precision; the amount stays exactly 1,000.00; the rounding rule is documented and identical in shift and reports | P0 | U | 5.3, 29 |
| TC-CAL-011 | Basis E-vol: Δ 100.00 L at 180.00 | Amount 18,000.00 | P0 | U | 5.3 |
| TC-CAL-012 | Basis *Highest* with three meters: E-cash 101 L, E-vol 100 L, M-vol 99 L | Basis = E-cash (101 L); the winning meter is recorded on the segment | P0 | U | 5.3 |
| TC-CAL-013 | Basis *Highest*, tie between two meters | The tie-break is deterministic and documented (*proposed*: order E-cash, E-vol, M-vol) | P1 | U | 5.3 |
| TC-CAL-014 | Drift E-vol vs M-vol within 0.5% / 2 L (the larger applies) | No drift flag | P1 | U | 5.3 |
| TC-CAL-015 | Drift exactly at the tolerance boundary | Within tolerance (boundary inclusive) **Open Q-03:** inclusive or exclusive? *Proposed: inclusive.* | P1 | U | 5.3 |
| TC-CAL-016 | Drift on a segment with 1 L sold and 0.5 L drift (50%) | Absolute limit 2 L applies; no flag | P1 | U | 5.3 |
| TC-CAL-017 | Net sold = basis litres − test − own use; test 5 L, own use 20 L, basis 300 L | Net 275 L | P0 | U | 5.3 |
| TC-CAL-018 | Own use + test greater than basis litres | Error (net sold cannot be negative). **Open Q-04:** code? *Proposed: new FMS-W1xx code.* | P0 | U | 5.3 |
| TC-CAL-019 | Basis meter not recorded on the nozzle | FMS-M603 | P0 | U | 5.3 |

### 6.2 Calibration and dips

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CAL-030 | Depth exactly on a chart row | Chart volume exactly | P0 | U | 5.2 |
| TC-CAL-031 | Depth between rows 1,230 and 1,240 mm at 1,234 mm | Linear interpolation, rounded to litre precision | P0 | U | 5.2 |
| TC-CAL-032 | Depth 0 mm | Volume of row 0 (dead stock or 0) | P0 | U | 5.2 |
| TC-CAL-033 | Depth below the first row (chart starts at 50 mm) | **Open Q-05:** extrapolate, use 0, or refuse? *Proposed: refuse with a coded message naming the chart's minimum.* | P1 | U | 5.2 |
| TC-CAL-034 | Depth above the last row | FMS-T202 | P0 | U | 5.2 |
| TC-CAL-035 | Water depth converted and subtracted | Product volume = volume(product depth) − volume(water depth) | P0 | U | 5.2 |
| TC-CAL-036 | Water depth greater than product depth | Refused (impossible reading). **Open Q-06:** code. | P0 | U | 5.2 |
| TC-CAL-037 | Two chart versions; dip dated the day before the new version | Old chart used | P0 | U | 5.2 |
| TC-CAL-038 | Dip dated exactly at `valid_from` of the new chart | New chart used (valid from is inclusive) | P0 | U | 5.2 |
| TC-CAL-039 | No chart valid on the date, chart mode | FMS-T201 | P0 | U | 5.2 |
| TC-CAL-040 | Litres-direct mode | Litres used as given; T201 and T202 do not apply | P0 | U | 5.2 |
| TC-CAL-041 | Chart last volume 2.5% away from tank capacity | Warning (more than 2%), saves | P2 | D | 5.2 |

### 6.3 Tank reconciliation and tolerances

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CAL-050 | Expected = opening + receipts − net sales − own use ± transfers | Exact | P0 | U | 5.5 |
| TC-CAL-051 | Variance = dip − expected; % = variance ÷ net sales × 100 | Exact, sign kept | P0 | U | 5.5 |
| TC-CAL-052 | Net sales zero, variance −5 L | Variance % undefined: no division by zero; tolerance in litres applies (±20 L) | P0 | U | 5.6 |
| TC-CAL-053 | Variance −25 L on sales 10,000 L (−0.25%): % limit 0.5% = 50 L, absolute 20 L; larger limit applies | Within tolerance | P0 | U | 5.6 |
| TC-CAL-054 | Variance −60 L on 10,000 L | Outside; reason required | P0 | U | 5.6 |
| TC-CAL-055 | Variance −101 L on 10,000 L (approval threshold 2× tolerance = 100 L) | Outside and needs approval | P0 | U | 5.6 |
| TC-CAL-056 | Variance exactly at the tolerance and exactly at the approval threshold | Boundary rule as TC-CAL-015 | P1 | U | 5.6 |
| TC-CAL-057 | Positive variance (gain) of the same sizes | Same tolerance rules (± tolerance) | P0 | U | 5.6 |
| TC-CAL-058 | Tolerance overridden per tank and per station | Tank override wins over station, station over company | P1 | U | 5.6 |
| TC-CAL-059 | Cumulative 30-day variance −0.31% vs ±0.3% | Flag in daily report and alert | P1 | U | 5.6 |
| TC-CAL-060 | No dip taken (template does not require one) | Opening of next shift = book stock; no variance row for the tank | P0 | U | 5.5 |

### 6.4 Cashier balance

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CAL-070 | The worked example of fms.md 8.2 | Expected 375,000; accounted 374,500; difference −500 (or the exact figures of 8.2) | P0 | U | 8.2 |
| TC-CAL-071 | Cash counted below float | Cash for the shift negative; accounted reduced; difference shortage | P0 | U | 7.2 |
| TC-CAL-072 | Debt receipt in cash: expected and accounted both rise by the receipt | Difference unchanged | P0 | U | 7.2 |
| TC-CAL-073 | Drops counted on the accounted side; cash in drawer lower | Difference unchanged by drops | P0 | U | 7.2 |
| TC-CAL-074 | Credit slip value on the accounted side, its litres inside metered expected | Difference zero for a pure credit sale | P0 | U | 7.2 |
| TC-CAL-075 | Cashier with readings but no collections at all | Difference = −expected (whole amount short) | P0 | U | 7.2 |
| TC-CAL-076 | Cashier with collections but no readings (cash collected for a colleague) | Difference = + collections; must be resolved (excess) or reassigned | P1 | U | 7.2 |

### 6.5 Price segments and attribution

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CAL-080 | Two segments 180 and 185 with readings at 14:00 | Litres and amounts split exactly per segment | P0 | U | 6.5a |
| TC-CAL-081 | Three segments in one shift | Three reading rows per affected nozzle; totals exact | P0 | U | 6.5a |
| TC-CAL-082 | Segment with zero litres on a nozzle | Row with 0 sold; no error | P1 | U | 6.5a |
| TC-CAL-083 | Attribution: remaining sales 60% PMS 40% AGO, mobile 180,000 | PMS 108,000, AGO 72,000 | P0 | U | 10.4 |
| TC-CAL-084 | Attribution with a remainder: 100.00 over three equal lines | 33.33, 33.33, 33.34; remainder on the largest line (or the documented rule) | P0 | U | 10.4, INV-18 |
| TC-CAL-085 | Attribution when credit slips exhaust a product (no remaining PMS) | Nothing attributed to PMS; no division by zero | P0 | U | 10.4 |

---

## 7. Masters and settings

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-MST-001 | Station code `westlands` | FMS-M601 | P1 | D | 15.3 |
| TC-MST-002 | Station code duplicated across companies | Refused (code unique) | P1 | D | cat 5 |
| TC-MST-003 | Till account of another company on Station | FMS-M602 | P0 | D | 15.3 |
| TC-MST-004 | Till account of the wrong type (an expense account) | FMS-M602 | P0 | D | 15.3 |
| TC-MST-005 | Sales basis E-vol while only E-cash recorded | FMS-M603 | P0 | D | 15.3 |
| TC-MST-006 | Dispenser override with basis outside its recorded meters | FMS-M603 (D23) | P0 | D | 5.3 |
| TC-MST-007 | Tank capacity 0, or safe fill above capacity | FMS-M604 | P1 | D | 15.3 |
| TC-MST-008 | Chart row 42 depth below row 41 | FMS-M605 (row named) | P1 | D | 15.3 |
| TC-MST-009 | Chart with equal volumes on two rows | FMS-M605 (strictly increasing) | P1 | D | 5.2 |
| TC-MST-010 | Nozzle linked to a tank of another station | FMS-M606 | P0 | D | 15.3 |
| TC-MST-011 | Nozzle linked to a tank holding another product | Refused. **Open Q-07:** code (not in 15.3). *Proposed: FMS-M608.* | P0 | D | 5.1 |
| TC-MST-012 | Manual edit of `Nozzle.last_*` | FMS-M607 | P0 | D | 15.3 |
| TC-MST-013 | Edit `last_*` through the REST API as Administrator | FMS-M607 (enforced in the controller, not the UI) | P0 | S | 15.3 |
| TC-MST-014 | Change a tank's warehouse after shifts exist | **Open Q-08:** allowed? *Proposed: refused once any ledger row exists.* | P0 | D | 5.1 |
| TC-MST-015 | Change a tank's product after shifts exist | Refused (history would become wrong). **Open Q-09:** code. | P0 | D | 5.1 |
| TC-MST-016 | Delete a tank, nozzle or station with history | Refused by link checks | P0 | D | |
| TC-MST-017 | Deactivate a nozzle while a shift is open with its row | **Open Q-10:** remove the row, keep it, or block? *Proposed: block deactivation while a draft shift includes it.* | P1 | D | 5.3 |
| TC-MST-018 | Mode of Payment without an account for the company | FMS-P301 at close (and ideally at setup) | P0 | D | 15.3 |
| TC-MST-019 | Tolerance settings negative or zero | Refused | P1 | D | 5.6 |
| TC-MST-020 | Shift template times overlapping another template of the station (Day 06–18, Night 17–06) | **Open Q-11:** blocked at template level or only at shift level (FMS-S110)? *Proposed: warn on the template, block at the shift.* | P1 | D | 6.1 |
| TC-MST-021 | Template with no cashiers | Saves; shifts from it fail FMS-S104 until assigned | P2 | D | 6.1 |
| TC-MST-022 | Station time zone changed after shifts exist | **Open Q-12:** allowed? *Proposed: refused, or only effective for shifts created afterwards with a warning.* | P0 | D | 13 |

---

## 8. Shift creation and continuity

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-SHC-001 | Create a shift after a closed shift | Rows per active nozzle with openings locked to the previous closings; tanks with openings; roster; price segments; window from template and date | P0 | D | 6.3 |
| TC-SHC-002 | First shift ever at a station | Openings from `Nozzle.last_*` (set at onboarding) and tank opening stock | P0 | D | 6.3 |
| TC-SHC-003 | Opening reading edited by the user | Refused (read-only, locked) | P0 | D | 6.3 |
| TC-SHC-004 | Opening edited through the API | Refused by the controller (FMS-S102 at least) | P0 | S | 6.6 |
| TC-SHC-005 | Previous shift corrected after this shift was created | FMS-S102 until *Re-fetch openings* is used | P0 | D | 15.3 |
| TC-SHC-006 | Overnight shift Night 18:00–06:00 on 2026-11-06 | Window 2026-11-06 18:00 to 2026-11-07 06:00 (station time); posting date 2026-11-06 (D20) | P0 | D | 6.3 |
| TC-SHC-007 | Shift window overlapping a submitted shift | FMS-S110 at close | P0 | D | 6.6 |
| TC-SHC-008 | Two draft shifts at the same station at the same time | **Open Q-13:** allowed (D28)? *Proposed per ux 11.2: refused with FMS-S116 unless overlap allowed.* | P1 | D | ux 11.2 |
| TC-SHC-009 | New shift while the previous is Pending Approval | **Open Q-14:** allowed? Openings would come from an unsubmitted shift. *Proposed: refused (ux FMS-S117).* | P0 | D | ux 11.2 |
| TC-SHC-010 | Nozzle added to the station after this shift was created | **Open Q-15:** must the open shift get the row? *Proposed: a gate refuses close while an active nozzle has no row; a button adds missing rows.* | P0 | D | 6.6 |
| TC-SHC-011 | Nozzle out of service | Skipped in the shift; its reading must not change (5.3) | P1 | D | 5.3 |
| TC-SHC-012 | Out-of-service nozzle whose meter changed between shifts | **Open Q-16:** *Proposed: block return to service until a Meter Change explains the movement.* | P0 | D | 5.3 |
| TC-SHC-013 | Template changed (times) after shifts were created from it | Existing shifts keep their windows (snapshot); new shifts use the new times | P1 | D | 6.3 |
| TC-SHC-014 | Station settings changed (sales basis) while a shift is open | Open shift keeps its snapshot settings | P0 | D | ux 10.1 |
| TC-SHC-015 | No price in force for a fuel item at shift start | Creation refused (ux FMS-S118) | P0 | D | ux 11.2 |
| TC-SHC-016 | Shift date far in the past (beyond `allow_backdated_shift_days`) | Needs approval or refused (8.9) | P1 | D | 8.9 |
| TC-SHC-017 | Shift date in the future | **Open Q-17:** *Proposed: refused beyond the next scheduled slot.* | P1 | D | |
| TC-SHC-018 | A day with no trading (station closed): no shift at all | Next shift opens from the last closed; FMS Health reports the gap | P2 | E | 15.4 |
| TC-SHC-019 | Previous shift cancelled (whole-shift cancellation, C503) | New openings revert to the shift before it | P0 | D | 6.8 |
| TC-SHC-020 | Shift deleted while draft | Allowed for drafts; no ledger rows exist; continuity unaffected | P1 | D | |

---

## 9. Meter readings

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-MTR-001 | All closings entered, normal | Litres and amounts computed; cashier expected updated | P0 | D | 5.3 |
| TC-MTR-002 | One active nozzle without closing | FMS-S101 at close, naming the nozzle | P0 | D | 6.6 |
| TC-MTR-003 | Closing below opening, no tick | FMS-S101 | P0 | D | 6.6 |
| TC-MTR-004 | Reading row without cashier | FMS-S104 | P0 | D | 6.6 |
| TC-MTR-005 | Handover: two rows for one nozzle, intermediate reading | First row closes and second opens at the same value; each cashier gets their litres | P0 | D | 6.5 |
| TC-MTR-006 | Handover rows that do not chain (second opening ≠ first closing) | Refused. **Open Q-18:** code. | P0 | D | 6.5 |
| TC-MTR-007 | Handover intermediate reading outside the nozzle's opening–closing range | Refused | P0 | D | 6.5 |
| TC-MTR-008 | Three handovers on one nozzle in one shift | Four rows chained; totals equal single-row result | P1 | D | 6.5 |
| TC-MTR-009 | Same cashier on both handover rows | Allowed; combined in the balance | P2 | D | 6.5 |
| TC-MTR-010 | Drift beyond tolerance, station requires reason | FMS-W103 until a reason is given | P1 | D | 6.6 |
| TC-MTR-011 | Drift beyond tolerance, station set to *Warn* | Saves and closes with a flag | P1 | D | 5.3 |
| TC-MTR-012 | Litres far above the 30-day average | Warning only (fms.md 6.4), close allowed | P2 | D | 6.4 |
| TC-MTR-013 | Meter photo attached (optional evidence) | Stored on the row; visible in the Shift Report | P3 | D | 9.2 |
| TC-MTR-014 | Power cut, manual bypass: "manual meter adjustment with a reason" | **Open Q-19:** how is a manual adjustment represented (6.5)? *Proposed: a row field `manual_adjustment_l` with a mandatory reason, shown as an exception.* | P0 | D | 6.5 |
| TC-MTR-015 | Reading typed with a thousands separator or comma decimal (`105,230` in a locale using comma) | Parsed by the user's number format; stored correctly | P1 | M | 29 |
| TC-MTR-016 | Meter with three decimals on one pump (precision mismatch) | **Open Q-20:** precision per meter? (ux Q-12) | P1 | D | 29 |

---

## 10. Dips and tank reconciliation

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-DIP-001 | Tank requiring a dip without one | FMS-S103 | P0 | D | 6.6 |
| TC-DIP-002 | Variance outside tolerance, no reason | FMS-S106 | P0 | D | 6.6 |
| TC-DIP-003 | Variance above the approval threshold, reason given, not approved | FMS-S106 (approval); shift goes to Pending Approval | P0 | D | 5.6 |
| TC-DIP-004 | Rise beyond tolerance with no GRN | FMS-T203 | P0 | D | 6.6 |
| TC-DIP-005 | Rise explained by a GRN posted in the window | No T203; receipts include it | P0 | D | 5.4 |
| TC-DIP-006 | GRN posted with the wrong tank (rise in T1, GRN to T2) | T203 on T1 and a large loss on T2 | P0 | D | 5.4 |
| TC-DIP-007 | Two tanks with the same product, nozzles fed from one | Each tank reconciled with its own nozzles only | P0 | D | 5.1 |
| TC-DIP-008 | Dip in chart mode with a changed chart mid-month | Each dip uses the chart valid at its date (TC-CAL-037) | P0 | D | 5.2 |
| TC-DIP-009 | Tank switched from litres mode to chart mode | History unchanged; new dips use the chart | P1 | D | 5.2 |
| TC-DIP-010 | Spot dip (Tank Dip) submitted mid-shift | Recorded, posts nothing; book difference shown | P1 | D | cat 8.4 |
| TC-DIP-011 | Stock Reconciliation posted at close sets book = dip | INV-02 | P0 | A | 5.7 |
| TC-DIP-012 | Company posts variance only on last shift of the day | Day shift: no Stock Reconciliation; Night shift: one, with the day's variance | P0 | A | 5.7 |
| TC-DIP-013 | Company posts only when outside tolerance | Within tolerance: no adjustment; book drifts; next out-of-tolerance posting corrects all | P0 | A | 5.7 |
| TC-DIP-014 | Dip shows tank above capacity | **Open Q-21:** warning or block? *Proposed: block above capacity, warn above safe fill.* | P1 | D | 5.1 |
| TC-DIP-015 | Variance would make book stock negative before the reconciliation posts | Posting order (D35) prevents negative stock; INV-16 | P0 | A | 6.7 |
| TC-DIP-016 | Temperature and density recorded (compensation off) | Stored only; volumes unchanged (D30) | P2 | D | 5.8 |

---

## 11. Deliveries

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-DLV-001 | GRN into a tank without delivery dips (dips required) | FMS-T206 | P0 | D | 5.4 |
| TC-DLV-002 | Received = after − before + sales during drop | Exact | P0 | U | 5.4 |
| TC-DLV-003 | Delivery variance −0.5% without reason | FMS-T205 | P0 | D | 5.4 |
| TC-DLV-004 | Variance within −0.3% | Submits; no adjustment; Wetstock Delivery row written | P0 | D | 5.4 |
| TC-DLV-005 | *Record delivery shortage* | Draft Stock Entry for exactly the shortage to *Delivery Shortage Claims*; not submitted automatically | P0 | D | 5.4 |
| TC-DLV-006 | Shortage Stock Entry submitted before the shift closes | Shift receipts = GRN − shortage | P0 | A | 5.5 |
| TC-DLV-007 | Over-delivery (+0.5%) | **Open Q-22:** reason required for gains too? *Proposed: same tolerance both ways.* | P1 | D | 5.4 |
| TC-DLV-008 | Draft GRN in the window | FMS-T204 at close | P0 | D | 6.6 |
| TC-DLV-009 | GRN posted after the shift closed, dated inside its window | **Open Q-23:** blocked (nf D50 for counted items) or allowed with repost? *Proposed: blocked for tank warehouses; post at real time or via correction.* | P0 | D | 8.9 |
| TC-DLV-010 | Delivery starting before shift end and finishing after | Assigned to the shift containing the GRN posting time; dips explain both shifts | P0 | E | 5.4 |
| TC-DLV-011 | GRN posting time exactly at `shift_end` | **Open Q-24:** window inclusive or exclusive at each end? *Proposed: start inclusive, end exclusive.* | P0 | D | 5.4 |
| TC-DLV-012 | Two deliveries to the same tank in one shift | Both pulled; reconciliation exact | P0 | D | 5.4 |
| TC-DLV-013 | One GRN, two tanks (compartments) | One dip row per tank; both pulled | P0 | D | 5.4 |
| TC-DLV-014 | Diesel GRN line into a petrol tank warehouse | Refused (product does not match the tank). **Open Q-25:** code. | P0 | D | 5.4 |
| TC-DLV-015 | Dip after lower than dip before with no sales during drop | Refused or negative received flagged. **Open Q-26:** code. | P0 | D | 5.4 |
| TC-DLV-016 | Delivery larger than ullage (overfill) | After-dip above chart → FMS-T202; above capacity → TC-DIP-014 | P1 | D | 5.4 |
| TC-DLV-017 | GRN cancelled after a closed shift pulled it | Refused (FMS-C502 pattern): a correction is needed | P0 | D | 6.8 |
| TC-DLV-018 | Purchase Return of fuel from a tank | **Open Q-27:** pulled into the shift as negative receipts? *Proposed: yes, as a transfer-out line.* | P1 | D | |
| TC-DLV-019 | Landed Cost Voucher on a pulled GRN after the shift closed | Valuation reposts; INV-19 after repost | P0 | A | 5.4 |
| TC-DLV-020 | GRN to a tank warehouse at a station with dips not required | No T206; receipts pulled | P1 | D | 5.4 |
| TC-DLV-021 | GRN with zero rate (price unknown) | **Open Q-28:** allowed? COGS would be zero. *Proposed: refused for fuel items.* | P0 | A | 8.3 |

---

## 12. Own use, pump tests, transfers and meter changes

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-OWN-001 | Fuel Own Use submitted in the window | Pulled onto the nozzle row; not sold; stock reduced at cost to the purpose's account | P0 | A | 5.10 |
| TC-OWN-002 | Draft Fuel Own Use in the window | FMS-S113 | P0 | D | 6.6 |
| TC-OWN-003 | Own use without narration | Refused (mandatory) | P1 | D | 5.10 |
| TC-OWN-004 | Own use on a nozzle of another station | Refused | P0 | D | 5.10 |
| TC-OWN-005 | Own use larger than the nozzle's litres in the shift | TC-CAL-018 | P0 | D | 5.3 |
| TC-OWN-006 | Own use cancelled after the shift closed | Refused: correction | P0 | D | 6.8 |
| TC-OWN-007 | Own use posted outside any shift window (between shifts) | **Open Q-29:** which shift pulls it? *Proposed: the shift whose window contains it; between shifts (gap) it is refused.* | P0 | D | 5.10 |
| TC-OWN-010 | Test volume within limit | Not sold, not removed from the tank | P0 | U | 5.3 |
| TC-OWN-011 | Test volume above limit | FMS-S115 | P0 | D | 6.6 |
| TC-OWN-012 | Test volume with no limit set | Allowed; reported (MTR-05) | P2 | D | 5.3 |
| TC-OWN-020 | Tank Transfer T2 → T3 (same product) | Stock Entry; both tanks' expected adjusted; INV-08 | P0 | A | 5.5 |
| TC-OWN-021 | Transfer between different products | Refused | P0 | D | 5.5 |
| TC-OWN-022 | Transfer larger than the source's book stock | Refused (negative stock, P302) | P0 | D | 5.5 |
| TC-OWN-030 | Meter Change between shifts | Next shift opens from the new start value; INV-07 uses the change | P0 | D | 5.3 |
| TC-OWN-031 | Meter Change while a shift is open on the nozzle | **Open Q-30:** *Proposed: refused while a draft shift includes the nozzle, or it splits the row like a handover.* | P0 | D | 5.3 |
| TC-OWN-032 | Meter Change with old final reading below the last closing | Refused (litres would vanish). **Open Q-31:** code. | P0 | D | 5.3 |
| TC-OWN-033 | Meter Change cancelled after a shift used its start value | Refused | P0 | D | |

---

## 13. Prices and price segments

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PRC-001 | Fuel Price Change approved during an open shift (segments mode) | New segment in the open shift; readings required (FMS-S112) | P0 | D | 6.5a |
| TC-PRC-002 | Segment without readings | FMS-S112 | P0 | D | 6.6 |
| TC-PRC-003 | Time-based estimate setting on, segment without readings | Litres estimated, flagged as an exception | P1 | D | 6.5a |
| TC-PRC-004 | Between-shifts mode: change during an open shift | Open shift keeps one segment; next shift uses the new price | P0 | D | 6.5a |
| TC-PRC-005 | `effective_at` in the future | Refused (D24) | P0 | D | 6.5a |
| TC-PRC-006 | `effective_at` exactly equal to `shift_start` | New price for the whole shift; one segment | P0 | D | 6.5a |
| TC-PRC-007 | `effective_at` exactly equal to `shift_end` | **Open Q-32:** belongs to this shift (zero-length segment) or the next? *Proposed: next shift (end exclusive).* | P0 | D | 6.5a |
| TC-PRC-008 | Price change back-dated into a closed shift window | **Open Q-33:** *Proposed: refused; history of closed shifts never changes.* | P0 | D | 6.5a |
| TC-PRC-009 | Two price changes for the same product within minutes | Two segments; readings for each | P1 | D | 6.5a |
| TC-PRC-010 | Price change rejected | No segment; old price stays | P0 | D | 6.5a |
| TC-PRC-011 | Approved price change cancelled while the shift is open | **Open Q-34:** *Proposed: cancellation refused once a shift has a segment from it; post a new change instead.* | P0 | D | 6.5a |
| TC-PRC-012 | Credit Sales Invoice posted manually at 14:30 after a 14:00 change | Rate from the change in force at posting time (validate hook) | P0 | D | 6.5a |
| TC-PRC-013 | POS Invoice at 13:59 and 14:01 | Old and new rates respectively | P0 | D | 6.5a |
| TC-PRC-014 | Item Price written for reference with valid-from date | Written; not used for fuel rates at FMS stations | P1 | D | 6.5a |
| TC-PRC-015 | Price change submitted while the shift is *Closing* | **Open Q-35:** *Proposed: segment refused for a closing shift; applies from the next.* | P0 | C | 6.7 |
| TC-PRC-016 | Price 0 or negative | Refused | P0 | D | |
| TC-PRC-017 | Price change by the station manager without area manager approval | Not effective (workflow) | P0 | D | 14.3 |

---

## 14. Cashiers, cash, floats and drops

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CSH-001 | Shortage −500, no resolution | FMS-S105 | P0 | D | 6.6 |
| TC-CSH-002 | Shortage charged to cashier | Journal Entry to Staff Shortage Receivable with Employee party; INV-15 | P0 | A | 7.3 |
| TC-CSH-003 | Write-off below the small-difference limit | Allowed without approval | P0 | D | 7.3 |
| TC-CSH-004 | Write-off above the limit | Needs area manager approval | P0 | D | 7.3 |
| TC-CSH-005 | Split resolution: 300 charged, 200 written off | Both posted; Σ = difference exactly | P0 | A | 7.3 |
| TC-CSH-006 | Resolutions totalling more or less than the difference | FMS-S105 | P0 | D | 6.6 |
| TC-CSH-007 | Excess posted to Cash Over | Journal Entry; excess flagged in reports when repeated | P0 | A | 7.3 |
| TC-CSH-008 | Shortage resolved as *Charge* to an Employee who has left | **Open Q-36:** allowed? *Proposed: allowed with a warning; recovery tracked in CSH-06.* | P1 | D | 7.3 |
| TC-CSH-009 | Cashier disabled as Employee before the shift closes | **Open Q-37:** *Proposed: close allowed; new shifts refuse the cashier.* | P1 | D | |
| TC-CSH-010 | Same cashier on open shifts at two stations at the same time | **Open Q-38:** *Proposed: refused when windows overlap.* | P1 | D | 7.1 |
| TC-CSH-011 | Float zero | Allowed | P2 | D | 7.5 |
| TC-CSH-012 | Float *Returned to safe* (D27) | Internal transfer posted at close; INV-01 includes it | P0 | A | 7.5 |
| TC-CSH-013 | Float *Stays in till* | No transfer; till keeps the float | P0 | A | 7.5 |
| TC-CSH-014 | Drop with safe receipt number | Internal transfer till → safe; drops on accounted side | P0 | A | 6.5 |
| TC-CSH-015 | Drop larger than the cash the cashier could have | Allowed (it is a fact) but the difference shows an excess; flagged | P2 | D | 7.2 |
| TC-CSH-016 | Denomination breakdown that does not add up to the amount | Refused | P1 | D | 7.5 |
| TC-CSH-017 | Negative cash count | Refused | P0 | D | |
| TC-CSH-018 | Multi-currency: USD and SOS counted | Each to its own till account; converted at the company rate for the date | P0 | A | 7.5 |
| TC-CSH-019 | No exchange rate for the date | **Open Q-39:** *Proposed: close refused with a coded message naming the currency pair and date.* | P0 | D | 7.5 |
| TC-CSH-020 | Exchange rate changed after the shift closed | Closed shift unchanged | P0 | A | 7.5 |
| TC-CSH-021 | Cashier who sold nothing but holds a float | Balance = 0 if counted = float | P2 | D | 7.2 |
| TC-CSH-022 | Shortage approval given, then the cash count is changed | Approval resets to Pending (6.2) | P0 | D | 6.2 |

---

## 15. Mobile money, cards and payment imports

### 15.1 Feeds and matching

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PAY-001 | Callback for till 123456 inside the window | Payment Feed Entry; at close a collection row on the mapped cashier | P0 | D | 12.2 |
| TC-PAY-002 | Same callback delivered twice (provider retry) | One Integration Inbox row, one feed entry (external id unique); INV-12 | P0 | D | 12.1 |
| TC-PAY-003 | Same callback delivered 50 times concurrently | One feed entry; no deadlock; no 500 to the provider | P0 | C | 12.1 |
| TC-PAY-004 | Callback for an unknown till | Inbox Failed with FMS-I401; nothing assigned | P0 | D | 15.3 |
| TC-PAY-005 | Till mapped to the station but not to a cashier | Entry unassigned; FMS-S111 at close | P0 | D | 6.6 |
| TC-PAY-006 | Callback arrives after the shift closed for a payment inside its window | Stays on the unmatched list; not added to the closed shift. **Open Q-40:** how is it resolved (correction, next shift, accountant)? *Proposed: accountant assigns it through a Native document correction; never to the next shift.* | P0 | E | 12.2 |
| TC-PAY-007 | Callback arrives before the shift is created | Stored; matched when the shift with that window closes | P1 | D | 12.2 |
| TC-PAY-008 | Callbacks out of order (later transaction first) | Same matched set as in order (TC-PBT-007) | P0 | D | 12.1 |
| TC-PAY-009 | Reversal of a payment (provider reverses after customer dispute) | **Open Q-41:** how are reversals represented and posted? *Proposed: a negative feed entry linked to the original; if the original is in a closed shift, flagged for a correction; never silently netted.* | P0 | E | 12.2 |
| TC-PAY-010 | Amount in callback differs from the statement for the same reference | **Open Q-42:** which wins? *Proposed: statement is authoritative; difference flagged in PAY-01.* | P0 | E | 8.5 |
| TC-PAY-011 | Same reference on two different providers | Both accepted (unique per provider, S114) | P1 | D | 6.6 |
| TC-PAY-012 | Reference typed manually, then the feed arrives with the same reference | **Open Q-43:** match or duplicate? *Proposed: the feed entry links to the typed collection; no second row; S114 never fires for this pair.* | P0 | D | 6.6 |
| TC-PAY-013 | Collection without a reference | FMS-S114 | P0 | D | 6.6 |
| TC-PAY-014 | Feed entry with amount 0 or negative (non-reversal) | Rejected in the inbox as malformed | P0 | D | 12.1 |
| TC-PAY-015 | Feed entry in a currency other than the till's | Rejected or flagged; never posted at face value | P0 | D | 13 |
| TC-PAY-016 | Each mobile money transaction becomes its own Payment Entry | One Payment Entry per row, reference copied, clearing account | P0 | A | 6.7 |
| TC-PAY-017 | 500 transactions on one shift | Background close (above 200 rows); all 500 Payment Entries; INV-14 | P0 | P | 6.7 |

### 15.2 Statement and settlement imports

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PAY-030 | Import the same statement twice | Second import creates nothing; duplicates reported | P0 | D | 12.2 |
| TC-PAY-031 | Statement overlapping the previous one by one day | Only new rows created | P0 | D | 12.2 |
| TC-PAY-032 | File with a UTF-8 BOM, Windows line endings, Latin-1 accents in payer names | Parsed correctly | P1 | D | |
| TC-PAY-033 | Amounts with thousands separators `1,000.00` and `1.000,00` | Parsed per the provider's declared format; wrong format rejected, not mis-parsed | P0 | D | |
| TC-PAY-034 | Dates as Excel serials, text, and ISO | Parsed per format; ambiguous `03/04/2026` resolved by the provider's declared format | P0 | D | |
| TC-PAY-035 | Rows for another station's till | Assigned to that station's feed, not this shift | P0 | D | 12.2 |
| TC-PAY-036 | Missing column | Whole file rejected with the column named; no rows created | P1 | D | |
| TC-PAY-037 | Formula content in payer name (`=HYPERLINK(...)`) | Stored as text; exported safely (TC-SEC-040) | P0 | S | |
| TC-PAY-038 | 1 million rows | Rejected above the size limit, or processed in background without timeouts | P1 | P | |
| TC-PAY-039 | Card settlement with fees | Fees post as bank charges; settlement matches the batch's Payment Entries | P0 | A | 8.5 |
| TC-PAY-040 | Card settlement missing one transaction | That Payment Entry stays in clearing; PAY-04 shows it | P0 | A | 8.5 |
| TC-PAY-041 | Bank statement imported twice | ERPNext duplicate check; no second Bank Transaction | P0 | D | 8.5 |
| TC-PAY-042 | Clearing to bank transfer for the exact settled amount | Clearing returns to zero for those entries; INV-14 | P0 | A | 8.5 |

---

## 16. Credit customers and vehicles

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CRD-001 | Slip without customer | FMS-S107 | P0 | D | 6.6 |
| TC-CRD-002 | Vehicle of another customer | FMS-S107 | P0 | D | 6.6 |
| TC-CRD-003 | Vehicle not allowed the product | FMS-S107 | P0 | D | 6.6 |
| TC-CRD-004 | Customer over the credit limit, not approved | FMS-S107 | P0 | D | 6.6 |
| TC-CRD-005 | Over-limit approved by the area manager | Close proceeds; invoice posts | P0 | A | 6.6 |
| TC-CRD-006 | Over-limit approved in FMS but ERPNext's own credit-limit check blocks the Sales Invoice at posting | **Open Q-44:** how does an FMS-approved over-limit pass ERPNext's native check (Credit Controller role, bypass setting)? *Proposed: posting user holds the bypass only for approved slips; otherwise the close fails atomically with a coded message, never a raw ERPNext error.* | P0 | A | 6.6 |
| TC-CRD-007 | Vehicle over its monthly litre limit | FMS-S107 unless approved | P0 | D | 6.6 |
| TC-CRD-008 | Credit litres for AGO above metered AGO | FMS-S108 | P0 | D | 6.6 |
| TC-CRD-009 | Customer disabled or frozen in ERPNext | **Open Q-45:** caught as a gate before posting? *Proposed: yes, new code; the close never fails at posting for a known condition.* | P0 | D | |
| TC-CRD-010 | Duplicate slip number for the same customer | **Open Q-46:** blocked? *Proposed: refused within the same slip book.* | P1 | D | 11.2 |
| TC-CRD-011 | Slip number gap | Reported in CRD-01; does not block | P2 | D | 11.2 |
| TC-CRD-012 | Per-shift invoicing | One Sales Invoice per credit customer per shift | P0 | A | 6.7 |
| TC-CRD-013 | Monthly invoicing (D26) | Delivery Notes per shift; invoice at month end covers exactly the month's notes | P0 | A | 6.7 |
| TC-CRD-014 | Customer currency differs from company currency | **Open Q-47:** supported? *Proposed: credit customers must use the company currency in Phases 0 to 3.* | P1 | A | 13 |
| TC-CRD-015 | Debt receipt at the station by mobile money | Payment Entry against the customer with the reference; cashier expected and accounted both include it | P0 | A | 6.7 |
| TC-CRD-016 | Debt receipt for more than the customer owes | Unallocated advance on the customer | P1 | A | |
| TC-CRD-017 | Odometer lower than the vehicle's previous reading | Allowed (fact) and flagged (CRD-03) | P2 | D | rc CRD-03 |

---

## 17. Expenses

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-EXP-001 | Expense without type | FMS-S109 | P0 | D | 6.6 |
| TC-EXP-002 | Expense above the per-line limit | FMS-S109 | P0 | D | 6.6 |
| TC-EXP-003 | Expense receipt required by setting, not attached | Refused. **Open Q-48:** code. | P1 | D | 8.7 |
| TC-EXP-004 | Expense type without an account for the company | Refused at close with a coded message | P0 | D | 8.7 |
| TC-EXP-005 | ERPNext budget with action *Stop* exceeded by the expense | **Open Q-49:** gate before posting? *Proposed: checked at readiness; never a raw budget error at posting.* | P0 | A | |
| TC-EXP-006 | Many small expenses that together exceed a daily limit | **Open Q-50:** is there a daily limit? *Proposed: not in Phases 0 to 3; reported in EXP-02.* | P2 | D | |
| TC-EXP-007 | Expense posted to the right expense account with the Station dimension | Journal Entry lines correct | P0 | A | 6.7 |

---

## 18. Shift gates

Each gate has a passing case, a failing case and a "failing together" case. All failures are reported together (FMS-F12).

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-GTE-001 | All gates pass | Submit allowed | P0 | D | 6.6 |
| TC-GTE-002 | Every gate fails at once (one of each code) | One message listing all codes; nothing posted (INV-13) | P0 | D | 6.6 |
| TC-GTE-003 | Gates run in `before_submit` even when submit comes from the API | Same result as the UI | P0 | S | 6.6 |
| TC-GTE-004 | Gates run on the background close path | Same result as the foreground path | P0 | D | 6.7 |
| TC-GTE-005 | A gate condition becomes true between readiness check and submit (a draft GRN appears) | Submit refused (gates rerun at submit, not trusted from the client) | P0 | C | ux 12 |
| TC-GTE-006 | Readiness check (ux UX-10) lists exactly the same issues as `before_submit` | Equal sets for 100 generated failing shifts | P1 | D | ux 12.2 |
| TC-GTE-007 | FMS-S110 overlap with a *draft* shift | Not a failure (only submitted shifts count) | P1 | D | 6.6 |
| TC-GTE-008 | FMS-S111 with feeds not yet enabled for the station | Gate passes (applies "once feeds exist") | P1 | D | 6.6 |

Individual gates are covered in their areas: S101 (9), S102 (8), S103 (10), S104 (9), S105 (14), S106 (10), S107 (16), S108 (16), S109 (17), S110 (8), S111 (15), S112 (13), S113 (12), S114 (15), S115 (12), T203 and T204 (10, 11), W103 (9).

---

## 19. Posting and accounting integrity

### 19.1 Documents created at close

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PST-001 | Worked example fms.md 8.2 | Exactly the documents and amounts of 8.2; INV-01 to INV-10 | P0 | A | 8.2 |
| TC-PST-002 | Every document type of 6.7 present when its trigger exists | Credit invoices, walk-in invoice, Payment Entries (mobile, card, cash, vouchers, drops, float, debt), Journal Entry, Stock Reconciliation, ledger rows | P0 | A | 6.7 |
| TC-PST-003 | No document when its trigger is absent | No empty invoices, no zero Journal Entries | P1 | A | 6.7 |
| TC-PST-004 | Shift with zero sales and zero collections | **Open Q-51:** close allowed with no documents except ledgers and tank reconciliation? *Proposed: yes.* | P1 | A | |
| TC-PST-005 | Posting times: invoices at end − 1 min, Stock Reconciliation at end, in system time converted from station time | Exact times (D35) | P0 | A | 6.7 |
| TC-PST-006 | COGS uses moving average before the tank adjustment | Valuation equals manual calculation | P0 | A | 6.7 |
| TC-PST-007 | Every generated document carries `fms_forecourt_shift` and Station dimension | INV-10 | P0 | A | 6.7 |
| TC-PST-008 | Cost center and income account per line | From item defaults, item group, station (nf 10.5 pattern) | P1 | A | 8.8 |
| TC-PST-009 | Taxes: fuel prices tax-inclusive (`included_in_print_rate`) | Net income and tax split exactly; totals equal pump amounts | P0 | A | 13 |
| TC-PST-010 | Per-litre levy as Item Tax *On Item Quantity* | Levy = litres × rate exactly | P0 | A | 13 |
| TC-PST-011 | Walk-in customer missing for the station | Refused at close with a coded message | P0 | D | |

### 19.2 Failure during posting

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PST-020 | Exception injected after each of the 11 posting steps in turn | Full rollback each time; INV-13; status back to Reconciled; coded message | P0 | R | 6.7 |
| TC-PST-021 | Negative stock in a tank warehouse at posting | FMS-P302; rollback | P0 | A | 15.3 |
| TC-PST-022 | Mode of Payment without account | FMS-P301; rollback | P0 | A | 15.3 |
| TC-PST-023 | Accounting period closed for the shift date | Refused before posting with a coded message | P0 | A | 8.9 |
| TC-PST-024 | Fiscal year missing for the date | Refused before posting with a coded message | P0 | A | |
| TC-PST-025 | Accounts frozen up to a date after the shift date | Refused before posting with a coded message | P0 | A | |
| TC-PST-026 | Warehouse, item, customer or cost center disabled between creation and close | Refused before posting with a coded message naming the record | P0 | A | |
| TC-PST-027 | A native ERPNext validation fails (any reason) | Rollback; user sees a coded FMS message with the ERPNext reason in plain words; full error in Error Log | P0 | R | ux 20.5 |
| TC-PST-028 | Retry after a failed close | Same documents as a first-time close; no leftovers, no duplicates | P0 | R | 6.7 |
| TC-PST-029 | Fiscal adapter (on Sales Invoice submit) times out during close | **Open Q-52:** does a fiscal failure roll back the close? *Proposed: no; the invoice posts and fiscalisation retries through the Integration Inbox; CMP-02 shows it pending.* | P0 | R | 12.3 |

### 19.3 Background close

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PST-040 | 201 payment rows | Background job; status Closing; realtime refresh on done | P0 | D | 6.7 |
| TC-PST-041 | Job fails | Status back to Reconciled; error shown; INV-13 | P0 | R | 6.7 |
| TC-PST-042 | Job enqueued twice | One run (deduplicated by shift) | P0 | C | TASKS F16 |
| TC-PST-043 | Worker killed mid-job | Transaction rolled back by the database; shift stuck in Closing is detected and returned to Reconciled. **Open Q-53:** detection rule? *Proposed: a scheduler check resets Closing older than the job timeout after confirming no documents exist.* | P0 | R | 6.7 |
| TC-PST-044 | Redis or the queue unavailable at close | **Open Q-54:** *Proposed: close refused with a coded message; status unchanged.* | P1 | R | |

---

## 20. Approvals and workflow

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-APR-001 | Shift needing approval moves to Pending Approval on save | `approval_state` Pending; submit refused until approved | P0 | D | 6.2 |
| TC-APR-002 | Approver is the preparer | Refused (workflow) | P0 | S | 14.3 |
| TC-APR-003 | Area manager of another station group approves | Refused (no permission) | P0 | S | 14.2 |
| TC-APR-004 | Approval via the email action link after the shift changed | Refused: the change reset approval | P0 | D | 6.2 |
| TC-APR-005 | Approved amounts changed after approval | Approval back to Pending | P0 | D | 6.2 |
| TC-APR-006 | A non-approval field changed after approval (a typo in a note) | **Open Q-55:** does any change reset approval? *Proposed: only approved amounts, reasons and readings that change them.* | P1 | D | 6.2 |
| TC-APR-007 | Rejected with comment | Back to Counting; comment visible | P1 | D | 6.2 |
| TC-APR-008 | Approver loses the role between request and action | Action refused | P1 | S | |
| TC-APR-009 | Approval via REST `apply_workflow` by the station manager | Refused | P0 | S | |
| TC-APR-010 | Fuel Price Change workflow | Draft → Pending → Approved; only approved changes create segments | P0 | D | cat 8.5 |
| TC-APR-011 | Shift Correction needs director approval | FMS-C501 when submitted without | P0 | D | 15.3 |
| TC-APR-012 | Notifications sent to approvers | Workflow Action and email to the right users only | P2 | D | TASKS I04 |

---

## 21. Corrections

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-COR-001 | Native document correction: credit slip to wrong customer | Invoice cancelled and amended; nothing else changes; INV-17 | P0 | A | 6.8 |
| TC-COR-002 | Meter reading typed 105,230 instead of 105,320, next shift draft | Superseding Nozzle and Sales Ledger rows for this shift; next shift opening updated; balances recalculated | P0 | A | 6.8 |
| TC-COR-003 | Same, next shift already closed | Both shifts corrected; walk-in Credit Note or extra invoice; both cashiers recalculated; new differences need resolution | P0 | A | 6.8 |
| TC-COR-004 | Same, the next two shifts closed | **Open Q-56:** the spec moves litres between this and the next shift only. *Proposed: only the next shift is affected because its opening changes; later shifts are unaffected.* | P0 | A | 6.8 |
| TC-COR-005 | Meter correction that makes the next shift's sales negative | Refused with a coded message | P0 | D | 6.8 |
| TC-COR-006 | Dip correction | Superseding Wetstock row; back-dated Stock Reconciliation; ERPNext reposts; next shift's row superseded; INV-19 after repost | P0 | A | 6.8 |
| TC-COR-007 | Dip correction while a Repost Item Valuation for the station is still running | **Open Q-57:** *Proposed: correction waits or is refused until reposting finishes.* | P0 | C | 6.8 |
| TC-COR-008 | Cashier count correction | Reversing Journal Entry and a new one; CSH-01 updated | P0 | A | 6.8 |
| TC-COR-009 | Resolution correction: shortage charged to the wrong cashier | Reversal and new charge; both statements right | P0 | A | 6.8 |
| TC-COR-010 | Reclassification of a variance reason | FMS rows superseded; no GL change | P1 | A | 6.8 |
| TC-COR-011 | Reclassification of an expense type that changes the account | Superseding rows plus native fix | P0 | A | 6.8 |
| TC-COR-012 | Correction in an open accounting period | Posted at the original shift date | P0 | A | 6.8 |
| TC-COR-013 | Correction when the period is closed | Posted at the correction date with a reference to the shift | P0 | A | 6.8 |
| TC-COR-014 | Correction rejected | Nothing changes | P0 | D | 6.8 |
| TC-COR-015 | Two corrections of the same shift at the same time | Second refused or serialised; INV-17 | P0 | C | |
| TC-COR-016 | Correction of a correction | Supersedes the corrected rows (chain), not the originals twice | P0 | A | 6.8 |
| TC-COR-017 | Correction creates a new cashier difference | Resolution required inside the correction before Apply | P0 | D | 6.8 |
| TC-COR-018 | Correction fails during Apply (fault injected) | Full rollback; correction stays Approved, not Applied | P0 | R | 6.8 |
| TC-COR-019 | Shift banner lists its corrections | Shown | P2 | M | 6.8 |
| TC-COR-020 | Audit view shows original and corrected rows; default reports show corrected only | As stated | P0 | D | 6.8 |

---

## 22. Cancellation and immutability

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CAN-001 | Cancel a Payment Entry generated by a shift | FMS-C502 | P0 | D | 15.3 |
| TC-CAN-002 | Cancel the shift's Sales Invoice, Journal Entry or Stock Reconciliation directly | FMS-C502 | P0 | D | 15.3 |
| TC-CAN-003 | Same through the REST API as System Manager | FMS-C502 (hook, not UI) | P0 | S | 6.8 |
| TC-CAN-004 | Cancel a shift without System Manager role | Refused (no Cancel permission for FMS roles) | P0 | S | 6.8 |
| TC-CAN-005 | Cancel an older closed shift (not the latest) | FMS-C503 | P0 | D | 6.8 |
| TC-CAN-006 | Cancel the latest shift without director approval | FMS-C503 | P0 | D | 6.8 |
| TC-CAN-007 | Cancel the latest shift with System Manager and director approval | All generated documents cancelled; ledgers flagged `is_cancelled`; next shift's openings revert | P0 | A | 6.8 |
| TC-CAN-008 | Cancel a shift in a closed period | Refused | P0 | D | 6.8 |
| TC-CAN-009 | Edit a ledger row (UI, API, data import) | Refused (no write permission; `in_create`) | P0 | S | cat 10 |
| TC-CAN-010 | Delete a ledger row as Administrator | Refused | P0 | S | cat 10 |
| TC-CAN-011 | Edit a submitted shift via `frappe.db.set_value` from a server script | Not possible from AFMS code paths; a lint rule bans `db.set_value` on FMS submitted DocTypes | P1 | S | 9.2 |
| TC-CAN-012 | Amend a cancelled shift | **Open Q-58:** allowed? *Proposed: refused; create a new shift.* | P1 | D | |
| TC-CAN-013 | Data Import tool used to insert Forecourt Shift rows | Refused for FMS transactional DocTypes | P0 | S | |
| TC-CAN-014 | Version history exists for every change to shifts and masters | Version rows written | P1 | D | 9.2 |

---

## 23. Period close and back-dating

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PER-001 | Shift dated within `allow_backdated_shift_days` | Allowed | P1 | D | 8.9 |
| TC-PER-002 | Shift dated beyond the limit | Needs approval | P1 | D | 8.9 |
| TC-PER-003 | Any FMS document in a closed Accounting Period | Cannot be posted, cancelled or back-dated | P0 | A | 8.9 |
| TC-PER-004 | Period closed while a shift of that period is still open | **Open Q-59:** *Proposed: period close refused while drafts or Pending Approval shifts exist in it (checked by a hook on Accounting Period).* | P0 | A | 8.9 |
| TC-PER-005 | Shift spanning two periods (Night shift 31 Oct 18:00 – 1 Nov 06:00) | Posts in October (posting date = shift date, D20) | P0 | A | 8.9 |
| TC-PER-006 | Year-end closing (Period Closing Voucher) after FMS postings | P&L closed; FMS balances unaffected | P0 | A | |
| TC-PER-007 | Back-dated stock document of any type into a closed shift window | TC-DLV-009, nf D50 | P0 | D | nf 10.8 |

---

## 24. Ledgers and reports

The full report test list is in the reporting catalogue, section 29. The cases below are those that protect money and stock.

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-LED-001 | One ledger row set per close: Nozzle (per segment), Sales (per line × payment type), Cashier (per cashier), Wetstock (per tank) | Counts and values exact | P0 | A | 6.7 |
| TC-LED-002 | Sales Ledger `basis` Exact for credit and POS, Attributed for the rest | As specified | P0 | A | 10.4 |
| TC-LED-003 | Golden month: every report total equals its source and the GL | rc section 29 checks all pass | P0 | E | rc 29 |
| TC-LED-004 | Report after a correction | Corrected figures; history view shows both | P0 | A | 6.8 |
| TC-LED-005 | Report after a whole-shift cancellation | Cancelled rows excluded | P0 | A | 6.8 |
| TC-LED-006 | Report run by a station manager | Only own stations (INV-20) | P0 | S | rc 27.3 |
| TC-LED-007 | Report with SQL or HTML in filter values | Parameterised; no injection; escaped output | P0 | S | rc 27 |
| TC-LED-008 | Report across companies with different currencies | Totals per currency (rc 4.7) | P0 | A | rc 4.7 |
| TC-LED-009 | Total row of a T-WTD report | Rates recomputed from totals | P1 | U | rc 4.2 |
| TC-LED-010 | Ledger write fails after documents posted (fault) | Whole close rolls back (ledgers are in the same transaction) | P0 | R | 6.7 |

---

## 25. Integrations

### 25.1 Integration Inbox

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-INT-001 | Message stored before processing | Inbox row exists even if processing crashes | P0 | R | 12.1 |
| TC-INT-002 | Processing fails | Status Failed, error stored, attempts incremented, *Retry* works | P0 | D | 12.1 |
| TC-INT-003 | Retry with exponential backoff | Attempts at increasing intervals up to the limit; then stays Failed | P1 | D | 12.1 |
| TC-INT-004 | Poison message that always fails | Stops after the limit; does not block other messages | P0 | R | 12.1 |
| TC-INT-005 | Replay all messages of a day (after a restore) | Same domain records, no duplicates (idempotent by external id) | P0 | R | 12.1 |
| TC-INT-006 | Message with an unknown type | Ignored with status Ignored and a reason | P2 | D | 12.1 |
| TC-INT-007 | Payload larger than the limit | Rejected with 413; nothing stored | P1 | S | |
| TC-INT-008 | Malformed JSON | Rejected (4xx) or stored as Failed. **Open Q-60:** which? *Proposed: store with status Failed when the signature is valid, reject otherwise.* | P1 | D | 12.1 |

### 25.2 Webhook security

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-INT-020 | Callback without a valid signature or credentials | 401/403; nothing stored | P0 | S | 14.3 |
| TC-INT-021 | Valid signature replayed hours later | **Open Q-61:** timestamp window? *Proposed: rejected outside a configurable window; idempotency still protects.* | P0 | S | |
| TC-INT-022 | Callback from an IP outside the provider's published range (when the provider publishes one) | Rejected when the allow-list is configured | P1 | S | |
| TC-INT-023 | Callback flood (1,000 per second) | Rate limit; legitimate traffic still processed; no data loss for accepted messages | P1 | P | |

### 25.3 Fiscal adapter

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-INT-040 | Invoice accepted | Fiscal number, signature and QR stored on the invoice | P0 | D | 12.3 |
| TC-INT-041 | Invoice rejected by the authority | Status Rejected with the reason; CMP-02 lists it; accountant notified | P0 | D | 12.3 |
| TC-INT-042 | Authority down for 6 hours | Queued; retried; all accepted after recovery, in order | P0 | R | 12.3 |
| TC-INT-043 | Fiscalised invoice cancelled in a correction | `cancel(invoice)` sent; credit note fiscalised | P0 | D | 12.3 |
| TC-INT-044 | Same invoice submitted twice to the authority (retry after timeout that actually succeeded) | Authority duplicate response handled as success; one fiscal number | P0 | R | 12.3 |

### 25.4 Bank and provider files

Covered in section 15.2.

### 25.5 Sandbox acceptance

Before go-live, each real provider and fiscal sandbox is run through: normal payment, duplicate, reversal, late callback, wrong till; fiscal accept, reject, cancel. Results recorded in `docs/uat/`.

---

## 26. Concurrency and race conditions

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-CON-001 | Two users press *Close* on the same shift at the same moment | One close; the other gets a coded message (ux FMS-S120); INV-12, INV-13 | P0 | C | ux 12.5 |
| TC-CON-002 | Double click on *Close* | One close | P0 | C | ux 12.5 |
| TC-CON-003 | User A edits a draft shift while user B saves it | Second save refused (modified timestamp) | P0 | C | |
| TC-CON-004 | GRN submitted into the window while the shift is Closing | **Open Q-62:** *Proposed: GRN refused while the shift whose window contains it is Closing; or the close detects it and fails.* Either way never a close that misses a receipt. | P0 | C | 5.4 |
| TC-CON-005 | Own use submitted into the window while Closing | Same rule as TC-CON-004 | P0 | C | 5.10 |
| TC-CON-006 | Feed entry arrives for the window while Closing | Not included; stays unmatched; handled as TC-PAY-006 | P0 | C | 12.2 |
| TC-CON-007 | Two stations close at the same second, same items | Both succeed; no deadlock or, on deadlock, automatic retry succeeds; INV for both | P0 | C | |
| TC-CON-008 | 20 stations close concurrently | All succeed within the time target; no lost updates on `Nozzle.last_*` | P0 | C | |
| TC-CON-009 | Next shift created while the previous is Closing | Refused (TC-SHC-009) | P0 | C | |
| TC-CON-010 | Correction applied while the next shift is being closed | Serialised; both end consistent (INV-17) or one refused with a coded message | P0 | C | 6.8 |
| TC-CON-011 | Two imports of the same statement in parallel | One set of rows (unique constraint, not just a check) | P0 | C | 12.2 |
| TC-CON-012 | Approval and an edit at the same moment | Either the edit resets the approval, or the approval applies to the unedited version; never approval of unseen data | P0 | C | 6.2 |
| TC-CON-013 | Price change approved at the same second the shift starts closing | Rule of TC-PRC-015 holds | P0 | C | |
| TC-CON-014 | Repost Item Valuation running while a shift closes at the same station | Close succeeds; INV-19 after both finish | P0 | C | |

Uniqueness that protects money must be enforced by **database unique indexes**, not only by Python checks, because checks race. Candidates: Integration Inbox (`provider`, `external_id`), collection references per provider for submitted shifts (through a helper table if needed), Mode B `client_txn_id`, FCC transaction on invoice lines.

---

## 27. Failure, recovery and chaos

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-REC-001 | Database connection lost in the middle of close | Rollback; status Reconciled after reconnect; INV-13 | P0 | R | 6.7 |
| TC-REC-002 | Web server restarted during a foreground close | Same as TC-REC-001 | P0 | R | |
| TC-REC-003 | Worker killed during background close | TC-PST-043 | P0 | R | |
| TC-REC-004 | Disk full during close | Rollback; coded message; no corrupt rows | P0 | R | |
| TC-REC-005 | Redis lost: no realtime updates | Close still finishes; the page shows the result on refresh | P1 | R | |
| TC-REC-006 | Scheduler stopped for a day | Inbox retries and reports resume; nothing lost; FMS Health reports the gap | P1 | R | |
| TC-REC-007 | Restore last night's backup, replay the inbox | Feeds rebuilt exactly; shifts closed after the backup must be re-entered (documented runbook) | P0 | R | 12.1 |
| TC-REC-008 | Point-in-time restore of the database to before a close | Close simply not present; continuity intact | P1 | R | |
| TC-REC-009 | Clock of the server jumps backwards an hour | No shift window or posting time inconsistency; NTP alert | P1 | R | |
| TC-REC-010 | Browser crashes during entry | Draft saved up to the last save; nothing posted | P2 | M | |
| TC-REC-011 | Network drops during *Close* on a tablet | Server finishes or rolls back alone; reopening the form shows the true status | P0 | R | |
| TC-REC-012 | Partial upgrade (migration fails halfway) | Site in maintenance; rollback to backup works (runbook) | P0 | R | 33 |

---

## 28. Time, dates and time zones

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-TIM-001 | Station time zone differs from the system time zone (system UTC, station Africa/Nairobi) | Windows in station time; posting times converted correctly | P0 | D | 6.7 |
| TC-TIM-002 | Night shift across midnight | Posting date = shift date (D20) | P0 | D | 6.3 |
| TC-TIM-003 | Night shift across month end and year end | Same; period and fiscal year of the start date | P0 | A | 8.9 |
| TC-TIM-004 | Night shift across the fiscal year end | Posts in the old fiscal year | P0 | A | |
| TC-TIM-005 | Leap day 2028-02-29 | Shifts, windows and reports correct; period presets correct | P1 | D | |
| TC-TIM-006 | Daylight saving: spring forward inside a night shift (Europe/Berlin station) | Window is 11 real hours; litres unaffected; times correct | P1 | D | 13 |
| TC-TIM-007 | Daylight saving: fall back (a repeated hour) | No duplicate or skipped posting times; a GRN in the repeated hour is assigned correctly | P1 | D | 13 |
| TC-TIM-008 | Event exactly at `shift_start` and exactly at `shift_end` | Boundary rule of TC-DLV-011 for all window lookups (GRN, own use, feeds, price) | P0 | D | |
| TC-TIM-009 | Events with seconds and microseconds at the boundary (17:59:59.999) | Same rule; no event lost between shifts | P0 | D | |
| TC-TIM-010 | Gap between shifts (Day ends 18:00, Night starts 18:30) | Events in the gap are refused or assigned per TC-OWN-007; never lost silently | P0 | D | |
| TC-TIM-011 | Feed timestamps in UTC from the provider | Converted to station time before window matching | P0 | D | 12.2 |
| TC-TIM-012 | Feed with a timestamp in the future (provider clock wrong) | Stored; flagged; matched by window when it falls in one | P1 | D | |
| TC-TIM-013 | Report period presets near midnight in the station time zone vs server | Presets use the station time zone (rc 3.3) | P1 | D | rc 3.3 |

---

## 29. Numbers, precision and rounding

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-NUM-001 | Litres × price rounding per line versus per total | One documented rule, the same in shift, invoice and reports; Σ of lines = invoice total exactly | P0 | U | |
| TC-NUM-002 | 500 payments of 33.33 | Sum exactly 16,665.00 (decimal arithmetic, no float drift) | P0 | U | |
| TC-NUM-003 | All money arithmetic in `calc/` uses `Decimal` or Frappe's `flt` with explicit precision consistently | Code review plus property test TC-PBT-003 | P0 | U | |
| TC-NUM-004 | Currency with zero decimals (UGX) | Amounts whole; litres × price rounded to whole currency by the documented rule | P0 | A | 13 |
| TC-NUM-005 | Currency with three decimals | Amounts at three decimals throughout | P1 | A | 13 |
| TC-NUM-006 | Very large values: meter 9,999,999.99; delivery 60,000 L; shift sales 50 million | No overflow, field precision sufficient | P0 | D | |
| TC-NUM-007 | Very small values: 0.01 L sold, 0.01 currency difference | Handled; a 0.01 difference still needs resolution (nothing silent, P6) | P0 | D | 7.3 |
| TC-NUM-008 | Prices with three decimals (183.475) | Stored and applied at that precision | P1 | D | |
| TC-NUM-009 | Exchange rate with 9 decimals | Conversion consistent; base totals equal Σ of converted lines (INV-18) | P0 | A | |
| TC-NUM-010 | Negative values typed in any quantity field | Refused | P0 | D | |
| TC-NUM-011 | Scientific notation input (`1e6`) | Refused or parsed exactly; never a silent wrong number | P1 | D | |
| TC-NUM-012 | Gallons as stock UOM (13) | Conversion factors exact; tank reconciliation in the stock UOM | P1 | A | 13 |

---

## 30. Security

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-SEC-001 | Station manager opens another station's shift by URL | PermissionError | P0 | S | 14.2 |
| TC-SEC-002 | Same through `/api/resource` and every whitelisted FMS method (IDOR) | PermissionError | P0 | S | |
| TC-SEC-003 | Area manager limited to a station group | Only stations in that branch of the tree | P0 | S | 14.2 |
| TC-SEC-004 | Investor attempts any write through the API | Refused | P0 | S | 14.1 |
| TC-SEC-005 | Cashier reads another cashier's Cashier Ledger or statement | Refused | P0 | S | 14.1 |
| TC-SEC-006 | Guest calls a whitelisted FMS method | Refused except signed webhook endpoints | P0 | S | |
| TC-SEC-007 | Station manager approves own variance by API | Refused (TC-APR-009) | P0 | S | |
| TC-SEC-008 | Role escalation: station manager edits own User roles or User Permissions | Refused | P0 | S | |
| TC-SEC-009 | Two-factor authentication enforced for managers and above | Login without the second factor refused | P1 | S | 14.3 |
| TC-SEC-010 | Revoked handheld or bridge API key | All calls refused | P0 | S | 14.3 |
| TC-SEC-020 | SQL injection in every report filter and search | No effect; parameterised queries | P0 | S | |
| TC-SEC-021 | Stored XSS in variance reason notes, slip numbers, payer names, rendered in HTML summaries and print formats | Escaped | P0 | S | ux 6.6 |
| TC-SEC-030 | Uploads: statement files with a wrong extension, executable content, zip bombs, very large files | Type and size checks; rejected | P1 | S | |
| TC-SEC-031 | Attachments (receipts, deposit slips, meter photos) not readable by users outside the station | Private files with permission checks | P1 | S | |
| TC-SEC-040 | Export to Excel with values starting `=`, `+`, `-`, `@` from external data | Neutralised in exports (CSV injection) | P1 | S | |
| TC-SEC-050 | Personal data (payer phone numbers) visible only to permitted roles | Masked otherwise (rc Q-09) | P1 | S | rc PAY-03 |
| TC-SEC-060 | Dependency and static security scans (FMS-L02) | No high findings | P1 | S | TASKS L02 |
| TC-SEC-061 | Secrets (provider keys, HMAC secrets) stored as Password fields, never in logs or Error Log payloads | Verified | P0 | S | |
| TC-SEC-062 | Error Log content does not leak to non-System Managers | Refused | P1 | S | ux 20.5 |

---

## 31. Fraud scenarios

Each scenario of fms.md 9.1 is simulated end to end. The system must **detect or block** it; the expected result names the control.

| ID | Fraud simulated | Expected detection | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-FRD-001 | Closing reading recorded lower than actual | Next shift's locked opening exposes it (impossible jump or negative next-shift variance); tank variance | P0 | E | 9.1 |
| TC-FRD-002 | Inflated pump tests to hide sales | FMS-S115 above limit; MTR-05 test share; tank variance (tests return to tank) | P0 | E | 9.1 |
| TC-FRD-003 | Fake credit slip for a vehicle of another customer | FMS-S107 | P0 | E | 9.1 |
| TC-FRD-004 | Fake credit slip for a real vehicle, real customer | Customer statement dispute; monthly litre limit; CRD-03 consumption anomaly | P1 | E | 9.1 |
| TC-FRD-005 | Mobile money diverted to a personal number | Cashier's mobile share low vs station (SAL-05, CSH-02, CTL-06) | P1 | E | 7.4 |
| TC-FRD-006 | Typing a fake mobile money reference to cover cash taken | With feeds: no matching feed entry → reported; reference reused → FMS-S114 | P0 | E | 6.6 |
| TC-FRD-007 | Fake expenses | Limit (S109), receipt, EXP-02 trend | P1 | E | 9.1 |
| TC-FRD-008 | Dip manipulated to hide a loss | Cumulative variance, spot dips by area manager (WET-06), next shift exposes it | P1 | E | 9.1 |
| TC-FRD-009 | Short delivery by the driver | Delivery dips, T205, DLV-02 by driver | P0 | E | 5.4 |
| TC-FRD-010 | Siphoning at night | Night shift variance pattern (WET-04) | P1 | E | 9.1 |
| TC-FRD-011 | Overcharging customers (price above system) | E-cash vs E-vol drift; price cross-check (PRC-02) | P1 | E | 9.1 |
| TC-FRD-012 | Manager and cashier collude: cash balances, tank loses | Tank variance independent of cash; WET-04, CTL-06 | P1 | E | 9.1 |
| TC-FRD-013 | Back-dated correction to hide a loss | Director approval; CTL-03, CTL-04; immutability | P0 | E | 9.1 |
| TC-FRD-014 | Shared login: manager approves as the area manager on the same device | CTL-07 signals; 2FA | P1 | E | rc CTL-07 |
| TC-FRD-015 | Repeated small excesses to hide earlier under-recording | Repeated excess flag (7.3) | P2 | E | 7.3 |
| TC-FRD-016 | Own use recorded for a vehicle that does not exist | Purpose and vehicle on the entry; EXP-03 review | P2 | E | 5.10 |

---

## 32. Multi-company, multi-currency, multi-jurisdiction

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-MCY-001 | Two companies, same item codes | Postings to each company's own accounts and warehouses | P0 | A | 13 |
| TC-MCY-002 | Station of company A uses an account of company B anywhere | FMS-M602 | P0 | D | 15.3 |
| TC-MCY-003 | User with access to company A sees nothing of B | INV-20 | P0 | S | 14.2 |
| TC-MCY-004 | Company in USD with SOS cash | TC-CSH-018 | P0 | A | 7.5 |
| TC-MCY-005 | Group report across KES and USD companies | Per-currency totals or presentation currency (rc 4.7) | P0 | A | rc 4.7 |
| TC-MCY-006 | Translations: a non-English UI | All FMS strings translated or in English, none broken; error codes unchanged | P2 | M | 13 |
| TC-MCY-007 | Right-to-left language | Forms and reports render | P3 | M | 13 |
| TC-MCY-008 | Country with per-transaction receipting (Per transaction mode) | Walk-in invoice posts only unreceipted volume (12.3) | P0 | A | 12.3 |

---

## 33. Upgrades, migration and go-live

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-MIG-001 | `bench migrate` on a site with data, twice | Second run changes nothing (patches idempotent) | P0 | D | TASKS L04 |
| TC-MIG-002 | Upgrade from the previous release with the golden month loaded | All invariants still hold; reports unchanged | P0 | E | |
| TC-MIG-003 | Fixture update (workspaces, roles) on a site where the customer changed a workspace | **Open Q-63:** overwrite or keep? *Proposed: standard workspaces overwritten; customer copies untouched.* | P2 | D | |
| TC-MIG-004 | Frappe/ERPNext minor upgrade within v16 | Full CI suite green before production upgrade | P0 | E | |
| TC-MIG-005 | Opening balances at go-live: tank stock, nozzle last readings, customer balances, cashier receivables | Loaded once, verified against the paper books; first shift continuity correct | P0 | E | TASKS N01 |
| TC-MIG-006 | Go-live in the middle of a month | Reports split correctly; no double counting of pre-go-live sales | P0 | E | |
| TC-MIG-007 | Parallel run (FMS-N02): daily comparison of FMS with the current books | Differences explained daily; acceptance thresholds met. **Open Q-64:** thresholds for litres, cash and stock? | P0 | E | TASKS N02 |
| TC-MIG-008 | Removing the app from a copy of the site | Documented; not required to succeed (data stays) | P3 | M | |

---

## 34. Performance and volume

| ID | Case | Target | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-PRF-001 | Typical shift close (8 nozzles, 3 tanks, 2 cashiers, 76 payments) | Server close under 5 seconds | P1 | P | |
| TC-PRF-002 | Large shift (40 nozzles, 6 cashiers, 500 payments) | Background close under 2 minutes | P1 | P | 6.7 |
| TC-PRF-003 | Shift form load with 500 collection rows | Under 3 seconds on a 10-inch tablet on 4G | P1 | P | ux 22 |
| TC-PRF-004 | Volume set: 400 stations × 365 days × 2 shifts | Reports within rc 28 targets | P1 | P | rc 28 |
| TC-PRF-005 | Inbox throughput | 100 callbacks per second sustained without loss | P1 | P | |
| TC-PRF-006 | Dip correction reposting a year of valuation for one tank | Completes; INV-19; time recorded | P1 | P | 6.8 |
| TC-PRF-007 | Human close time (FMS-K02) | Under 10 minutes for the typical shift | P1 | M | TASKS K02 |

---

## 35. User interface and messages

| ID | Case | Expected | Pri | Lyr | Ref |
|---|---|---|---|---|---|
| TC-UIX-001 | Every FMS error appears with its code and the three-part message | Checked for every code in section 38 | P2 | D | ux 20.2 |
| TC-UIX-002 | A forced unexpected exception during close, seen by a station manager | Coded message with an Error Log reference; no traceback | P0 | S | ux 20.5 |
| TC-UIX-003 | Read-only fields cannot be changed by the client (devtools edit, then save) | Server ignores or refuses the change | P0 | S | |
| TC-UIX-004 | Tablet check (FMS-K03) | All tabs usable, no horizontal page scroll | P1 | M | TASKS K03 |
| TC-UIX-005 | Keyboard: *Enter* moves down in reading grids | Works | P2 | M | 6.4 |
| TC-UIX-006 | Readiness panel (if UX-10 accepted) matches gates | TC-GTE-006 | P1 | D | ux 12 |
| TC-UIX-007 | Status indicators use text as well as colour | Checked on every list and form | P2 | M | ux 16 |

---

## 36. Non-fuel and Mode B (proposed)

These run only after fms-nonfuel.md decisions are accepted. Each line is a group of cases to be expanded when the build tasks start.

| ID | Group | Key cases | Pri |
|---|---|---|---|
| TC-NFS-001 | Count formula (nf 7.2) | Every term A to X; sign rules; X < 0 blocked (D705); D < 0 blocked (D708) | P0 |
| TC-NFS-002 | Posting check (nf 10.7) | Stock after posting = count, else D709 and rollback | P0 |
| TC-NFS-003 | POS cash deduction (nf 7.9) | No false excess for POS cash | P0 |
| TC-NFS-004 | Handover counts and segments | Segments sum to the single-segment result | P0 |
| TC-NFS-005 | Batch and serial counts | Bundles match the batches and serials that dropped | P0 |
| TC-NFS-006 | Services | Ticket unique (D711), consumables K, rate bounds (D712), unpaid jobs (D722) | P1 |
| TC-NFS-007 | LPG exchange rule | Exchange and outright split; imbalance D720 | P1 |
| TC-MDB-001 | `sale.post` idempotency | Same `client_txn_id` ten times → one invoice (I411) | P0 |
| TC-MDB-002 | FCC transaction paid once | Two devices claim one transaction → I412 | P0 |
| TC-MDB-003 | Mobile money receipt used once | I414 | P0 |
| TC-MDB-004 | Offline queue | Replay in order at device time; old price version flagged (I413); limits (I418) | P0 |
| TC-MDB-005 | Close blocked by unsynced device | I420; device release; late sync via correction | P0 |
| TC-MDB-006 | Totaliser completeness | I419 on a gap | P0 |
| TC-MDB-007 | Unpaid FCC transactions at close | Charged to attendant tag, then nozzle assignment | P0 |
| TC-MDB-008 | Residual invoice and cashier balance (nf 11.12 example) | Exact figures of the example | P0 |
| TC-MDB-009 | Fiscal wait | Receipt prints "fiscal receipt to follow" after the timeout; fiscal data later | P1 |
| TC-MDB-010 | Device security | Revoked key refused (I415); session per cashier; idle lock | P0 |

---

## 37. Release gates, exit criteria and test management

### 37.1 Gates

| Gate | Must pass | Blocks |
|---|---|---|
| **Every commit** (CI, FMS-L01) | All U and D tests; invariant checks; TC-PBT at CI example counts; lint and security checks (FMS-L02) | Merge |
| **Merge to main** | Above, plus the golden month (FMS-K01) and scenario scripts | Release candidate |
| **Nightly** | C, R, S layers; TC-PBT at nightly counts; fuzz; mutation (weekly) | Next day's release candidate if a P0 fails |
| **Release candidate** | Everything above; P layer; manual M scripts; sandbox acceptance (25.5) when integrations changed | Release |
| **Pilot start** (FMS-N02) | Release gate; UAT signed (FMS-K06); opening balances verified (TC-MIG-005) | Parallel run |
| **Go-live** (FMS-N04) | Parallel run thresholds met (TC-MIG-007); no open Sev1 or Sev2; runbooks tested (TC-REC-007, TC-REC-012) | Go-live |

### 37.2 Exit criteria for a release

| Criterion | Threshold |
|---|---|
| P0 cases | 100% pass, no waivers |
| P1 cases | 100% pass, or a written waiver signed by the owner per case |
| Invariants | No violation in any run |
| Property tests | Nightly counts with no failure for 3 consecutive nights |
| Mutation score on `calc/` | ≥ 90% |
| Coverage | `calc/` 100% branches; `posting/`, `corrections/`, gates ≥ 95% lines; app overall ≥ 85% |
| Open defects | No Sev1 or Sev2 |
| Performance | Section 34 targets |
| Open questions | Every **Open** case used by the release has a decision (section 39) |

### 37.3 Defect severity

| Sev | Meaning | Example | Fix before |
|---|---|---|---|
| **Sev1** | Wrong or lost money or stock, duplicate posting, data corruption, security breach | Close posts a payment twice | Immediately; release blocked; hotfix in production |
| **Sev2** | Control bypassed, gate missing, report total wrong | Approver can approve own variance | Next release; usually blocks |
| **Sev3** | Wrong message, recoverable failure handled badly | Raw ERPNext error shown | Planned |
| **Sev4** | Cosmetic | Label misaligned | Backlog |

### 37.4 Regression rule

Every defect found anywhere (CI, UAT, pilot, production) gets a test case **before** the fix is merged. The case takes the next free ID in its area and names the defect in its description.

### 37.5 Writing the tests

| Rule | Detail |
|---|---|
| Naming | Test functions carry the case ID: `test_TC_MTR_003_closing_below_opening_without_rollover` |
| Location | `forecourt/tests/<area>/` per section of this catalogue; calculations next to `calc/` |
| Assertions | Assert the FMS code and the absence of side effects (T6, T7) |
| Flaky tests | Quarantined at most 7 days with an owner; **P0 tests are never quarantined**: a flaky P0 test is treated as a Sev1 defect |
| Data | Factories only (3.3); no reliance on data from other tests |
| Reporting | CI publishes results by case ID, so this catalogue can show pass or fail per case |

### 37.6 Tasks

For a new TASKS.md section **T. Test catalogue** (prefix FMS-T, unused):

| Task | Scope | Size |
|---|---|---|
| FMS-T01 | Map existing tests to case IDs; list uncovered P0 cases | M |
| FMS-T02 | Invariant checker (section 4) wired into every posting test | M |
| FMS-T03 | Factories and simulators (3.3, 3.5) | L |
| FMS-T04 | Property-based tests and fuzzers (section 5) | L |
| FMS-T05 | Calculation cases (section 6) | M |
| FMS-T06 | Document and gate cases (sections 7 to 18) | L |
| FMS-T07 | Posting, approval, correction, immutability, period cases (sections 19 to 23) | L |
| FMS-T08 | Integration and security cases (sections 25, 30) | L |
| FMS-T09 | Concurrency and resilience harness and cases (sections 26, 27) | L |
| FMS-T10 | Time, number, multi-company cases (sections 28, 29, 32) | M |
| FMS-T11 | Fraud scenario scripts (section 31) | M |
| FMS-T12 | Migration and go-live checks (section 33) | M |
| FMS-T13 | Performance set and runs (section 34) | M |
| FMS-T14 | Decisions on Open cases (section 39), then their tests | M |

FMS-K01 (golden month) remains the single end-to-end acceptance test.

### 37.7 Case counts

| Area | Prefix | P0 | P1 | P2 | P3 | Total |
|---|---|---|---|---|---|---|
| Property-based | PBT | 7 | 0 | 0 | 0 | 7 |
| Fuzzing | FUZ | 5 | 0 | 0 | 0 | 5 |
| Calculations | CAL | 44 | 10 | 1 | 0 | 55 |
| Masters | MST | 13 | 8 | 1 | 0 | 22 |
| Shift creation | SHC | 13 | 6 | 1 | 0 | 20 |
| Meters | MTR | 8 | 5 | 2 | 1 | 16 |
| Dips | DIP | 12 | 3 | 1 | 0 | 16 |
| Deliveries | DLV | 17 | 4 | 0 | 0 | 21 |
| Own use, tests, transfers, meter changes | OWN | 15 | 1 | 1 | 0 | 17 |
| Prices | PRC | 14 | 3 | 0 | 0 | 17 |
| Cash | CSH | 15 | 4 | 3 | 0 | 22 |
| Payments | PAY | 25 | 5 | 0 | 0 | 30 |
| Credit | CRD | 12 | 3 | 2 | 0 | 17 |
| Expenses | EXP | 5 | 1 | 1 | 0 | 7 |
| Gates | GTE | 5 | 3 | 0 | 0 | 8 |
| Posting | PST | 22 | 4 | 0 | 0 | 26 |
| Approvals | APR | 8 | 3 | 1 | 0 | 12 |
| Corrections | COR | 18 | 1 | 1 | 0 | 20 |
| Cancellation, immutability | CAN | 11 | 3 | 0 | 0 | 14 |
| Periods | PER | 5 | 2 | 0 | 0 | 7 |
| Ledgers, reports | LED | 9 | 1 | 0 | 0 | 10 |
| Integrations | INT | 11 | 5 | 1 | 0 | 17 |
| Concurrency | CON | 14 | 0 | 0 | 0 | 14 |
| Recovery | REC | 7 | 4 | 1 | 0 | 12 |
| Time | TIM | 8 | 5 | 0 | 0 | 13 |
| Numbers | NUM | 8 | 4 | 0 | 0 | 12 |
| Security | SEC | 12 | 7 | 0 | 0 | 19 |
| Fraud | FRD | 6 | 8 | 2 | 0 | 16 |
| Multi-company | MCY | 6 | 0 | 1 | 1 | 8 |
| Migration | MIG | 6 | 0 | 1 | 1 | 8 |
| Performance | PRF | 0 | 7 | 0 | 0 | 7 |
| UI | UIX | 2 | 2 | 3 | 0 | 7 |
| Non-fuel (proposed) | NFS | 5 | 2 | 0 | 0 | 7 |
| Mode B (proposed) | MDB | 9 | 1 | 0 | 0 | 10 |
| **Total** | | **377** | **115** | **24** | **3** | **519** |

Property-based (TC-PBT) and fuzz (TC-FUZ) cases count as P0: each one checks the invariants. Each property case runs hundreds to thousands of generated examples. 64 cases have an expected result waiting for a decision (section 39).

---

## 38. Traceability: error codes to tests

Every FMS error code in fms.md 15.3 must have at least one test that triggers it. Codes proposed in other documents are listed when this catalogue tests them.

| Code | Tests |
|---|---|
| FMS-S101 | TC-CAL-003, TC-MTR-002, TC-MTR-003 |
| FMS-S102 | TC-SHC-004, TC-SHC-005 |
| FMS-S103 | TC-DIP-001 |
| FMS-S104 | TC-MST-021, TC-MTR-004 |
| FMS-S105 | TC-CSH-001, TC-CSH-006 |
| FMS-S106 | TC-DIP-002, TC-DIP-003 |
| FMS-S107 | TC-CRD-001, TC-CRD-002, TC-CRD-003, TC-CRD-004, TC-CRD-007, TC-FRD-003 |
| FMS-S108 | TC-CRD-008 |
| FMS-S109 | TC-EXP-001, TC-EXP-002, TC-FRD-007 |
| FMS-S110 | TC-GTE-007, TC-MST-020, TC-SHC-007 |
| FMS-S111 | TC-GTE-008, TC-PAY-005 |
| FMS-S112 | TC-PRC-001, TC-PRC-002 |
| FMS-S113 | TC-OWN-002 |
| FMS-S114 | TC-FRD-006, TC-PAY-011, TC-PAY-012, TC-PAY-013 |
| FMS-S115 | TC-FRD-002, TC-OWN-011 |
| FMS-W102 | TC-CAL-007 |
| FMS-W103 | TC-MTR-010 |
| FMS-T201 | TC-CAL-039, TC-CAL-040 |
| FMS-T202 | TC-CAL-034, TC-CAL-040, TC-DLV-016 |
| FMS-T203 | TC-DIP-004, TC-DIP-005, TC-DIP-006 |
| FMS-T204 | TC-DLV-008 |
| FMS-T205 | TC-DLV-003, TC-FRD-009 |
| FMS-T206 | TC-DLV-001, TC-DLV-020 |
| FMS-P301 | TC-MST-018, TC-PST-022 |
| FMS-P302 | TC-OWN-022, TC-PST-021 |
| FMS-I401 | TC-PAY-004 |
| FMS-C501 | TC-APR-011 |
| FMS-C502 | TC-CAN-001, TC-CAN-002, TC-CAN-003, TC-DLV-017 |
| FMS-C503 | TC-CAN-005, TC-CAN-006, TC-SHC-019 |
| FMS-M601 | TC-MST-001 |
| FMS-M602 | TC-MCY-002, TC-MST-003, TC-MST-004 |
| FMS-M603 | TC-CAL-019, TC-MST-005, TC-MST-006 |
| FMS-M604 | TC-MST-007 |
| FMS-M605 | TC-FUZ-005, TC-MST-008, TC-MST-009 |
| FMS-M606 | TC-MST-010 |
| FMS-M607 | TC-MST-012, TC-MST-013 |
| *Proposed (ux guide 20.4)* | |
| FMS-S116 (proposed) | TC-SHC-008 |
| FMS-S117 (proposed) | TC-SHC-009 |
| FMS-S118 (proposed) | TC-SHC-015 |
| FMS-S119 (proposed) | to add with UX-06, UX-12 |
| FMS-S120 (proposed) | TC-CON-001 |
| *Proposed (fms-nonfuel.md)* FMS-D7xx, FMS-I411 to I420 | TC-NFS-001 to 007, TC-MDB-001 to 010 (expanded when accepted) |

---

## 39. Open questions

Each question comes from a test case whose expected result the specifications do not define. The proposed answer is the default the test will use once the owner confirms it.

| # | Case | Situation | Question | Proposed default |
|---|---|---|---|---|
| Q-01 | TC-CAL-005 | Rollover ticked but closing ≥ opening | is a tick with no rollover an error? | refuse the tick (coded message); sold = closing − opening. |
| Q-02 | TC-CAL-006 | Rollover ticked and closing exactly equals opening | a full cycle (≈1 million litres in a shift) is implausible. | refuse; a nozzle cannot sell its full meter range in one shift. |
| Q-03 | TC-CAL-015 | Drift exactly at the tolerance boundary | Within tolerance (boundary inclusive) — inclusive or exclusive? | inclusive. |
| Q-04 | TC-CAL-018 | Own use + test greater than basis litres | Error (net sold cannot be negative). — code? | new FMS-W1xx code. |
| Q-05 | TC-CAL-033 | Depth below the first row (chart starts at 50 mm) | extrapolate, use 0, or refuse? | refuse with a coded message naming the chart's minimum. |
| Q-06 | TC-CAL-036 | Water depth greater than product depth | Refused (impossible reading). — code. | To be defined |
| Q-07 | TC-MST-011 | Nozzle linked to a tank holding another product | Refused. — code (not in 15.3). | FMS-M608. |
| Q-08 | TC-MST-014 | Change a tank's warehouse after shifts exist | allowed? | refused once any ledger row exists. |
| Q-09 | TC-MST-015 | Change a tank's product after shifts exist | Refused (history would become wrong). — code. | To be defined |
| Q-10 | TC-MST-017 | Deactivate a nozzle while a shift is open with its row | remove the row, keep it, or block? | block deactivation while a draft shift includes it. |
| Q-11 | TC-MST-020 | Shift template times overlapping another template of the station (Day 06–18, Night 17–06) | blocked at template level or only at shift level (FMS-S110)? | warn on the template, block at the shift. |
| Q-12 | TC-MST-022 | Station time zone changed after shifts exist | allowed? | refused, or only effective for shifts created afterwards with a warning. |
| Q-13 | TC-SHC-008 | Two draft shifts at the same station at the same time | allowed (D28)? | per ux 11.2: refused with FMS-S116 unless overlap allowed. |
| Q-14 | TC-SHC-009 | New shift while the previous is Pending Approval | allowed? Openings would come from an unsubmitted shift. | refused (ux FMS-S117). |
| Q-15 | TC-SHC-010 | Nozzle added to the station after this shift was created | must the open shift get the row? | a gate refuses close while an active nozzle has no row; a button adds missing rows. |
| Q-16 | TC-SHC-012 | Out-of-service nozzle whose meter changed between shifts |  | block return to service until a Meter Change explains the movement. |
| Q-17 | TC-SHC-017 | Shift date in the future |  | refused beyond the next scheduled slot. |
| Q-18 | TC-MTR-006 | Handover rows that do not chain (second opening ≠ first closing) | Refused. — code. | To be defined |
| Q-19 | TC-MTR-014 | Power cut, manual bypass: "manual meter adjustment with a reason" | how is a manual adjustment represented (6.5)? | a row field `manual_adjustment_l` with a mandatory reason, shown as an exception. |
| Q-20 | TC-MTR-016 | Meter with three decimals on one pump (precision mismatch) | precision per meter? (ux Q-12) | To be defined |
| Q-21 | TC-DIP-014 | Dip shows tank above capacity | warning or block? | block above capacity, warn above safe fill. |
| Q-22 | TC-DLV-007 | Over-delivery (+0.5%) | reason required for gains too? | same tolerance both ways. |
| Q-23 | TC-DLV-009 | GRN posted after the shift closed, dated inside its window | blocked (nf D50 for counted items) or allowed with repost? | blocked for tank warehouses; post at real time or via correction. |
| Q-24 | TC-DLV-011 | GRN posting time exactly at `shift_end` | window inclusive or exclusive at each end? | start inclusive, end exclusive. |
| Q-25 | TC-DLV-014 | Diesel GRN line into a petrol tank warehouse | Refused (product does not match the tank). — code. | To be defined |
| Q-26 | TC-DLV-015 | Dip after lower than dip before with no sales during drop | Refused or negative received flagged. — code. | To be defined |
| Q-27 | TC-DLV-018 | Purchase Return of fuel from a tank | pulled into the shift as negative receipts? | yes, as a transfer-out line. |
| Q-28 | TC-DLV-021 | GRN with zero rate (price unknown) | allowed? COGS would be zero. | refused for fuel items. |
| Q-29 | TC-OWN-007 | Own use posted outside any shift window (between shifts) | which shift pulls it? | the shift whose window contains it; between shifts (gap) it is refused. |
| Q-30 | TC-OWN-031 | Meter Change while a shift is open on the nozzle |  | refused while a draft shift includes the nozzle, or it splits the row like a handover. |
| Q-31 | TC-OWN-032 | Meter Change with old final reading below the last closing | Refused (litres would vanish). — code. | To be defined |
| Q-32 | TC-PRC-007 | `effective_at` exactly equal to `shift_end` | belongs to this shift (zero-length segment) or the next? | next shift (end exclusive). |
| Q-33 | TC-PRC-008 | Price change back-dated into a closed shift window |  | refused; history of closed shifts never changes. |
| Q-34 | TC-PRC-011 | Approved price change cancelled while the shift is open |  | cancellation refused once a shift has a segment from it; post a new change instead. |
| Q-35 | TC-PRC-015 | Price change submitted while the shift is *Closing* |  | segment refused for a closing shift; applies from the next. |
| Q-36 | TC-CSH-008 | Shortage resolved as *Charge* to an Employee who has left | allowed? | allowed with a warning; recovery tracked in CSH-06. |
| Q-37 | TC-CSH-009 | Cashier disabled as Employee before the shift closes |  | close allowed; new shifts refuse the cashier. |
| Q-38 | TC-CSH-010 | Same cashier on open shifts at two stations at the same time |  | refused when windows overlap. |
| Q-39 | TC-CSH-019 | No exchange rate for the date |  | close refused with a coded message naming the currency pair and date. |
| Q-40 | TC-PAY-006 | Callback arrives after the shift closed for a payment inside its window | Stays on the unmatched list; not added to the closed shift. — how is it resolved (correction, next shift, accountant)? | accountant assigns it through a Native document correction; never to the next shift. |
| Q-41 | TC-PAY-009 | Reversal of a payment (provider reverses after customer dispute) | how are reversals represented and posted? | a negative feed entry linked to the original; if the original is in a closed shift, flagged for a correction; never silently netted. |
| Q-42 | TC-PAY-010 | Amount in callback differs from the statement for the same reference | which wins? | statement is authoritative; difference flagged in PAY-01. |
| Q-43 | TC-PAY-012 | Reference typed manually, then the feed arrives with the same reference | match or duplicate? | the feed entry links to the typed collection; no second row; S114 never fires for this pair. |
| Q-44 | TC-CRD-006 | Over-limit approved in FMS but ERPNext's own credit-limit check blocks the Sales Invoice at posting | how does an FMS-approved over-limit pass ERPNext's native check (Credit Controller role, bypass setting)? | posting user holds the bypass only for approved slips; otherwise the close fails atomically with a coded message, never a raw ERPNext error. |
| Q-45 | TC-CRD-009 | Customer disabled or frozen in ERPNext | caught as a gate before posting? | yes, new code; the close never fails at posting for a known condition. |
| Q-46 | TC-CRD-010 | Duplicate slip number for the same customer | blocked? | refused within the same slip book. |
| Q-47 | TC-CRD-014 | Customer currency differs from company currency | supported? | credit customers must use the company currency in Phases 0 to 3. |
| Q-48 | TC-EXP-003 | Expense receipt required by setting, not attached | Refused. — code. | To be defined |
| Q-49 | TC-EXP-005 | ERPNext budget with action *Stop* exceeded by the expense | gate before posting? | checked at readiness; never a raw budget error at posting. |
| Q-50 | TC-EXP-006 | Many small expenses that together exceed a daily limit | is there a daily limit? | not in Phases 0 to 3; reported in EXP-02. |
| Q-51 | TC-PST-004 | Shift with zero sales and zero collections | close allowed with no documents except ledgers and tank reconciliation? | yes. |
| Q-52 | TC-PST-029 | Fiscal adapter (on Sales Invoice submit) times out during close | does a fiscal failure roll back the close? | no; the invoice posts and fiscalisation retries through the Integration Inbox; CMP-02 shows it pending. |
| Q-53 | TC-PST-043 | Worker killed mid-job | Transaction rolled back by the database; shift stuck in Closing is detected and returned to Reconciled. — detection rule? | a scheduler check resets Closing older than the job timeout after confirming no documents exist. |
| Q-54 | TC-PST-044 | Redis or the queue unavailable at close |  | close refused with a coded message; status unchanged. |
| Q-55 | TC-APR-006 | A non-approval field changed after approval (a typo in a note) | does any change reset approval? | only approved amounts, reasons and readings that change them. |
| Q-56 | TC-COR-004 | Same, the next two shifts closed | the spec moves litres between this and the next shift only. | only the next shift is affected because its opening changes; later shifts are unaffected. |
| Q-57 | TC-COR-007 | Dip correction while a Repost Item Valuation for the station is still running |  | correction waits or is refused until reposting finishes. |
| Q-58 | TC-CAN-012 | Amend a cancelled shift | allowed? | refused; create a new shift. |
| Q-59 | TC-PER-004 | Period closed while a shift of that period is still open |  | period close refused while drafts or Pending Approval shifts exist in it (checked by a hook on Accounting Period). |
| Q-60 | TC-INT-008 | Malformed JSON | Rejected (4xx) or stored as Failed. — which? | store with status Failed when the signature is valid, reject otherwise. |
| Q-61 | TC-INT-021 | Valid signature replayed hours later | timestamp window? | rejected outside a configurable window; idempotency still protects. |
| Q-62 | TC-CON-004 | GRN submitted into the window while the shift is Closing | Either way never a close that misses a receipt. | GRN refused while the shift whose window contains it is Closing; or the close detects it and fails. |
| Q-63 | TC-MIG-003 | Fixture update (workspaces, roles) on a site where the customer changed a workspace | overwrite or keep? | standard workspaces overwritten; customer copies untouched. |
| Q-64 | TC-MIG-007 | Parallel run (FMS-N02): daily comparison of FMS with the current books | Differences explained daily; acceptance thresholds met. — thresholds for litres, cash and stock? | To be defined |
