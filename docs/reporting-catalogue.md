# AFMS Reporting Catalogue

**Version:** 1.0 (draft for review)
**Date:** 2026-11-06
**Applies to:** the `forecourt` app (AFMS) on Frappe Framework v16 and ERPNext v16
**Companion documents:** [fms.md](fms.md) v1.3 (behaviour; section 11 reporting) · [catalogue.md](catalogue.md) v1.2 (DocTypes, ledger fields, report list 13.1) · [ui-ux-design-guide.md](ui-ux-design-guide.md) v1.0 (sections 13 to 15: reporting standards, reports, dashboards) · [fms-nonfuel.md](fms-nonfuel.md) v0.2 (non-fuel and Mode B, proposed)
**Audience:** developers and AI coding agents building reports, accountants and managers reviewing them, the owner

This catalogue defines **every standard report AFMS provides**: what it answers, who uses it, where its data comes from, its filters, grouping, columns, calculations, totals, summary figures, chart and drill-down. It also defines the **shared filter and totals framework** all reports use, so that a filter, a total or a percentage behaves the same way in every report.

It expands section 14 of the UI/UX guide. The standards in sections 13 and 15 of that guide (report types, filter order, totals rules, dashboards) still apply and are restated here in more detail. Where the two differ, this catalogue wins for reports.

---

## How to read this catalogue

### Status marks

| Mark | Meaning |
|---|---|
| **[Exists]** | Built, according to TASKS.md (FMS-H01 to H11 ticked). Specification here may *extend* it; extensions are marked **(ext.)**. |
| **[Spec]** | Documented in fms.md or catalogue.md, not in the built list |
| **[New]** | Proposed by this catalogue |
| **[P]** | From fms-nonfuel.md: depends on decisions D37 to D62 being accepted |
| **[ERPNext]** | A native ERPNext report used as is, with AFMS filters or the Station dimension. AFMS adds nothing but a link. |
| **[Open]** | Needs a decision before building (section 33) |

**Limitation.** The built report code was not available when this catalogue was written. "[Exists]" reflects TASKS.md, not a code review. Task FMS-R01 (section 32) compares each built report with this catalogue before extensions are made.

### Report identifiers

Every report has an ID `DOM-nn` (for example `WET-03`), used in tasks, tests and reviews. The **title** is what users see. IDs never change; titles may.

| Prefix | Domain | Section |
|---|---|---|
| SHF | Shifts and daily operations | 7 |
| SAL | Fuel sales and volume | 8 |
| MTR | Meters, pumps and nozzles | 9 |
| WET | Wetstock and tanks | 10 |
| DLV | Deliveries | 11 |
| PRC | Prices, costs and margins | 12 |
| CSH | Cash and cashier accountability | 13 |
| PAY | Mobile money, card and bank | 14 |
| CRD | Credit customers and fleets | 15 |
| PUR | Purchases, suppliers and payables | 16 |
| DRY, LPG, SRV | Shop and lubricants, LPG, services | 17 |
| EXP | Expenses and own use | 18 |
| STF | Staff and productivity | 19 |
| CTL | Control, fraud and audit | 20 |
| EQP | Equipment, calibration and maintenance | 21 |
| CMP | Tax, fiscal and regulatory | 22 |
| FIN | Financial and management | 23 |
| FCS | Planning and forecasting | 24 |
| INT | Integrations, devices and system health | 25 |

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Reporting architecture](#2-reporting-architecture)
3. [The common filter framework](#3-the-common-filter-framework)
4. [The totals and summary framework](#4-the-totals-and-summary-framework)
5. [Presentation standards](#5-presentation-standards)
6. [Report index](#6-report-index)
7. [Shifts and daily operations (SHF)](#7-shifts-and-daily-operations-shf)
8. [Fuel sales and volume (SAL)](#8-fuel-sales-and-volume-sal)
9. [Meters, pumps and nozzles (MTR)](#9-meters-pumps-and-nozzles-mtr)
10. [Wetstock and tanks (WET)](#10-wetstock-and-tanks-wet)
11. [Deliveries (DLV)](#11-deliveries-dlv)
12. [Prices, costs and margins (PRC)](#12-prices-costs-and-margins-prc)
13. [Cash and cashier accountability (CSH)](#13-cash-and-cashier-accountability-csh)
14. [Mobile money, card and bank (PAY)](#14-mobile-money-card-and-bank-pay)
15. [Credit customers and fleets (CRD)](#15-credit-customers-and-fleets-crd)
16. [Purchases, suppliers and payables (PUR)](#16-purchases-suppliers-and-payables-pur)
17. [Shop, lubricants, LPG and services (DRY, LPG, SRV)](#17-shop-lubricants-lpg-and-services-dry-lpg-srv)
18. [Expenses and own use (EXP)](#18-expenses-and-own-use-exp)
19. [Staff and productivity (STF)](#19-staff-and-productivity-stf)
20. [Control, fraud and audit (CTL)](#20-control-fraud-and-audit-ctl)
21. [Equipment, calibration and maintenance (EQP)](#21-equipment-calibration-and-maintenance-eqp)
22. [Tax, fiscal and regulatory (CMP)](#22-tax-fiscal-and-regulatory-cmp)
23. [Financial and management (FIN)](#23-financial-and-management-fin)
24. [Planning and forecasting (FCS)](#24-planning-and-forecasting-fcs)
25. [Integrations, devices and system health (INT)](#25-integrations-devices-and-system-health-int)
26. [Scheduled reports and distribution](#26-scheduled-reports-and-distribution)
27. [Report access by role](#27-report-access-by-role)
28. [Performance, indexes and prepared reports](#28-performance-indexes-and-prepared-reports)
29. [Testing reports](#29-testing-reports)
30. [Data gaps found while specifying reports](#30-data-gaps-found-while-specifying-reports)
31. [Mapping to existing and earlier report lists](#31-mapping-to-existing-and-earlier-report-lists)
32. [Build plan](#32-build-plan)
33. [Open questions](#33-open-questions)

---

## 1. Purpose and scope

### 1.1 The questions a petrol station business asks

The catalogue is organised around the questions people ask, not around tables. Every report answers at least one of them.

| Area | Typical questions | Main reports |
|---|---|---|
| **Daily running** | Did every shift close? What is still open? What did we sell yesterday? | SHF-02, SHF-05, SHF-06 |
| **Fuel accountability** | Is any fuel missing? Which tank, which shift, which cashier? Is a tank leaking? | WET-02, WET-03, WET-04, MTR-01 |
| **Money accountability** | Is any money missing? Who is short, how often, and has it been recovered? | SHF-04, CSH-01, CSH-02, CSH-06 |
| **Payments** | Did every M-Pesa and card payment reach the bank? What is unmatched? | PAY-01, PAY-02, PAY-03, PAY-04 |
| **Customers** | What does each fleet owe, which vehicles bought what, is anyone over the limit? | CRD-01 to CRD-05 |
| **Supply** | Did we receive what we paid for? Which supplier or driver delivers short? When will we run out? | DLV-01 to DLV-04, PUR-01, FCS-01 |
| **Profit** | What margin do we make per litre, per product, per station, after losses? | PRC-03, PRC-04, FIN-01 |
| **Control** | What was written off, approved, corrected or back-dated, and by whom? | CTL-01 to CTL-08 |
| **Equipment** | Are meters, tanks and calibration charts in order? | EQP-01 to EQP-04, MTR-02 |
| **Compliance** | What tax did we charge, were invoices fiscalised, what volume do we report to the regulator? | CMP-01 to CMP-04 |
| **Owners** | How are my stations doing compared with each other and last year? | FIN-03 to FIN-06 |

### 1.2 Out of scope

- Full ERPNext financial reporting (statements, registers, ageing) is native and used as is; this catalogue only says how AFMS uses it (marked [ERPNext]).
- External BI (Frappe Insights, a column store) is optional (fms.md 11.5). Reports here are built inside Frappe.
- Payroll and HR reports belong to HRMS when installed.

---

## 2. Reporting architecture

### 2.1 Data sources

Reports read **flat, indexed tables**, never the nested shift document, except registers that list documents (fms.md 11.1).

| Source | Grain | Used for | Key fields (catalogue 10) |
|---|---|---|---|
| **Nozzle Ledger Entry** | Nozzle × cashier × price segment × shift | Meter movement, litres by equipment, drift, tests | `nozzle`, `pump`, `island`, `tank`, `item`, `cashier`, `attendant`, `segment_no`, `price`, `opening_*`, `closing_*`, `*_delta`, `basis_meter`, `gross_l`, `test_l`, `own_use_l`, `net_l`, `amount`, drift fields, `source` |
| **Sales Ledger Entry** | Shift × cashier × sales line × payment type | Sales by any dimension, payment mix | `item`, `item_group`, `is_fuel`, `nozzle`, `pump`, `island`, `tank`, `cashier`, `payment_type`, `mode_of_payment`, `customer`, `customer_vehicle`, `qty`, `amount`, `basis` |
| **Cashier Ledger Entry** | Cashier × shift | Balances, differences, resolutions | `cashier`, `fuel_l`, `fuel_amount`, `item_amount`, `debt_receipts`, `float_amount`, `cash`, `mobile`, `card`, `credit`, `voucher`, `expenses`, `drops`, `expected`, `accounted`, `difference`, `resolution_action`, `resolution_amount`, `reason` |
| **Wetstock Ledger Entry** | Tank × event (shift, delivery, spot dip, transfer, meter change, adjustment) | Tank reconciliation, deliveries, variance | `tank`, `item`, `entry_type`, `opening_l`, `receipt_l`, `sales_l`, `test_l`, `own_use_l`, `transfer_l`, `expected_l`, `dip_l`, `variance_l`, `variance_pct`, `invoiced_l`, `delivery_variance_l`, `supplier`, `transporter`, `driver`, `cashiers`, `reason`, `approved_by`, `source`, `valuation_rate`, `variance_value` |
| **[P] Dry Stock Ledger Entry** | Item × cashier × shift (count) | Non-fuel stock | fms-nonfuel.md 14.5 |
| **Common ledger fields** | | Filters and audit | `company`, `station`, `posting_date`, `forecourt_shift`, `voucher_type`, `voucher_no`, `is_cancelled`, `superseded_by`, `correction` |
| **ERPNext GL Entry** | Account × voucher | Money, margins, balances, P&L | With the **Station** accounting dimension |
| **ERPNext Stock Ledger Entry** | Item × warehouse × voucher | Stock position, valuation, cost of goods sold | Tank warehouses, shop warehouses |
| **FMS documents** | One row per document or child row | Registers: credit slips, spot dips, transfers, meter changes, price changes, corrections, collections, feed entries | Catalogue 8 to 11 |
| **ERPNext documents** | | Purchases, invoices, payments, tax | Purchase Order, Purchase Receipt, Purchase Invoice, Sales Invoice, Payment Entry, Bank Transaction |
| **Version, Comment, Workflow history** | | Audit and approval reports | Native |

### 2.2 Rules that apply to every ledger query

| Rule | Why |
|---|---|
| `is_cancelled = 0` | Cancelled postings never count |
| `superseded_by IS NULL` by default | Corrections replace rows; reports show corrected figures (fms.md 6.8). The **Include correction history** filter (3.6) shows both, with a *Superseded* flag. |
| Station permission conditions applied explicitly | Script Reports that use `frappe.qb` or SQL do **not** apply User Permissions automatically. Every report uses the shared helper `forecourt.reports.common.permitted_stations()` and adds `station IN (…)` and `company IN (…)` (section 27.3). |
| `posting_date` is the shift date | Overnight shifts belong to the evening they started (D20). Reports never re-derive dates from times. |
| Money in company currency | Ledger and GL amounts are in the company's currency. Cross-company totals follow 4.7. |
| Sign convention | Variance = physical − book. Negative is a loss (fms.md 5.5). Difference = accounted − expected. Negative is a shortage. |

### 2.3 Report types

| Type | When | Share of this catalogue |
|---|---|---|
| **Script Report** | Anything with calculations, grouping options, comparisons, tree rows, summary cards or charts. **The default.** | Most |
| **Query Report** | One SQL query, no post-processing, simple filters | Registers (CRD-01, WET-06, WET-07, EQP-02) |
| **Print Format** | One document on one page | SHF-01 |
| **Report Builder** (saved reports) | User-defined lists; not part of the standard set | — |
| **[ERPNext] native** | Statements, ageing, registers, stock balance | FIN-01, FIN-02, CRD-06, PUR-04 |
| **Prepared Report** (native background report) | Group-wide or multi-year runs that would exceed the time limit | Flagged per report (section 28) |

### 2.4 Code layout and naming

| Item | Convention |
|---|---|
| Location | `forecourt/<module>/report/<report_name>/` with `<report_name>.py`, `.js`, `.json` |
| Module | The module of the main source (catalogue 13.1 for existing reports; section 6 for new ones) |
| Shared code | `forecourt/reports/common.py` (filters, permissions, periods, comparisons, totals, tree rows, currency) and `forecourt/public/js/report_filters.js` (standard filter definitions and presets) |
| Report name | Title Case, describes what is shown; plural for lists (*Credit Slips Register*) |
| Column fieldnames | snake_case, units in the label, not the fieldname: `variance_l` labelled *Variance (L)* |
| Calculations | Pure functions in `forecourt/calc/` where they are shared with the shift (variance, tolerance), so a report and the shift never compute differently |

---

## 3. The common filter framework

All reports build their filters from one shared definition, so the same filter has the same name, type, default, order and dependency everywhere.

### 3.1 Filter order

Filters always appear in this order (reports omit what they do not use):

1. **Scope:** Company · Station group · Station(s)
2. **Time:** Period preset · From date · To date · Compare with · Granularity
3. **Shift:** Shift template · Shift
4. **Equipment:** Tank · Island · Pump · Nozzle
5. **Product:** Item group · Product(s) · Fuel only
6. **People:** Cashier · Attendant · Prepared by · Approved by
7. **Parties:** Customer group · Customer · Vehicle · Supplier · Transporter · Driver
8. **Payments:** Payment type(s) · Provider · Till or terminal · Basis
9. **Status and source:** Status · Source · Reason
10. **Thresholds:** Only exceptions · Minimum amount · Minimum variance % · Minimum litres
11. **Presentation:** Group by · Then by · Top N · Show zero rows · Include correction history · Presentation currency

### 3.2 Standard filters

| Filter | Fieldname | Type | Default | Depends on (`get_query`) | Notes |
|---|---|---|---|---|---|
| Company | `company` | Link Company | User's default company | | Mandatory where money is shown |
| Company (multi) | `companies` | MultiSelectList Company | User's permitted companies | | Group reports only |
| Station group | `station_group` | Link Station Group (tree) | | Company | Includes all descendant groups |
| Station | `station` | Link Station | User's default station | Company, station group | Station reports |
| Stations (multi) | `stations` | MultiSelectList Station | All permitted | Company, station group | Network reports |
| Period | `period` | Select | Report-specific | | Presets in 3.3; sets From and To |
| From date, To date | `from_date`, `to_date` | Date | From the period | | Mandatory |
| Date | `date` | Date | Yesterday or today | | Daily reports only, instead of From/To |
| Compare with | `compare_with` | Select: None / Previous period / Same period last year / Network average | None | | Section 3.4 |
| Granularity | `granularity` | Select: Shift / Day / Week / Month / Quarter / Year | Report-specific | | Time grouping |
| Shift template | `shift_template` | Link | | Station | Day, Night… |
| Shift | `forecourt_shift` | Link Forecourt Shift | | Station, dates | |
| Tank | `tank` | Link Fuel Tank | | Station | |
| Island, Pump, Nozzle | `island`, `pump`, `nozzle` | Link | | Station; pump on island; nozzle on pump | |
| Item group | `item_group` | Link Item Group (tree) | | | Descendants included |
| Products | `items` | MultiSelectList Item | | Item group; fuel flag where relevant | |
| Fuel only | `fuel_only` | Check | Report-specific | | `is_fuel` |
| Cashier | `cashier` | Link Employee | | `fms_is_forecourt_cashier` = 1; station via shift history | |
| Attendant | `attendant` | Link Employee | | Station | |
| Prepared by, Approved by | `prepared_by`, `approved_by` | Link User | | | Control reports |
| Customer group, Customer | `customer_group`, `customer` | Link | | Customer group | |
| Vehicle | `customer_vehicle` | Link Customer Vehicle | | Customer | |
| Supplier, Transporter, Driver | `supplier`, `transporter`, `driver` | Link / Data | | | |
| Payment types | `payment_types` | MultiSelectList: Cash, Mobile Money, Card, Credit, Voucher | All | | |
| Provider | `provider` | Link Payment Provider | | | |
| Till or terminal | `till_or_terminal` | Data | | Provider, station | |
| Basis | `basis` | Select: All / Exact / Attributed | All | | Sales Ledger only (2.1) |
| Status | `status` | Select | Report-specific | | |
| Source | `source` | Select: All / Manual / Import / Handheld / FCC / ATG | All | | |
| Reason | `reason` | Link Variance Reason | | | |
| Only exceptions | `only_exceptions` | Check | Report-specific | | Rows outside tolerance, with a difference, or flagged |
| Minimum amount, Minimum litres, Minimum variance % | `min_amount`, `min_litres`, `min_variance_pct` | Currency, Float, Percent | Blank | | Absolute value compared |
| Group by, Then by | `group_by`, `then_by` | Select | Report-specific | | Two-level grouping (4.3) |
| Top N | `top_n` | Int | Blank | | Ranking reports |
| Show zero rows | `show_zero_rows` | Check | Off | | E.g. idle nozzles |
| Include correction history | `include_history` | Check | Off | | Audit view (2.2) |
| Presentation currency | `presentation_currency` | Link Currency | | | Cross-company money (4.7) |

### 3.3 Period presets

`period` is a Select whose change handler sets From and To in the **station's time zone** (or the company's when no station is chosen).

| Preset | From | To |
|---|---|---|
| Today | Today | Today |
| Yesterday | Yesterday | Yesterday |
| This week | Monday of this week | Today |
| Last week | Monday of last week | Sunday of last week |
| Month to date | 1st of this month | Today |
| Last month | 1st of last month | Last day of last month |
| Quarter to date | First day of the quarter | Today |
| Last quarter | | |
| Year to date | First day of the fiscal year | Today |
| Last 7 days, Last 30 days, Last 90 days | Today − n + 1 | Today |
| Custom | User sets From and To | |

Fiscal year boundaries come from ERPNext's Fiscal Year of the company.

### 3.4 Comparisons

| Compare with | Meaning | Columns added |
|---|---|---|
| Previous period | Same length immediately before (MTD of last month for MTD; last week for this week) | *Prior*, *Change*, *Change %* for each measure the report marks comparable |
| Same period last year | Same dates one year earlier | Same |
| Network average | The average per station of the same measure across permitted stations (per-station reports only) | *Network avg*, *vs network %* |

Rules: comparisons apply only to measures (litres, amounts, counts, rates), never to balances. *Change %* is blank when the prior value is zero. A period that contains days before a station's first shift shows *n/a* for the prior.

### 3.5 Dependent filters and validation

- Each Link filter's `get_query` uses the filters above it (station group → station → tank → …).
- Changing a scope filter clears the dependent filters below it.
- From after To, a range longer than the report's limit (section 28), or a missing mandatory filter shows a coded message in the filter area: **FMS-R801** *From date must be on or before To date*, **FMS-R802** *This report can cover at most 366 days; use a prepared report for longer ranges*, **FMS-R803** *Choose a company: this report shows money*. (New range FMS-R8xx, section 33 Q-01.)

### 3.6 Saved filter sets

Users save frequently used filters with the native **Save As** of query reports (a custom report keeping the filters and column choices). Standard saved sets shipped as fixtures:

| Report | Saved set |
|---|---|
| WET-03 Wetstock Variance | *Outside tolerance, last 30 days* |
| PAY-03 Mobile Money Register | *Unmatched, last 7 days* |
| CSH-02 Cashier Performance | *Top 10 shortages, this month* |
| CTL-01 Exception Register | *Unapproved, this week* |

*To verify in FMS-R02:* the v16 behaviour of Save As for Script Reports and whether saved sets can ship as fixtures.

---

## 4. The totals and summary framework

### 4.1 Totals profiles

Every report declares one profile. The profile decides how its total row, group rows and summary cards are computed.

| Profile | Use | Total row | Group rows | Rates and percentages |
|---|---|---|---|---|
| **T-ADD** (additive) | Sales, volumes, counts, collections | Sum of every measure | Sums | None in the report |
| **T-WTD** (weighted) | Reports with averages, rates and percentages next to sums | Sum of additive measures; **rates recomputed from the summed numerator and denominator** | Same rule | Weighted, never averaged |
| **T-BAL** (statement) | Running balances: cashier statement, tank movement, customer statement | No sum of balances; **Opening** row first, **Closing** row last; movements summed | Opening and closing per group | |
| **T-RANK** (ranking) | Rankings and scorecards | No total row; network average row instead | | |
| **T-REG** (register) | Lists of documents | Count and additive amounts only | Optional | |
| **T-PIVOT** | Matrices | Row totals, column totals and grand total | | Share % recomputed from totals |

### 4.2 Weighted calculations

| Measure | Correct total | Wrong (never) |
|---|---|---|
| Average price | Σ amount ÷ Σ litres | Average of row prices |
| Variance % | Σ variance_l ÷ Σ sales_l × 100 | Sum or average of row % |
| Delivery variance % | Σ delivery_variance_l ÷ Σ invoiced_l × 100 | |
| Margin per litre | Σ gross margin ÷ Σ litres | |
| Payment share % | Σ amount of the type ÷ Σ amount × 100 | |
| Shortage per 1,000 L | Σ shortage ÷ Σ litres × 1,000 | |
| Fuel efficiency (L/100 km) | Σ litres ÷ Σ km × 100 | |
| Days of cover | Stock ÷ average daily sales over the stated window | |

### 4.3 Grouping

| Feature | Rule |
|---|---|
| Group by, Then by | Up to two levels. Group rows are tree parents (`indent` 0, then 1), detail rows below them. Uses the report's tree setting (`tree`, `parent_field`, `initial_depth` in the report JS). |
| Default grouping | The one most users need; the report is useful with defaults |
| Fixed grouping | Statements and reconciliations (T-BAL) |
| Collapsed by default | When a report has more than 200 detail rows, groups open collapsed (`initial_depth` 0) |
| Group labels | The group value plus a count: *PMS (42 shifts)* |

### 4.4 The total row

| Rule | Detail |
|---|---|
| When | T-ADD, T-WTD, T-REG and T-PIVOT reports, unless the filters make a total meaningless (a single row, or mixed currencies) |
| How | The report returns the total itself (computed in Python with the profile's rules) and sets `skip_total_row` so the grid's automatic total is not added. The grid's automatic total sums every numeric column, including rates. **To verify in FMS-R02:** whether v16 offers a per-column opt-out; if it does, additive-only reports may use the automatic total. |
| Position | The returned total row is the last row and is excluded from sorting by marking it (`is_total_row`); *to verify* sorting behaviour, otherwise totals go in the summary cards and group rows only |
| Style | Bold, labelled *Total* |
| Blank cells | Columns with no meaningful total (names, dates, balances in T-WTD) stay blank |

### 4.5 Summary cards

Script Reports return `report_summary`: at most **four** cards with the headline answers, each with an indicator.

| Card rule | Detail |
|---|---|
| Content | The figures the report exists for: litres, amount, variance %, exceptions count |
| Indicator | Green good, orange attention, red bad, blue neutral (UI/UX guide 16) |
| Comparison | When *Compare with* is set, cards show the change: *1,240,500 L (+4.2%)* |
| Datatype | Currency, Float, Int or Percent, so they format like the columns |

### 4.6 Footnotes

The report `message` (shown above the grid) carries footnotes that change how numbers should be read:

- **Attributed basis:** *32% of the payment-type figures are attributed, not measured (fms.md 10.4).* Shown whenever Attributed rows are included.
- **Correction history included:** *Superseded rows are shown and excluded from totals.*
- **Partial period:** *The station opened on 2026-10-12; earlier days have no data.*
- **Mixed currencies:** section 4.7.

### 4.7 Currencies across companies

Each company has its own currency (fms.md 7.5, 13). Money is never summed across currencies.

| Situation | Behaviour |
|---|---|
| One company, or companies with one currency | Normal totals |
| Several currencies, no presentation currency | Grouped by currency automatically; one total per currency; grand total blank; footnote |
| Presentation currency chosen | Amounts converted at the exchange rate on each posting date (ERPNext Currency Exchange); footnote names the source of rates |

### 4.8 Rounding and units

| Quantity | Display | Calculation |
|---|---|---|
| Litres | 2 decimals, *(L)* in the label | Full precision; round only for display |
| Money | Company currency precision | Full precision |
| Percentages | 1 decimal (variance % 2 decimals when below 1%) | |
| Meter readings | As recorded (meter precision) | |
| Counts | Integer | |

**[Open] Q-04:** final decimal precision rules (UI/UX guide Q-12).

---

## 5. Presentation standards

### 5.1 Columns

| Rule | Detail |
|---|---|
| Order | Identity (date, shift, station, equipment, person) → measures → rates → flags → links |
| Links | Columns that name a document or master use Link fieldtype, so a click opens it |
| Width | Names 160, codes 100, measures 110, flags 90 |
| Labels | Unit in brackets: *Variance (L)*, *Amount (KES)* only when currencies mix; otherwise the currency is implied |
| Negative values | Shown with a minus sign; red only for losses and shortages (variance, difference) |
| Flags | A word: *Outside*, *Approved*, *Gap*, *Superseded*; coloured by the report formatter, never colour alone |
| Hidden by default | Rarely used columns are available through *Pick columns* but not shown |

### 5.2 Conditional formatting

Done in the report JS `formatter`, with these meanings only (UI/UX guide 16):

| Condition | Style |
|---|---|
| Loss or shortage beyond tolerance | Red text |
| Outside tolerance with a reason, or attention | Orange text |
| Within tolerance | Normal text (no green on every row; green only in summary cards) |
| Superseded rows (history view) | Grey, struck through |
| Total and group rows | Bold |

### 5.3 Charts

| Data | Chart |
|---|---|
| Trend over time | Line |
| Comparison across stations, tanks, cashiers | Bar, sorted descending |
| Composition (≤ 5 parts) | Donut |
| Variance against tolerance | Line with the tolerance band as a second series |
| Two measures over time | Two separate lines on one chart only when the units match |

A chart is returned only when it helps (most registers have none). Charts follow the active filters and grouping.

### 5.4 Print, PDF, export

- Every report prints on A4 landscape with the filters as a header and the generation time and user as a footer (native print with a report print format where the default is not readable).
- Export to Excel and CSV is native; the total row is included and labelled.
- Reports that are signed (SHF-01, SHF-02, SHF-07, CSH-01, CMP-03) have a print format with signature lines.

### 5.5 Drill-down

Every number leads to its source: report row → ledger rows (Report view of the ledger, filtered) → document (shift, GRN, invoice) → the row inside it. Drill-down links are Link columns or a *View detail* column that opens the filtered source report.

---

## 6. Report index

**Freq.** = typical use: D daily, W weekly, M monthly, Q quarterly, A ad hoc. **Prof.** = totals profile (4.1).

| ID | Title | Status | Type | Module | Audience | Freq. | Prof. |
|---|---|---|---|---|---|---|---|
| SHF-01 | Shift Report | Exists | Print | Forecourt Shift | Manager, area manager | D | — |
| SHF-02 | Daily Station Report | Exists (ext.) | Script | Forecourt Shift | Manager, director | D | T-WTD |
| SHF-03 | Shift Summary | Exists (ext.) | Script | Forecourt Shift | Manager, area manager | D, W | T-WTD |
| SHF-04 | Shift Reconciliation | New | Script | Forecourt Shift | Manager, accountant, area manager | D, W | T-ADD |
| SHF-05 | Open Items | Exists | Script | Forecourt Shift | Manager, accountant | D | T-REG |
| SHF-06 | Shift Status and Timeliness | New | Script | Forecourt Shift | Area manager | D, W | T-RANK |
| SHF-07 | Monthly Station Report | New | Script | Forecourt Shift | Manager, director, investor | M | T-WTD |
| SAL-01 | Sales by Product | Exists (ext.) | Script | Forecourt Finance | Manager, accountant | D, M | T-WTD |
| SAL-02 | Sales by Tank | Exists | Script | Wetstock | Manager | W | T-WTD |
| SAL-03 | Sales by Cashier | Exists (ext.) | Script | Forecourt Finance | Manager, area manager | D, W | T-WTD |
| SAL-04 | Payment Mix Matrix | Exists | Script | Forecourt Finance | Accountant, area manager | W, M | T-PIVOT |
| SAL-05 | Sales Mix by Payment Type | Spec | Script | Forecourt Finance | Area manager | W | T-RANK |
| SAL-06 | Sales Trend and Comparison | New | Script | Forecourt Finance | Area manager, director | W, M | T-WTD |
| SAL-07 | Sales by Customer Type | New | Script | Forecourt Finance | Accountant, director | M | T-WTD |
| SAL-08 | Hourly Sales Profile | New (Mode B) | Script | Forecourt Finance | Manager, area manager | W | T-ADD |
| MTR-01 | Meter Movement | New | Script | Wetstock | Manager, area manager | A | T-BAL |
| MTR-02 | Meter Drift | Exists | Script | Wetstock | Area manager | W | T-WTD |
| MTR-03 | Pump and Nozzle Performance | Exists (ext.) | Script | Wetstock | Manager, area manager | W, M | T-WTD |
| MTR-04 | Meter Continuity Exceptions | New | Script | Wetstock | Area manager, auditor | W | T-REG |
| MTR-05 | Pump Test Register | New | Script | Wetstock | Area manager | W | T-ADD |
| WET-01 | Tank Stock Position | Exists | Script | Wetstock | Manager | D | T-ADD |
| WET-02 | Tank Stock Movement | New | Script | Wetstock | Manager, area manager | A, M | T-BAL |
| WET-03 | Wetstock Variance | Exists (ext.) | Script | Wetstock | Area manager | D, W | T-WTD |
| WET-04 | Leak and Loss Indicators | New | Script | Wetstock | Area manager, director | W | T-RANK |
| WET-05 | Water in Tanks | New | Script | Wetstock | Manager, area manager | W | T-REG |
| WET-06 | Spot Dip Register | New | Query | Wetstock | Area manager | W | T-REG |
| WET-07 | Tank Transfer Register | New | Query | Wetstock | Area manager | M | T-REG |
| WET-08 | Wetstock Valuation | New | Script | Wetstock | Accountant | M | T-ADD |
| DLV-01 | Delivery Register | New | Script | Wetstock | Manager, accountant | D, M | T-WTD |
| DLV-02 | Delivery Variance | Exists (ext.) | Script | Wetstock | Area manager | W, M | T-WTD |
| DLV-03 | Delivery Shortage Claims | New | Script | Wetstock | Accountant | W | T-REG |
| DLV-04 | Supplier and Transporter Performance | New | Script | Wetstock | Area manager, director | M, Q | T-RANK |
| PRC-01 | Price History | New | Script | Forecourt Shift | Area manager, accountant | A | T-REG |
| PRC-02 | Price Change Compliance | New | Script | Forecourt Shift | Area manager, auditor | W | T-REG |
| PRC-03 | Fuel Margin | New | Script | Forecourt Finance | Accountant, director | M | T-WTD |
| PRC-04 | Realised Margin after Losses | New | Script | Forecourt Finance | Director | M | T-WTD |
| PRC-05 | Purchase Cost Trend | New | Script | Forecourt Finance | Accountant, director | M | T-WTD |
| CSH-01 | Cashier Statement | Exists | Script | Forecourt Finance | Cashier (own), manager, accountant | W, M | T-BAL |
| CSH-02 | Cashier Performance | Exists (ext.) | Script | Forecourt Finance | Area manager | W, M | T-RANK |
| CSH-03 | Cash Collection | New | Script | Forecourt Finance | Manager, accountant | D | T-ADD |
| CSH-04 | Cash Position by Station | Exists | Script | Forecourt Finance | Accountant, director | D | T-ADD |
| CSH-05 | Banking Register | New | Script | Forecourt Finance | Accountant | D, W | T-REG |
| CSH-06 | Shortage Recovery | New | Script | Forecourt Finance | Accountant, manager | M | T-BAL |
| CSH-07 | Cash Count by Currency | New | Script | Forecourt Finance | Accountant | D | T-ADD |
| PAY-01 | Payment Reconciliation | New | Script | Forecourt Integrations | Accountant | D | T-ADD |
| PAY-02 | Clearing Account Ageing | Exists | Script | Forecourt Finance | Accountant | D, W | T-ADD |
| PAY-03 | Mobile Money Register | New | Script | Forecourt Integrations | Accountant, manager | D | T-REG |
| PAY-04 | Card Settlement | New | Script | Forecourt Integrations | Accountant | D, W | T-ADD |
| PAY-05 | Payment Import Log | New | Query | Forecourt Integrations | Manager, accountant | A | T-REG |
| PAY-06 | Debt Receipts Register | New | Script | Forecourt Finance | Accountant | W | T-REG |
| CRD-01 | Credit Slips Register | Exists (ext.) | Query | Forecourt Finance | Accountant, manager | D, M | T-REG |
| CRD-02 | Customer Fuel Statement | New | Script | Forecourt Finance | Accountant (to customers) | M | T-BAL |
| CRD-03 | Fleet Vehicle Consumption | New | Script | Forecourt Finance | Accountant, fleet customers | M | T-WTD |
| CRD-04 | Credit Limits and Over-limit Sales | New | Script | Forecourt Finance | Accountant, area manager | W | T-REG |
| CRD-05 | Unbilled Credit Deliveries | New | Script | Forecourt Finance | Accountant | M | T-ADD |
| CRD-06 | Accounts Receivable | ERPNext | Native | Accounts | Accountant | D, M | — |
| PUR-01 | Fuel Purchase Register | New | Script | Forecourt Finance | Accountant | M | T-WTD |
| PUR-02 | Receipts Awaiting Supplier Invoice | New | Script | Forecourt Finance | Accountant | W | T-ADD |
| PUR-03 | Supplier Advances | New | Script | Forecourt Finance | Accountant | W | T-BAL |
| PUR-04 | Accounts Payable | ERPNext | Native | Accounts | Accountant | W | — |
| PUR-05 | Landed Cost Summary | New | Script | Forecourt Finance | Accountant | M | T-WTD |
| DRY-01 to DRY-08 | Shop and lubricants (8 reports) | P | Script | Wetstock, Forecourt Finance | Manager, area manager | D to M | various |
| LPG-01 | LPG Cylinder Reconciliation | P | Script | Wetstock | Manager | W | T-BAL |
| SRV-01 to SRV-03 | Services (3 reports) | P | Script | Forecourt Services | Manager, area manager | W | various |
| EXP-01 | Station Expense Register | New | Script | Forecourt Finance | Accountant, area manager | W, M | T-REG |
| EXP-02 | Expense Trend | New | Script | Forecourt Finance | Area manager, director | M | T-WTD |
| EXP-03 | Fuel Own Use Register | New | Script | Wetstock | Area manager, accountant | M | T-ADD |
| STF-01 | Shifts Worked by Employee | New | Script | Forecourt Shift | Manager, HR | M | T-ADD |
| STF-02 | Staff Productivity | New | Script | Forecourt Finance | Area manager | M | T-RANK |
| CTL-01 | Exception Register | Exists (ext.) | Script | Forecourt Shift | Area manager, auditor | D, W | T-REG |
| CTL-02 | Approvals Log | New | Script | Forecourt Shift | Area manager, director, auditor | W, M | T-REG |
| CTL-03 | Corrections Register | New | Script | Forecourt Shift | Director, auditor | M | T-REG |
| CTL-04 | Back-dated and Late Postings | New | Script | Forecourt Shift | Auditor, accountant | W | T-REG |
| CTL-05 | Variance Reason Analysis | New | Script | Forecourt Shift | Area manager | M | T-PIVOT |
| CTL-06 | Control Signals by Cashier | New | Script | Forecourt Finance | Area manager, director | M | T-RANK |
| CTL-07 | Segregation of Duties Check | New | Script | Forecourt Shift | Auditor | M | T-REG |
| CTL-08 | Shift Edit Audit Trail | New | Script | Forecourt Shift | Auditor | A | T-REG |
| EQP-01 | Equipment Register | New | Script | Wetstock | Administrator, area manager | A | T-REG |
| EQP-02 | Meter Change Register | New | Query | Wetstock | Area manager, auditor | M | T-REG |
| EQP-03 | Calibration Chart Register | New | Script | Wetstock | Administrator | M | T-REG |
| EQP-04 | Equipment Health | New | Script | Wetstock | Area manager, administrator | D | T-REG |
| CMP-01 | Sales Tax Summary by Station | New | Script | Forecourt Finance | Accountant | M | T-ADD |
| CMP-02 | Fiscal Submission Status | New | Script | Forecourt Integrations | Accountant | D | T-REG |
| CMP-03 | Regulatory Volume Return | New (country template) | Script | Forecourt Finance | Accountant | M | T-BAL |
| CMP-04 | Regulated Price Compliance | Open | Script | Forecourt Shift | Area manager | M | T-REG |
| FIN-01 | Station Profit and Loss | ERPNext | Native | Accounts | Accountant, director | M | — |
| FIN-02 | Consolidated Financial Statements | ERPNext | Native | Accounts | Director, investor | M, Q | — |
| FIN-03 | Station Comparison | Exists (ext.) | Script | Forecourt Finance | Area manager, director | M | T-RANK |
| FIN-04 | Executive Summary | New | Script | Forecourt Finance | Director | W, M | T-WTD |
| FIN-05 | Investor Statement | New | Script | Forecourt Finance | Investor | M, Q | T-WTD |
| FIN-06 | Station Scorecard | New | Script | Forecourt Finance | Area manager, director | M | T-RANK |
| FCS-01 | Run-out Forecast | Exists (ext.) | Script | Wetstock | Manager, accountant | D | T-REG |
| FCS-02 | Sales Forecast | New | Script | Forecourt Finance | Area manager, director | M | T-ADD |
| INT-01 | FMS Health | Exists | Script | Forecourt Setup | Administrator, area manager | D | T-REG |
| INT-02 | Integration Inbox Log | New | Script | Forecourt Integrations | Administrator | D | T-REG |
| INT-03 to INT-09 | Mode B (7 reports) | P | Script | Forecourt Integrations | Manager, area manager | D, W | various |

**Totals:** 111 reports: 22 built (12 of them extended here), 1 documented but not built, 64 new (including SAL-08, Mode B only, and CMP-03, a country template), 19 proposed with non-fuel and Mode B (P), 4 native ERPNext, 1 open (CMP-04).

---

## How each report is specified

Each report below uses the same card. Filters are written as **M** mandatory, **D** has a default, **O** optional. "Standard scope" means Company, Station group and Station(s) from 3.2 with their defaults.

| Row | Content |
|---|---|
| Answers | The question the report answers |
| Users · use | Audience and frequency |
| Type · source | Report type and main tables |
| Filters | In the order of 3.1 |
| Grouping | Default, and options for *Group by* / *Then by* |
| Columns | In display order; calculated columns show their formula |
| Totals | Profile (4.1) and specific rules |
| Summary | Up to four cards |
| Chart | If any |
| Drill-down | Where a click goes |
| Notes | Edge cases, data gaps, decisions |

---

## 7. Shifts and daily operations (SHF)

### SHF-01 · Shift Report [Exists]

| | |
|---|---|
| Answers | Everything about one shift on one A4 page, for signature and filing |
| Users · use | Manager after every close; area manager on review |
| Type · source | Print Format of Forecourt Shift |
| Content | Header (station, template, date, window, status, prepared by, approved by) · prices and segments · meter readings per nozzle (opening, closing, litres, amount, cashier) · tank reconciliation per tank · credit slips · cashier balances with resolutions · expenses · totals · documents created · signature lines (manager, cashier per cashier, approver) |
| Notes | Must fit one A4 page for the test station (FMS-F17). Corrected shifts print a *Corrected* banner and list corrections on a second page. |

### SHF-02 · Daily Station Report (DSR) [Exists (ext.)]

| | |
|---|---|
| Answers | What happened at a station on one day, all shifts together |
| Users · use | Manager daily; emailed to directors each morning (26) |
| Type · source | Script · Nozzle, Sales, Cashier, Wetstock Ledgers; GL for banking |
| Filters | Company M · Station M (D: user's) · Date M (D: yesterday) |
| Grouping | Fixed sections (below) |
| Sections and columns | **1 Sales by product:** product · litres · amount · avg price · cash · mobile · card · credit · voucher. **2 Shifts:** shift · template · status · litres · amount · cashier difference · tank variance (L). **3 Tanks:** tank · opening · receipts · sales · closing dip · variance (L) · variance % · days of cover. **4 Deliveries:** GRN · supplier · tank · invoiced · received · variance. **5 Cash:** counted · drops · banked · in transit. **6 Exceptions:** count by type with links. |
| Totals | T-WTD per section |
| Summary | Litres · Sales · Total cashier difference · Tank variance % |
| Chart | None (one-page print) |
| Drill-down | Shift and GRN links |
| Notes (ext.) | Adds section 5 (cash) and 6 (exceptions) and the summary cards. Shows *Not closed* for shifts of the day still open, with their status, so missing data is visible. |

### SHF-03 · Shift Summary [Exists (ext.): *Sales by Shift*]

| | |
|---|---|
| Answers | Shift by shift: volume, money, payment mix, problems |
| Users · use | Manager daily; area manager weekly |
| Type · source | Script · Sales, Cashier, Wetstock Ledgers |
| Filters | Standard scope · Period M (D: This week) · Shift template O · Status O · Only exceptions O |
| Grouping | Default: shift. Options: day, week, shift template, station |
| Columns | Shift · Date · Template · Status · Cashiers (count) · Litres · Fuel amount · Shop amount · Cash · Mobile · Card · Credit · Voucher · Expenses · Cashier difference · Tank variance (L) · Tank variance % · Resolutions (count) · Corrected (flag) |
| Totals | T-WTD: amounts and litres summed; tank variance % = Σ variance ÷ Σ sales |
| Summary | Litres · Sales · Cashier difference · Shifts with exceptions |
| Chart | Stacked bar: sales per shift by payment type |
| Drill-down | Shift |

### SHF-04 · Shift Reconciliation [New]

| | |
|---|---|
| Answers | Which shifts did not balance, for whom, and what was done |
| Users · use | Manager, accountant daily; area manager weekly |
| Type · source | Script · Cashier Ledger Entry; Shift Resolution; Journal Entry |
| Filters | Standard scope · Period M (D: Month to date) · Cashier O · Resolution action O (Charge to cashier, Write off, Record excess) · Only with difference D (on) · Minimum amount O · Approved by O |
| Grouping | Fixed: shift, then cashier (tree) |
| Columns | Shift · Cashier · Expected · Cash (net of float) · Mobile · Card · Credit · Voucher · Expenses · Drops · Accounted · Difference · Action · Reason · Approved by · Journal Entry |
| Calculations | Accounted = cash + mobile + card + credit + voucher + expenses + drops (fms.md 7.2) |
| Totals | T-ADD |
| Summary | Shortages · Excesses · Written off · Charged to cashiers |
| Drill-down | Shift (Cashiers tab), Journal Entry |

### SHF-05 · Open Items [Exists]

| | |
|---|---|
| Answers | What is unfinished: the station's to-do list |
| Users · use | Manager and accountant daily |
| Type · source | Script · Forecourt Shift (drafts), Purchase Receipt (drafts, no invoice), Payment Feed Entry (unmatched), GL (unbanked cash) |
| Filters | Standard scope · Item type O (Draft shift, Draft GRN, GRN without invoice, Unmatched payment, Unbanked cash, Draft own use, Pending approval) · Older than (days) O |
| Grouping | Fixed: item type |
| Columns | Type · Document · Station · Date · Age (days) · Amount or litres · Waiting for (role) · Action |
| Totals | T-REG: count and amount per type |
| Summary | Open items · Oldest (days) · Unbanked cash · Unmatched payments |

### SHF-06 · Shift Status and Timeliness [New]

| | |
|---|---|
| Answers | Did every station close every shift, and how fast? |
| Users · use | Area manager daily and weekly |
| Type · source | Script · Forecourt Shift, Forecourt Shift Template; Version (submit time) |
| Filters | Standard scope (multi stations) · Period M (D: Last 7 days) · Only late or missing O |
| Grouping | Default: station, then day |
| Columns | Station · Date · Template · Expected end · Status · Closed at · Hours to close · Prepared by · Approval wait (hours) · Missing (flag) |
| Calculations | Hours to close = closed at − shift end. Missing = a template slot with no shift. |
| Totals | T-RANK: per station average hours to close, count late, count missing; network average row |
| Summary | Shifts expected · Closed · Missing · Average hours to close |
| Notes | "Closed at" needs the submit time: read from Version until a `closed_at` field exists (section 30, gap G-03). The threshold for *late* is a report filter, default 12 hours, **[Open] Q-05**. |

### SHF-07 · Monthly Station Report [New]

| | |
|---|---|
| Answers | A month at a station, day by day, on one page: the monthly companion of the DSR |
| Users · use | Manager, director, investor monthly; signed copy for the file |
| Type · source | Script · ledgers, GL |
| Filters | Company M · Station M · Month M (D: last month) |
| Grouping | Fixed: day rows |
| Columns | Day · Litres per product (one column each) · Total litres · Sales · Cash · Mobile · Card · Credit · Deliveries (L) · Tank variance (L) · Variance % · Cashier difference · Expenses |
| Totals | T-WTD; variance % weighted |
| Summary | Litres · Sales · Variance % · Cashier difference |
| Chart | Line: litres per day by product |

---

## 8. Fuel sales and volume (SAL)

### SAL-01 · Sales by Product [Exists (ext.)]

| | |
|---|---|
| Answers | How much of each product was sold, and how it was paid |
| Users · use | Manager daily; accountant monthly |
| Type · source | Script · Sales Ledger Entry |
| Filters | Standard scope · Period M (D: Month to date) · Compare with O · Granularity O · Item group O · Products O · Fuel only D (on) · Payment types O · Basis O · Customer O |
| Grouping | Default: product. Options: station, day, week, month, shift template, payment type, cashier |
| Columns | Group · Litres or quantity · Amount · Avg price · Cash · Mobile · Card · Credit · Voucher · Attributed share % · (comparison: Prior, Change, Change %) |
| Calculations | Avg price = amount ÷ litres; Attributed share = Attributed amount ÷ amount |
| Totals | T-WTD |
| Summary | Litres · Amount · Avg price · Change % (when comparing) |
| Chart | Bar by group; line when grouped by time |
| Drill-down | Sales Ledger rows (Report view) → shift |
| Notes | Footnote on attributed share (4.6) |

### SAL-02 · Sales by Tank [Exists]

| | |
|---|---|
| Answers | Litres dispensed from each tank, next to its receipts and variance |
| Type · source | Script · Sales and Wetstock Ledgers |
| Filters | Standard scope · Period M (D: Month to date) · Tank O · Products O |
| Grouping | Default: tank. Options: day, week, month |
| Columns | Tank · Product · Litres sold · Amount · Cash · Mobile · Card · Credit · Receipts (L) · Variance (L) · Variance % |
| Totals | T-WTD |
| Chart | Bar: litres by tank |

### SAL-03 · Sales by Cashier [Exists (ext.)]

| | |
|---|---|
| Answers | What each cashier sold and collected |
| Users · use | Manager daily; area manager weekly |
| Type · source | Script · Sales and Cashier Ledgers |
| Filters | Standard scope · Period M (D: This week) · Cashier O · Products O · Payment types O · Compare with O (Network average) |
| Grouping | Default: cashier. Options: cashier then product, cashier then payment type, cashier then shift |
| Columns | Cashier · Shifts · Litres · Fuel amount · Shop amount · Cash · Mobile · Card · Credit · Mobile share % · Difference · Shortages (count) |
| Totals | T-WTD |
| Summary | Litres · Sales · Mobile share % · Total difference |
| Notes (ext.) | Mobile share and network average column; these feed CTL-06 |

### SAL-04 · Payment Mix Matrix [Exists]

| | |
|---|---|
| Answers | Any two dimensions against each other: product × payment type, nozzle × payment type, shift × payment type |
| Type · source | Script (pivot) · Sales Ledger Entry |
| Filters | Standard scope · Period M · Rows M (D: Product) · Columns M (D: Payment type) · Measure D (Amount; Litres) · Show as D (Values; Row %; Column %) · Basis O |
| Totals | T-PIVOT: row and column totals; shares recomputed |
| Notes | Basis shown per cell in the tooltip; footnote |

### SAL-05 · Sales Mix by Payment Type [Spec] (fms.md 11.3)

| | |
|---|---|
| Answers | Is any station or cashier unusual in how customers pay? |
| Users · use | Area manager weekly |
| Type · source | Script · Sales Ledger Entry |
| Filters | Standard scope (multi) · Period M (D: Last 30 days) · Level D (Station; Cashier) |
| Columns | Station or cashier · Sales · Cash % · Mobile % · Card % · Credit % · Network mobile % · Deviation (points) · Flag |
| Totals | T-RANK; network average row |
| Notes | A cashier with far less mobile money than colleagues may be redirecting payments (fms.md 7.4). Flag threshold is a filter (D: 15 points) **[Open] Q-06**. |

### SAL-06 · Sales Trend and Comparison [New]

| | |
|---|---|
| Answers | Are we growing? Compared with last period, last year and other stations |
| Users · use | Area manager, director weekly and monthly |
| Type · source | Script · Sales and Nozzle Ledgers |
| Filters | Standard scope (multi) · Period M (D: Last 90 days) · Granularity D (Week) · Compare with D (Same period last year) · Products O · Measure D (Litres; Amount) |
| Grouping | Default: period. Options: station, product |
| Columns | Period · Measure · Prior · Change · Change % · Average per day · Days with data |
| Calculations | Average per day = measure ÷ days with closed shifts (not calendar days, so a missing day does not look like a drop) |
| Totals | T-WTD |
| Chart | Line: current against prior |

### SAL-07 · Sales by Customer Type [New]

| | |
|---|---|
| Answers | How much of the business is walk-in, credit fleets, vouchers, and (later) loyalty |
| Type · source | Script · Sales Ledger Entry, Customer |
| Filters | Standard scope · Period M (D: Last month) · Customer group O · Products O |
| Grouping | Default: customer type (Walk-in, Credit, Voucher). Options: customer group, customer, station |
| Columns | Type or customer · Litres · Amount · Share % · Avg price · Customers (count) |
| Totals | T-WTD |
| Chart | Donut by type |

### SAL-08 · Hourly Sales Profile [New, Mode B only]

| | |
|---|---|
| Answers | When during the day do we sell? For staffing and deliveries |
| Type · source | Script · FCC Transaction or Sales Invoice posting time (Mode B) |
| Filters | Standard scope · Period M (D: Last 30 days) · Day of week O · Products O |
| Grouping | Fixed: hour of day; option day of week × hour |
| Columns | Hour · Transactions · Litres · Amount · Average litres per transaction |
| Chart | Bar by hour |
| Notes | **Not possible in Mode A**: meters are read per shift, so there is no time within the shift (gap G-02). Hidden from stations without transaction capture. |

---

## 9. Meters, pumps and nozzles (MTR)

### MTR-01 · Meter Movement [New]

| | |
|---|---|
| Answers | The history of a nozzle's meters, shift after shift |
| Users · use | Manager when checking a reading; area manager in investigations |
| Type · source | Script · Nozzle Ledger Entry (including Meter Change rows) |
| Filters | Company O · Station M · Pump O · Nozzle O · Period M (D: Last 30 days) · Meter D (Basis; E-cash; E-vol; Manual; All) · Cashier O · Include correction history O |
| Grouping | Fixed: nozzle, then shift in time order |
| Columns | Date · Shift · Segment · Cashier · Opening · Closing · Gross (L) · Test (L) · Own use (L) · Net (L) · Price · Amount · Drift (L) · Event · Source |
| Calculations | Event = *Meter change*, *Rollover*, *Correction*, *Gap* (opening ≠ previous closing) |
| Totals | T-BAL: first opening, last closing per nozzle; litres and amounts summed |
| Summary | Net litres · Test litres · Gaps · Meter changes |
| Chart | Line: net litres per shift (one nozzle selected) |
| Drill-down | Shift (Meters tab), Meter Change |
| Entry points | Meter row *History* on the shift (UI/UX guide 10.2.3); Nozzle form *View* |

### MTR-02 · Meter Drift [Exists]

| | |
|---|---|
| Answers | Do the meters of each nozzle agree with each other and with tank movement? |
| Type · source | Script · Nozzle Ledger Entry, Wetstock Ledger Entry |
| Filters | Standard scope · Period M (D: Last 30 days) · Pump O · Nozzle O · Drift pair D (All; E-vol vs manual; E-cash vs E-vol; E-cash vs manual) · Only beyond tolerance O |
| Grouping | Default: nozzle. Options: pump, tank, week |
| Columns | Nozzle · Tank · Litres (basis) · Drift E-vol/manual (L) · Drift E-cash/E-vol (L) · Drift E-cash/manual (L) · Drift % · Shifts beyond tolerance · Reasons given |
| Totals | T-WTD: drift % = Σ drift ÷ Σ litres |
| Chart | Line: drift % by week per nozzle |
| Notes | Stations that record only the E-cash meter have no meter-pair drift; the report then shows nozzle volume against tank movement only |

### MTR-03 · Pump and Nozzle Performance [Exists (ext.): *Sales by Pump and Nozzle*]

| | |
|---|---|
| Answers | Which dispensers and nozzles sell, which sit idle, and which misbehave |
| Users · use | Manager, area manager weekly and monthly |
| Type · source | Script · Nozzle and Sales Ledgers; Meter Change |
| Filters | Standard scope · Period M (D: Last 30 days) · Island O · Pump O · Products O · Show zero rows D (on) |
| Grouping | Default: island, then pump, then nozzle (tree). Options: product |
| Columns | Island · Pump · Nozzle · Product · Litres · Amount · Share of station % · Shifts with zero sales · Test litres · Drift % · Meter changes · Cash · Mobile · Card · Credit |
| Totals | T-WTD |
| Summary | Litres · Idle nozzles · Nozzles with drift · Meter changes |
| Chart | Bar: litres by nozzle |
| Notes (ext.) | Idle, test, drift and meter change columns added |

### MTR-04 · Meter Continuity Exceptions [New]

| | |
|---|---|
| Answers | Where did the chain of readings break? |
| Users · use | Area manager, auditor weekly |
| Type · source | Script · Nozzle Ledger Entry, Meter Change, Shift Correction |
| Filters | Standard scope · Period M (D: Last 30 days) · Type O (Gap, Rollover, Meter change, Manual adjustment, Correction) |
| Columns | Date · Station · Nozzle · Shift · Previous closing · This opening · Difference · Type · Explained by (document) · Flag |
| Totals | T-REG: count by type |
| Notes | A gap with no Meter Change or correction is the most serious: it should be impossible after FMS-S102 and is shown in red |

### MTR-05 · Pump Test Register [New]

| | |
|---|---|
| Answers | How much fuel was "tested" and poured back, by whom and where |
| Users · use | Area manager weekly |
| Type · source | Script · Nozzle Ledger Entry (`test_l`) |
| Filters | Standard scope · Period M (D: Last 30 days) · Nozzle O · Cashier O · Only above limit O |
| Grouping | Default: nozzle. Options: cashier, station |
| Columns | Nozzle · Cashier · Shifts · Test litres · Litres sold · Test % of sales · Nozzle limit (L per shift) · Shifts above limit |
| Totals | T-WTD |
| Notes | Abuse of test volumes hides sales (fms.md 7.4) |

---

## 10. Wetstock and tanks (WET)

### WET-01 · Tank Stock Position [Exists]

| | |
|---|---|
| Answers | How much fuel is in each tank now, and how long will it last? |
| Users · use | Manager daily before ordering |
| Type · source | Script · Stock Ledger Entry (tank warehouses), Wetstock Ledger Entry, Fuel Tank |
| Filters | Standard scope (multi) · As at M (D: now) · Products O · Only below reorder O |
| Grouping | Default: station, then tank |
| Columns | Station · Tank · Product · Capacity · Safe fill · Book stock · Last dip · Last dip at · Ullage (safe fill − book) · Reorder level · Average daily sales (last 14 days) · Days of cover · Stock value · Flag (*Below reorder*, *Above capacity*, *Negative*) |
| Totals | T-ADD per product (litres, value); no total of days of cover |
| Summary | Stock (L) · Stock value · Tanks below reorder · Lowest days of cover |
| Chart | Bar: fill % by tank |
| Notes | The averaging window for days of cover is a filter (D: 14 days) |

### WET-02 · Tank Stock Movement [New]

| | |
|---|---|
| Answers | A tank's statement: opening, every movement, closing, variance |
| Users · use | Manager, area manager on investigation and month end |
| Type · source | Script · Wetstock Ledger Entry |
| Filters | Company O · Station M · Tank O · Period M (D: Month to date) · Granularity D (Shift; Day) · Include correction history O |
| Grouping | Fixed: tank, then period |
| Columns | Period · Shift · Opening · Receipts · Sales · Test · Own use · Transfers · Expected · Dip · Variance (L) · Variance % · Cumulative variance (L) · Cumulative variance % · Within tolerance · Reason · Approved by · Delivery |
| Calculations | Cumulative variance % = running Σ variance ÷ running Σ sales |
| Totals | T-BAL: opening first, closing last; movements and variance summed; variance % weighted |
| Summary | Receipts · Sales · Variance (L) · Cumulative variance % |
| Chart | Line: cumulative variance % with the tolerance band (± cumulative tolerance, fms.md 5.6) |
| Drill-down | Shift (Tanks tab), GRN, transfer |

### WET-03 · Wetstock Variance [Exists (ext.)]

| | |
|---|---|
| Answers | How much fuel are we losing, where, and is it within tolerance? |
| Users · use | Area manager daily and weekly; director monthly |
| Type · source | Script · Wetstock Ledger Entry |
| Filters | Standard scope (multi) · Period M (D: Last 30 days) · Compare with O · Products O · Tank O · Reason O · Only exceptions O · Minimum variance % O |
| Grouping | Default: station, then tank. Options: product, week, month, reason |
| Columns | Group · Sales (L) · Variance (L) · Variance % · Variance value · Shifts · Within tolerance · Outside tolerance · Approved · Largest single variance (L) · Cumulative 30-day % · Flag |
| Totals | T-WTD |
| Summary | Variance (L) · Variance % · Variance value · Shifts outside tolerance |
| Chart | Bar: variance % by group, tolerance line |
| Notes (ext.) | Variance value and cumulative columns; the "wetstock reconciliation" report of the brief |

### WET-04 · Leak and Loss Indicators [New]

| | |
|---|---|
| Answers | Which tanks show a pattern that could mean a leak, theft or a measurement problem? |
| Users · use | Area manager weekly; director monthly |
| Type · source | Script · Wetstock Ledger Entry, Nozzle Ledger Entry |
| Filters | Standard scope (multi) · Window D (30 days) · Products O |
| Columns | Station · Tank · Variance % (window) · Cumulative tolerance · Consecutive loss shifts · Loss shifts % · Variance at night vs day shifts · Variance after deliveries · Trend (L per week) · Signals (count) · Signals (list) |
| Calculations | Signals: cumulative % beyond tolerance; more than *n* consecutive loss shifts (filter, D 5); loss shifts above 70% of shifts; losses concentrated on one shift template; a steady negative trend |
| Totals | T-RANK by signals, then variance % |
| Notes | The report shows **signals**, not conclusions. Thresholds are filters with defaults; the defaults are **[Open] Q-07** for the owner and the area managers. Statistical methods (regression of dip against meter volume) are possible later on the same data. |

### WET-05 · Water in Tanks [New]

| | |
|---|---|
| Answers | Which tanks have water, and is it rising? |
| Users · use | Manager, area manager weekly |
| Type · source | Script · Shift Tank Dip and Tank Dip (`water_mm`, `water_l`) of submitted documents |
| Filters | Standard scope · Period M (D: Last 30 days) · Tank O · Only with water D (on) |
| Columns | Date · Station · Tank · Product · Water (mm) · Water (L) · Change since previous dip · Source document |
| Totals | T-REG |
| Chart | Line: water (L) per tank |
| Notes | Water is not in the Wetstock Ledger (gap G-01); the report reads the dip documents. No threshold is defined in the specs (UI/UX guide Q-05). |

### WET-06 · Spot Dip Register [New]

| | |
|---|---|
| Answers | Every spot dip, and what it showed against the book |
| Type · source | Query · Tank Dip (submitted) |
| Filters | Standard scope · Period M (D: Last 30 days) · Tank O · Purpose O · Dipped by O |
| Columns | Dipped at · Station · Tank · Purpose · Dip (mm) · Volume (L) · Book (L) · Difference (L) · Difference % · Dipped by · Witness |
| Totals | T-REG |

### WET-07 · Tank Transfer Register [New]

| | |
|---|---|
| Type · source | Query · Tank Transfer (submitted), Stock Entry |
| Filters | Standard scope · Period M (D: Last month) · Tank O |
| Columns | Transferred at · From tank · To tank · Product · Litres · Reason · Stock Entry · Prepared by · Approved by |
| Totals | T-REG: litres |

### WET-08 · Wetstock Valuation [New]

| | |
|---|---|
| Answers | What is the fuel worth, and what did losses cost? |
| Users · use | Accountant monthly |
| Type · source | Script · Stock Ledger Entry, Wetstock Ledger Entry (`variance_value`) |
| Filters | Company M · Station group O · Stations O · As at M (D: end of last month) · Products O |
| Grouping | Default: station, then product |
| Columns | Station · Product · Book stock (L) · Valuation rate · Stock value · Variance this month (L) · Variance value this month · Own use value · Delivery shortage value |
| Totals | T-ADD; valuation rate weighted |
| Notes | Equals the stock balance in ERPNext for tank warehouses (test in 29) |

---

## 11. Deliveries (DLV)

### DLV-01 · Delivery Register [New]

| | |
|---|---|
| Answers | Every fuel delivery with its paperwork and dips |
| Users · use | Manager on each delivery; accountant monthly |
| Type · source | Script · Purchase Receipt (Fuel Delivery fields), GRN Delivery Dip, Wetstock Ledger Entry (Delivery) |
| Filters | Standard scope · Period M (D: Month to date) · Supplier O · Transporter O · Driver O · Products O · Status O (Draft, Submitted, Invoiced) · Only beyond tolerance O |
| Grouping | Default: none (list). Options: supplier, transporter, tank, week |
| Columns | Received at · GRN · Supplier · Delivery note no. · Truck · Driver · Transporter · Seals · Tank · Product · Invoiced (L) · Dip before · Dip after · Sales during drop (L) · Received (L) · Variance (L) · Variance % · Reason · Shortage entry · Purchase Order · Purchase Invoice |
| Totals | T-WTD: variance % = Σ variance ÷ Σ invoiced |
| Summary | Deliveries · Invoiced (L) · Received (L) · Variance % |
| Drill-down | GRN, Purchase Invoice |

### DLV-02 · Delivery Variance [Exists (ext.)]

| | |
|---|---|
| Answers | Who delivers short? |
| Users · use | Area manager weekly; director monthly |
| Type · source | Script · Wetstock Ledger Entry (Delivery) |
| Filters | Standard scope (multi) · Period M (D: Last 90 days) · Supplier O · Transporter O · Driver O · Products O |
| Grouping | Default: supplier. Options: transporter, driver, station, month |
| Columns | Group · Deliveries · Invoiced (L) · Received (L) · Variance (L) · Variance % · Deliveries beyond tolerance · Largest shortage (L) · Shortage value · Claimed (L) |
| Totals | T-WTD |
| Chart | Bar: variance % by group with the tolerance line |

### DLV-03 · Delivery Shortage Claims [New]

| | |
|---|---|
| Answers | Which shortages were claimed, and were they recovered? |
| Users · use | Accountant weekly |
| Type · source | Script · Stock Entry (from *Record delivery shortage*), Debit Note (Purchase Invoice return), Journal Entry against transporters |
| Filters | Company M · Station O · Period M (D: Last 90 days) · Supplier O · Transporter O · Status O (Not claimed, Claimed, Recovered) |
| Columns | GRN · Date · Supplier · Transporter · Tank · Shortage (L) · Value · Stock Entry · Claim document · Claim amount · Recovered · Outstanding · Age (days) |
| Totals | T-REG |
| Summary | Shortage value · Claimed · Recovered · Outstanding |

### DLV-04 · Supplier and Transporter Performance [New]

| | |
|---|---|
| Answers | Which suppliers and transporters to keep |
| Users · use | Area manager, director monthly and quarterly |
| Type · source | Script · Wetstock Ledger Entry (Delivery), Purchase Order, Purchase Receipt, Purchase Invoice |
| Filters | Company M · Station group O · Period M (D: Last quarter) · Level D (Supplier; Transporter; Driver) |
| Columns | Name · Deliveries · Litres received · Variance % · Deliveries beyond tolerance % · Shortage value · Recovered % · Average days PO to GRN · Average cost per litre · Price difference vs PO (when POs exist) |
| Totals | T-RANK, with an all-suppliers row |
| Notes | "Days PO to GRN" only where Purchase Orders are used (they are optional, fms.md 8.3) |

---

## 12. Prices, costs and margins (PRC)

**Revenue for margins.** Margin reports use **net revenue** (income account amount, excluding tax) from the GL or Sales Invoice items, not the Sales Ledger `amount`, because the specs do not state whether the Sales Ledger stores tax-inclusive pump amounts (gap G-04, **[Open] Q-08**). Cost of goods sold comes from the Stock Ledger (`stock_value_difference` of the sales vouchers on tank warehouses), so it follows ERPNext valuation exactly.

### PRC-01 · Price History [New]

| | |
|---|---|
| Answers | What was the price of each product at each station, and when did it change? |
| Users · use | Area manager, accountant on demand |
| Type · source | Script · Fuel Price Change (submitted), Fuel Price Change Item |
| Filters | Standard scope (multi) · Period M (D: Last 90 days) · Products O · Status D (Approved) |
| Columns | Effective at · Station · Product · Old price · New price · Change · Change % · Reason · Reference · Prepared by · Approved by · Approved at · Shift affected |
| Totals | T-REG |
| Chart | Step line: price over time per product |

### PRC-02 · Price Change Compliance [New]

| | |
|---|---|
| Answers | Were price changes applied correctly and on time? |
| Users · use | Area manager, auditor weekly |
| Type · source | Script · Fuel Price Change, Shift Price, Nozzle Ledger Entry, Workflow history |
| Filters | Standard scope · Period M (D: Last 30 days) · Only exceptions D (on) |
| Columns | Price change · Station · Product · Effective at · Approved at · Delay (approved − effective, hours) · Segment created in shift · Change-time readings present · Price cross-check failures (amount ≠ volume × price beyond ±1) · Flag |
| Calculations | Cross-check from the Nozzle Ledger: amount − net litres × price, per segment (fms.md 5.6 price cross-check) |
| Totals | T-REG: count by flag |
| Notes | A pump still programmed with the old price shows as cross-check failures on its nozzles |

### PRC-03 · Fuel Margin [New]

| | |
|---|---|
| Answers | What gross margin do we make per product, per station, per litre? |
| Users · use | Accountant, director monthly |
| Type · source | Script · GL (income accounts, Station dimension), Stock Ledger Entry (COGS of shift sales vouchers), Nozzle Ledger (litres) |
| Filters | Company M · Station group O · Stations O · Period M (D: Last month) · Compare with O · Products O · Granularity O |
| Grouping | Default: station, then product. Options: product, month |
| Columns | Group · Litres · Net revenue · COGS · Gross margin · Margin % · Margin per litre · Avg net selling price · Avg cost per litre |
| Totals | T-WTD: per-litre and % recomputed |
| Summary | Gross margin · Margin per litre · Margin % · Litres |
| Chart | Bar: margin per litre by station |
| Notes | Credit sales and walk-in are both included; debt receipts are not revenue and are excluded |

### PRC-04 · Realised Margin after Losses [New]

| | |
|---|---|
| Answers | What is left of the margin after wetstock losses, own use and delivery shortages? |
| Users · use | Director monthly |
| Type · source | Script · PRC-03 figures, Wetstock Ledger (`variance_value`), own-use and shortage Stock Entries (GL) |
| Filters | As PRC-03 |
| Columns | Group · Litres · Gross margin · Tank variance cost · Own use cost · Uncovered delivery shortage · Realised margin · Realised per litre · Losses as % of gross margin |
| Totals | T-WTD |
| Chart | Waterfall-style bar: gross margin, then each loss, then realised (shown as stacked bars; Frappe charts have no waterfall) |

### PRC-05 · Purchase Cost Trend [New]

| | |
|---|---|
| Answers | What do we pay per litre, by supplier and over time? |
| Type · source | Script · Purchase Invoice items (fuel), Landed Cost Voucher, Purchase Receipt |
| Filters | Company M · Station O · Period M (D: Last 6 months) · Supplier O · Products O · Granularity D (Month) |
| Columns | Period · Supplier · Product · Litres invoiced · Net cost · Landed costs · Total cost · Cost per litre · Change vs previous period |
| Totals | T-WTD |
| Chart | Line: cost per litre per supplier |

---

## 13. Cash and cashier accountability (CSH)

### CSH-01 · Cashier Statement [Exists]

| | |
|---|---|
| Answers | What does each cashier owe the company, shift by shift? |
| Users · use | Cashier (own statement), manager, accountant weekly and monthly |
| Type · source | Script · Cashier Ledger Entry; GL on *Staff Shortage Receivable* with the Employee party |
| Filters | Company M · Station O · Cashier M (D: own Employee for cashiers) · Period M (D: Month to date) |
| Grouping | Fixed: cashier, then date |
| Columns | Date · Shift · Expected · Accounted · Difference · Action · Charged · Written off · Excess · Recovered (cash or salary) · Balance |
| Totals | T-BAL: opening balance, movements, closing balance |
| Summary | Opening balance · Charged · Recovered · Closing balance |
| Notes | Cashiers see only their own statement (permission query; section 27) |

### CSH-02 · Cashier Performance [Exists (ext.): *Cashier Variance Ranking*]

| | |
|---|---|
| Answers | Which cashiers have problems, and how do they compare? |
| Users · use | Area manager weekly and monthly |
| Type · source | Script · Cashier, Sales, Nozzle and Wetstock Ledgers |
| Filters | Standard scope (multi) · Period M (D: Last 30 days) · Top N O · Minimum shifts D (3) |
| Columns | Cashier · Station · Shifts · Hours on duty · Litres per hour · Shortages (count) · Shortage amount · Shortage per 1,000 L · Excesses (count) · Mobile share % vs station · Test litres per shift · Tank variance on their shifts vs others (L) |
| Totals | T-RANK by shortage amount; station average row |
| Notes (ext.) | Adds the fraud signals of fms.md 7.4. "Attendant performance" from the brief maps here; attendants carry no balance. |

### CSH-03 · Cash Collection [New]

| | |
|---|---|
| Answers | Follow the cash: counted, dropped, banked, still at the station |
| Users · use | Manager, accountant daily |
| Type · source | Script · Cashier Ledger (`cash`, `drops`, `float_amount`), Payment Entry (internal transfers and deposits), GL balances of till, safe and in-transit accounts |
| Filters | Company M · Station D · Period M (D: Last 7 days) · Cashier O |
| Grouping | Fixed: day, then shift |
| Columns | Day · Shift · Cash counted (net of float) · Drops to safe · Banked · Deposit slip · In transit · Safe balance at day end · Days since last banking |
| Totals | T-ADD; balances shown as of the last day only |
| Summary | Cash collected · Banked · Not yet banked · Days since last banking |

### CSH-04 · Cash Position by Station [Exists]

| | |
|---|---|
| Answers | Where is the cash right now? |
| Type · source | Script · GL balances (till, safe, in transit, clearing) by Station dimension |
| Filters | Company M · Station group O · As at M (D: today) |
| Columns | Station · Tills · Safe · In transit · Mobile money clearing · Card clearing · Total |
| Totals | T-ADD |

### CSH-05 · Banking Register [New]

| | |
|---|---|
| Answers | Every deposit to the bank, with its slip and how long the cash waited |
| Type · source | Script · Payment Entry (Internal Transfer from safe or in-transit to bank), attachments; Bank Transaction match |
| Filters | Company M · Station D · Period M (D: Month to date) · Bank account O · Matched to bank O |
| Columns | Date · Station · From account · Bank account · Amount · Deposit slip no. · Slip attached · Cash collected from (dates) · Days held · Matched to bank statement · Bank Transaction |
| Totals | T-REG |
| Summary | Banked · Average days held · Unmatched deposits |

### CSH-06 · Shortage Recovery [New]

| | |
|---|---|
| Answers | Have the shortages charged to staff been recovered? |
| Users · use | Accountant, manager monthly |
| Type · source | Script · GL on Staff Shortage Receivable (party Employee); Payment Entry (repayments); HRMS Additional Salary when installed (D16) |
| Filters | Company M · Station O · Employee O · As at M (D: today) · Only outstanding D (on) |
| Columns | Employee · Station · Charged (period) · Recovered by cash · Recovered by salary · Written off · Outstanding · Oldest outstanding (days) · Ageing 0–30 · 31–60 · 61–90 · 90+ |
| Totals | T-BAL per employee; ageing buckets summed |
| Summary | Outstanding · Over 90 days · Employees with balances |
| Notes | Recovery rules are company policy; the report only shows the ledger |

### CSH-07 · Cash Count by Currency [New]

| | |
|---|---|
| Answers | How much cash was counted in each currency and at what rate? |
| Users · use | Accountant daily, at multi-currency stations |
| Type · source | Script · Shift Cash Count (submitted shifts) |
| Filters | Company M · Station D · Period M (D: Last 7 days) · Currency O · Cashier O |
| Columns | Date · Shift · Cashier · Currency · Amount · Exchange rate · Base amount · Denomination detail (when recorded) |
| Totals | T-ADD per currency; base amounts summed |
| Notes | Hidden for stations with one currency |

---

## 14. Mobile money, card and bank (PAY)

### PAY-01 · Payment Reconciliation [New]

| | |
|---|---|
| Answers | For each provider and day: what the provider says, what the shifts recorded, what reached the bank |
| Users · use | Accountant daily |
| Type · source | Script · Payment Feed Entry, Shift Collection (through its Payment Entry), Bank Transaction |
| Filters | Company M · Station D · Provider D (first mobile money provider) · Period M (D: Last 7 days) · Status O (All, Unmatched, Not settled) |
| Grouping | Fixed: provider, then date; option till or terminal |
| Columns | Date · Provider · Till or terminal · Feed count · Feed amount · Recorded in shifts · Unmatched · Settled to bank · Not settled · Settlement date · Fees · Net settled |
| Calculations | Unmatched = feed amount − recorded; Not settled = recorded − settled |
| Totals | T-ADD |
| Summary | Unmatched · Not settled · Oldest unsettled (days) · Fees |
| Notes | Settlement and fees need the bank import (FMS-J06). Columns with no data source for a provider are hidden, never shown as zero. |

### PAY-02 · Clearing Account Ageing [Exists]

| | |
|---|---|
| Answers | Which payments are sitting in clearing accounts, and for how long? |
| Type · source | Script · Payment Entry, GL on clearing accounts |
| Filters | Company M · Station O · Provider O · As at M (D: today) |
| Columns | Provider · Station · 0–1 day · 2–3 days · 4–7 days · 8–30 days · 30+ · Total · Oldest item |
| Totals | T-ADD |

### PAY-03 · Mobile Money Register [New]

| | |
|---|---|
| Answers | Every mobile money transaction, its status and the cashier it belongs to |
| Users · use | Accountant, manager daily |
| Type · source | Script · Payment Feed Entry, Shift Collection, Payment Import Batch |
| Filters | Standard scope · Period M (D: Yesterday) · Provider O · Till O · Status O (Unmatched, Matched, Ignored, Duplicate) · Cashier O · Payer contains O · Reference contains O · Minimum amount O |
| Columns | Time · Provider · Till · Reference · Payer · Amount · Status · Shift · Cashier · Collection type (sale, debt receipt) · Payment Entry · Source (Feed, Import, Typed) |
| Totals | T-REG |
| Summary | Transactions · Amount · Unmatched · Duplicates refused |
| Notes | Payer phone numbers are personal data: masked except for accountants (permlevel), **[Open] Q-09** |

### PAY-04 · Card Settlement [New]

| | |
|---|---|
| Answers | Did the acquirer pay us for every card batch, net of fees? |
| Type · source | Script · Shift Collection (Card), Payment Entry, Bank Transaction |
| Filters | Company M · Station D · Terminal O · Period M (D: Last 14 days) · Only unsettled O |
| Columns | Batch date · Terminal · Transactions · Amount · Settled amount · Fees · Settlement date · Days to settle · Difference |
| Totals | T-ADD |

### PAY-05 · Payment Import Log [New]

| | |
|---|---|
| Type · source | Query · Payment Import Batch |
| Filters | Standard scope · Period M (D: Last 30 days) · Provider O · Status O |
| Columns | Imported at · Provider · Station · File · Rows · Created · Duplicates · Unassigned · Shift · Imported by |
| Totals | T-REG |

### PAY-06 · Debt Receipts Register [New]

| | |
|---|---|
| Answers | Which credit customers paid old balances at the station, and how |
| Type · source | Script · Shift Collection (type Debt Receipt), Payment Entry |
| Filters | Standard scope · Period M (D: Month to date) · Customer O · Paid by O (Cash, Mobile Money, Card) |
| Columns | Date · Shift · Cashier · Customer · Paid by · Provider · Reference · Amount · Payment Entry · Allocated to invoices |
| Totals | T-REG |

---

## 15. Credit customers and fleets (CRD)

### CRD-01 · Credit Slips Register [Exists (ext.)]

| | |
|---|---|
| Answers | Every credit slip, and any gaps in slip numbers |
| Users · use | Accountant daily and monthly; manager |
| Type · source | Query · Shift Credit Sale (submitted shifts), Sales Invoice, Delivery Note |
| Filters | Standard scope · Period M (D: Month to date) · Customer O · Vehicle O · Products O · Cashier O · Only gaps O · Only over limit O |
| Columns | Date · Shift · Slip no. · Customer · Vehicle · Driver · Product · Litres · Rate · Amount · Odometer · Cashier · Over limit · Approved by · Invoice or Delivery Note |
| Totals | T-REG: litres and amount |
| Notes (ext.) | Gap detection lists missing numbers per customer slip book (fms.md 11.2) |

### CRD-02 · Customer Fuel Statement [New]

| | |
|---|---|
| Answers | A statement for a fleet customer with the fuel details they ask for |
| Users · use | Accountant monthly, sent to customers |
| Type · source | Script · Sales Invoice and Delivery Note (from shifts), Shift Credit Sale, Payment Entry, GL (party balance) |
| Filters | Company M · Customer M · Period M (D: Last month) · Vehicle O · Station O |
| Grouping | Fixed: date; option vehicle |
| Columns | Date · Station · Slip no. · Vehicle · Driver · Product · Litres · Rate · Amount · Invoice · Payments · Balance |
| Totals | T-BAL: opening balance, charges, payments, closing balance |
| Notes | Print format with the company letterhead; sent by email with ERPNext Process Statement of Accounts or by Auto Email Report |

### CRD-03 · Fleet Vehicle Consumption [New]

| | |
|---|---|
| Answers | How much each vehicle buys, how far it goes, and whether that looks normal |
| Users · use | Accountant monthly; useful to fleet customers |
| Type · source | Script · Shift Credit Sale (litres, odometer), Customer Vehicle (monthly limit, allowed products) |
| Filters | Company M · Customer M · Period M (D: Last month) · Vehicle O · Only anomalies O |
| Columns | Vehicle · Driver(s) · Fills · Litres · Amount · First odometer · Last odometer · Distance (km) · L/100 km · Monthly limit · Limit used % · Products outside allowed · Odometer went backwards (count) |
| Calculations | Distance from odometer readings in time order; L/100 km = Σ litres ÷ distance × 100, blank when fewer than two readings |
| Totals | T-WTD |
| Notes | An odometer going backwards or an unusual L/100 km is a signal of misuse (by the driver or at the station) |

### CRD-04 · Credit Limits and Over-limit Sales [New]

| | |
|---|---|
| Answers | Which customers are near or over their limit, and who approved over-limit sales? |
| Users · use | Accountant, area manager weekly |
| Type · source | Script · Customer (credit limit), GL balance, Shift Credit Sale (`over_limit`, `over_limit_approved_by`), Customer Vehicle |
| Filters | Company M · Customer group O · Customer O · As at M (D: today) · Only over 80% D (on) |
| Columns | Customer · Credit limit · Balance · Unbilled deliveries · Exposure · Used % · Over-limit sales (count, amount, period) · Approved by · Vehicles over monthly litres |
| Calculations | Exposure = balance + unbilled Delivery Notes (monthly mode) |
| Totals | T-REG |

### CRD-05 · Unbilled Credit Deliveries [New]

| | |
|---|---|
| Answers | In monthly invoicing (D26), what has been delivered but not yet invoiced? |
| Type · source | Script · Delivery Note (from shifts), not fully billed |
| Filters | Company M · Station O · As at M · Customer O |
| Columns | Customer · Delivery Notes · First date · Last date · Litres · Amount · Days unbilled |
| Totals | T-ADD |
| Notes | Hidden when the company invoices per shift |

### CRD-06 · Accounts Receivable [ERPNext]

Native report with the **Station** dimension filter; *Accounts Receivable Summary* for totals. AFMS adds a link and a saved filter set *Credit customers, by station*.

---

## 16. Purchases, suppliers and payables (PUR)

### PUR-01 · Fuel Purchase Register [New]

| | |
|---|---|
| Answers | Ordered, received and invoiced: does it all agree? |
| Users · use | Accountant monthly |
| Type · source | Script · Purchase Order, Purchase Receipt, Purchase Invoice, GRN Delivery Dip |
| Filters | Company M · Station O · Period M (D: Last month) · Supplier O · Products O · Only mismatches O |
| Columns | GRN date · Supplier · Purchase Order · PO litres · PO rate · GRN · Invoiced litres (on GRN) · Received litres (dips) · Purchase Invoice · Invoice litres · Invoice rate · Rate difference · Quantity difference · Status |
| Calculations | Quantity difference = invoice litres − received litres; rate difference = invoice rate − PO rate |
| Totals | T-WTD |

### PUR-02 · Receipts Awaiting Supplier Invoice [New]

| | |
|---|---|
| Answers | Which GRNs have no supplier invoice yet? |
| Type · source | Script · Purchase Receipt (submitted, not fully billed) |
| Filters | Company M · Station O · As at M · Supplier O · Older than (days) O |
| Columns | GRN · Date · Supplier · Products · Litres · Value · Age (days) |
| Totals | T-ADD |
| Notes | Also listed in SHF-05 Open Items |

### PUR-03 · Supplier Advances [New]

| | |
|---|---|
| Answers | Which prepayments to suppliers are not yet used against invoices? |
| Type · source | Script · Payment Entry (advance to supplier), allocation to Purchase Invoices |
| Filters | Company M · Supplier O · As at M |
| Columns | Supplier · Advance paid · Allocated · Unallocated · Oldest unallocated (days) · Payment Entries |
| Totals | T-BAL per supplier |
| Notes | Many fuel suppliers require prepayment (fms.md 8.3) |

### PUR-04 · Accounts Payable [ERPNext]

Native, with the Station dimension where invoices carry it.

### PUR-05 · Landed Cost Summary [New]

| | |
|---|---|
| Type · source | Script · Landed Cost Voucher, Purchase Receipt |
| Filters | Company M · Period M (D: Last month) · Supplier O · Station O |
| Columns | GRN · Supplier · Litres · Product cost · Landed costs (by type) · Total · Landed cost per litre |
| Totals | T-WTD |

---

## 17. Shop, lubricants, LPG and services (DRY, LPG, SRV) [P]

These depend on fms-nonfuel.md (decisions D37 to D62). Until it is accepted, shop sales are reported by SAL-01 with *Fuel only* off, and ERPNext's *Stock Balance*, *Stock Ledger* and *Item-wise Sales Register* serve the shop.

| ID | Title | Answers | Source | Key filters | Key columns | Prof. |
|---|---|---|---|---|---|---|
| DRY-01 | Dry Stock Movement | Per item and location: opening, receipts, sales, adjustments, consumption, closing count, difference | Dry Stock Ledger, Stock Ledger | Station M, Period M, Item group O, Item O, Warehouse O, Cashier O | Opening · Receipts · Sold or recorded · Adjustments · Service consumption · Closing count · Difference | T-BAL |
| DRY-02 | Dry Stock Sales by Cashier | What each cashier sold from the shelf (Mode A) or left unreceipted (Mode B) | Dry Stock Ledger | Station M, Period M, Cashier O | Cashier · Item · Units · Value · Unreceipted units (Mode B) | T-ADD |
| DRY-03 | Dry Stock Count Exceptions | Counts above book, unusual jumps, confirm-as-book use | Dry Stock Ledger | Station M, Period M, Exception type O | Date · Item · Cashier · Book · Counted · Difference · Flag · Reason | T-REG |
| DRY-04 | Shop Stock Position | Book, last count, days of cover, reorder | Stock Ledger, Dry Stock Ledger | Station M, As at M, Item group O, Only below reorder O | Item · Book · Last count · Reorder level · Avg daily sales · Days of cover · Value | T-ADD |
| DRY-05 | Expiry and Batch | Batches expiring soon | Batch, Stock Ledger | Station M, Expiring within (days) D 60 | Item · Batch · Expiry · Qty · Value · Days left | T-ADD |
| DRY-06 | Slow Movers and Dead Stock | Items that do not sell | Stock Ledger, Sales Ledger | Company M, Station O, No sale for (days) D 90 | Item · Stock · Value · Last sale · Days since | T-ADD |
| DRY-07 | Shop Margin by Item Group | Margin of non-fuel business lines | GL, Stock Ledger | Company M, Station O, Period M | Item group · Net revenue · COGS · Margin · Margin % | T-WTD |
| DRY-08 | Adjustment and Write-off Trend | Damage, own use, promotions by reason and cashier | Stock Entry (Dry Stock Adjustment) | Station M, Period M, Reason O | Reason · Count · Units · Value · Approved by | T-PIVOT |
| LPG-01 | LPG Cylinder Reconciliation | Fulls sold against empties received, exchange against outright | Dry Stock Ledger | Station M, Period M, Cylinder size O, Cashier O | Size · Fulls sold · Empties received · Exchange · Outright · Imbalance | T-BAL |
| SRV-01 | Service Sales by Type, Crew and Day | What services earn | Sales Ledger (Service Job) | Station M, Period M, Service type O, Crew O | Service · Jobs · Units · Amount · Average rate · Rate overrides | T-WTD |
| SRV-02 | Job Ticket Register | Gaps and duplicates in job cards | Service Job | Station M, Period M, Only gaps O | Ticket · Date · Service · Vehicle · Amount · Status | T-REG |
| SRV-03 | Consumables Yield | Consumables used against jobs posted | Dry Stock Ledger, Service Job | Station M, Period M, Consumable O | Consumable · Standard use · Counted use · Difference · Implied unrecorded jobs | T-WTD |

---

## 18. Expenses and own use (EXP)

### EXP-01 · Station Expense Register [New]

| | |
|---|---|
| Answers | Every expense paid from the till, with type, receipt and limit |
| Users · use | Accountant, area manager weekly and monthly |
| Type · source | Script · Shift Collection (type Expense) of submitted shifts, Journal Entry; Purchase Invoices with the Station dimension (larger expenses) as an option |
| Filters | Standard scope · Period M (D: Month to date) · Expense type O · Cashier O · Include supplier invoices O · Only without receipt O · Only above limit O |
| Columns | Date · Shift · Cashier · Expense type · Description · Amount · Receipt attached · Limit · Over limit · Journal Entry or Purchase Invoice |
| Totals | T-REG |
| Summary | Expenses · Without receipt · Over limit · Count |

### EXP-02 · Expense Trend [New]

| | |
|---|---|
| Answers | Are station expenses rising, and where? |
| Type · source | Script · GL (expense accounts, Station dimension) |
| Filters | Company M · Station group O · Stations O · Period M (D: Last 6 months) · Granularity D (Month) · Compare with O · Expense type or account O |
| Grouping | Default: expense type. Options: station, month |
| Columns | Group · Amount · Per 1,000 L sold · Change % · Share % |
| Totals | T-WTD |
| Chart | Line or stacked bar by month |

### EXP-03 · Fuel Own Use Register [New]

| | |
|---|---|
| Answers | Fuel used by the company itself: how much, for what, by whom |
| Users · use | Area manager, accountant monthly |
| Type · source | Script · Stock Entry (type Fuel Own Use) with FMS fields; Nozzle Ledger (`own_use_l`) |
| Filters | Standard scope · Period M (D: Last month) · Purpose O · Vehicle or asset O · Attendant O · Products O |
| Grouping | Default: purpose. Options: vehicle or asset, station, month |
| Columns | Date · Station · Nozzle · Product · Litres · Value · Purpose · Vehicle or asset · Attendant · Narration · Reference · Expense account |
| Totals | T-ADD |
| Summary | Litres · Value · Entries · Largest purpose |

---

## 19. Staff and productivity (STF)

### STF-01 · Shifts Worked by Employee [New]

| | |
|---|---|
| Answers | Who worked which shifts, as cashier or attendant |
| Users · use | Manager monthly; HR or payroll input |
| Type · source | Script · Shift Cashier, Shift Meter Reading (attendants), Forecourt Shift (window) |
| Filters | Company M · Station D · Period M (D: Last month) · Employee O · Role in shift O (Cashier, Attendant) |
| Columns | Employee · Station · Shifts as cashier · Shifts as attendant · Hours · Night shifts · Shifts with shortage |
| Totals | T-ADD |
| Notes | AFMS records shift presence, not attendance. Attendance and payroll are HRMS's job when installed (D16). |

### STF-02 · Staff Productivity [New]

| | |
|---|---|
| Answers | Volume and value handled per person and per hour |
| Type · source | Script · Nozzle, Sales and Cashier Ledgers |
| Filters | Standard scope (multi) · Period M (D: Last 30 days) · Minimum shifts D (3) |
| Columns | Employee · Station · Hours · Litres · Litres per hour · Sales per hour · Transactions per hour (Mode B only) · Shortage per 1,000 L |
| Totals | T-RANK; station averages |

---

## 20. Control, fraud and audit (CTL)

Control reports show **facts and signals**, never verdicts. A signal is a reason to look, not proof of wrongdoing.

### CTL-01 · Exception Register [Exists (ext.)]

| | |
|---|---|
| Answers | Every exception the system recorded: what, where, who approved |
| Users · use | Area manager daily and weekly; auditor |
| Type · source | Script · Shift Resolution, Shift Tank Dip, Shift Credit Sale (over limit), Shift Correction, Workflow history, Nozzle Ledger (drift) |
| Filters | Standard scope (multi) · Period M (D: This week) · Exception type O (Tank variance, Cashier write-off, Excess, Over-limit credit, Drift, Back-dated post, Rejected approval, Correction) · Reason O · Only unapproved O · Minimum amount O |
| Columns | Date · Station · Shift · Type · Subject (cashier, tank, customer, nozzle) · Amount · Litres · Reason · Note · Needed approval · Approved by · Approved at · Document |
| Totals | T-REG: count and amount per type |
| Summary | Exceptions · Unapproved · Write-offs · Over-limit credit |

### CTL-02 · Approvals Log [New]

| | |
|---|---|
| Answers | Who approved what, how fast, and how often they rejected |
| Users · use | Area manager, director, auditor weekly and monthly |
| Type · source | Script · Workflow history (Version and Comment of Forecourt Shift, Fuel Price Change, Shift Correction) |
| Filters | Company M · Station O · Period M (D: Last 30 days) · Document type O · Approver O · Action O (Approved, Rejected) |
| Columns | Document type · Document · Station · Requested by · Requested at · Approver · Action · Acted at · Hours to act · Comment |
| Totals | T-REG; average hours to act per approver |
| Summary | Approvals · Rejections · Average hours · Pending now |

### CTL-03 · Corrections Register [New]

| | |
|---|---|
| Answers | Which closed shifts were corrected, why, and with what effect |
| Users · use | Director, auditor monthly |
| Type · source | Script · Shift Correction, Shift Correction Item, superseded ledger rows |
| Filters | Company M · Station O · Period M (D: Last 90 days) · Correction type O · Status O |
| Columns | Correction · Shift · Station · Type · Reason · Prepared by · Approved by · Applied at · Litres moved · Amount moved · Next shift affected · Documents changed |
| Totals | T-REG |
| Notes | Repeated corrections at one station or by one preparer are a training or control issue |

### CTL-04 · Back-dated and Late Postings [New]

| | |
|---|---|
| Answers | Which documents were posted long after the event, or into past periods? |
| Users · use | Auditor, accountant weekly |
| Type · source | Script · GL Entry and Stock Ledger Entry (`creation` vs `posting_date`), Purchase Receipt, Stock Entry, Payment Entry at FMS stations |
| Filters | Company M · Station O · Period M (D: Last 30 days) · Minimum delay (days) D (2) · Document type O |
| Columns | Document type · Document · Station · Posting date · Created at · Delay (days) · Created by · Inside a closed shift window (flag) · Closed accounting period (flag) |
| Totals | T-REG |
| Notes | Postings inside closed shift windows are blocked for counted items (fms-nonfuel.md D50); this report covers everything else |

### CTL-05 · Variance Reason Analysis [New]

| | |
|---|---|
| Answers | Which reasons are used, where, by whom: is *Dip error* covering real losses? |
| Type · source | Script (pivot) · Shift Tank Dip, Shift Resolution, Shift Meter Reading (drift reasons) |
| Filters | Standard scope (multi) · Period M (D: Last 90 days) · Area D (Tank, Cashier, Drift) · Rows D (Reason) · Columns D (Station; Prepared by; Month) |
| Totals | T-PIVOT: count and litres or amount |
| Notes | A reason used far more at one station than the network is a signal |

### CTL-06 · Control Signals by Cashier [New]

| | |
|---|---|
| Answers | Which cashiers show several warning signs at once? |
| Users · use | Area manager, director monthly |
| Type · source | Script · Cashier, Sales, Nozzle and Wetstock Ledgers |
| Filters | Standard scope (multi) · Window D (Last 60 days) · Minimum shifts D (5) · Minimum signals D (2) |
| Columns | Cashier · Station · Shifts · Signal: shortages above station norm · Signal: mobile share below station norm · Signal: test litres above norm · Signal: tank variance worse on their shifts · Signal: repeated excesses · Signal: over-limit credit · Signals (count) |
| Calculations | Each signal compares the cashier with the station average over the window; thresholds are filters with defaults **[Open] Q-07** |
| Totals | T-RANK by signals |
| Notes | Access limited to area managers and directors (section 27). Shows signals only; no score is stored on the employee. |

### CTL-07 · Segregation of Duties Check [New]

| | |
|---|---|
| Answers | Were preparer and approver always different people? |
| Type · source | Script · Workflow history, `approved_by` fields, Version |
| Filters | Company M · Period M (D: Last 90 days) |
| Columns | Document · Type · Preparer · Approver · Same person (flag) · Edited after approval (flag) · Re-approved (flag) |
| Totals | T-REG |
| Notes | The workflow prevents the same person (I03); this report proves it and catches workarounds such as shared logins (same user on two devices at once, from session data where available) |

### CTL-08 · Shift Edit Audit Trail [New]

| | |
|---|---|
| Answers | Who changed what on a shift, and when, before it closed |
| Users · use | Auditor on demand |
| Type · source | Script · Version of Forecourt Shift (child-row changes) |
| Filters | Company O · Station M · Shift O · Period M · User O · Field O (closing readings, dips, cash, resolutions) |
| Columns | Changed at · User · Shift · Section · Row (nozzle, tank, cashier) · Field · Old value · New value · Status at the time |
| Totals | T-REG |
| Notes | Changes after *Reconciled* or after approval are highlighted |

---

## 21. Equipment, calibration and maintenance (EQP)

### EQP-01 · Equipment Register [New]

| | |
|---|---|
| Answers | What equipment each station has, and how it is configured |
| Type · source | Script · Station, Fuel Tank, Island, Pump, Nozzle, Tank Calibration Chart |
| Filters | Company O · Station group O · Station O · Active D (on) |
| Grouping | Fixed: station, tank and island, pump, nozzle (tree) |
| Columns | Station · Tank (capacity, safe fill, product, chart valid from) · Island · Pump (meters recorded, sales basis) · Nozzle (product, tank, max meter, test limit, last readings) |
| Totals | Counts of tanks, pumps, nozzles; capacity summed per product |

### EQP-02 · Meter Change Register [New]

| | |
|---|---|
| Type · source | Query · Meter Change (submitted) |
| Filters | Standard scope · Period M (D: Last 12 months) · Reason O · Nozzle O |
| Columns | Changed at · Station · Pump · Nozzle · Reason · Technician · Old final readings · New start readings · Certificate attached · Prepared by |
| Totals | T-REG |

### EQP-03 · Calibration Chart Register [New]

| | |
|---|---|
| Answers | Which tanks have valid calibration charts, and which need attention? |
| Type · source | Script · Tank Calibration Chart, Fuel Tank |
| Filters | Company O · Station O · Status O (Valid, Missing, Chart mode without chart) |
| Columns | Station · Tank · Dip entry mode · Chart · Valid from · Rows · Maximum depth · Certificate · Status |
| Totals | T-REG |
| Notes | The specs define *valid from* only, no expiry (FMS Health checks "expiring or missing"). Re-calibration intervals are **[Open] Q-10**. |

### EQP-04 · Equipment Health [New]

| | |
|---|---|
| Answers | Which equipment looks wrong today? |
| Users · use | Area manager, administrator daily |
| Type · source | Script · Nozzle Ledger, Wetstock Ledger, Stock Ledger, Tank Calibration Chart |
| Filters | Standard scope (multi) · As at M (D: today) |
| Columns | Station · Equipment · Problem (*No movement 7 days while active*, *Drift trend*, *Book below zero*, *Book above capacity*, *No dip for n days*, *Chart missing*) · Since · Severity |
| Totals | T-REG: count by problem |
| Notes | The equipment part of INT-01 FMS Health (fms.md 15.4) as a report users can filter |

---

## 22. Tax, fiscal and regulatory (CMP)

The core is jurisdiction-neutral (fms.md P9). Country-specific content lives in **country packs**: the report logic is shared, and the columns and labels that a regulator or tax authority requires are defined per country after confirmation with the company's accountant. Nothing here states a legal requirement; the content of each country template is **[Open] Q-11**.

### CMP-01 · Sales Tax Summary by Station [New]

| | |
|---|---|
| Answers | Tax charged on sales per station, product and tax rate |
| Users · use | Accountant monthly, for the tax return |
| Type · source | Script · Sales Invoice taxes (Sales Taxes and Charges), Sales Invoice items, Station dimension |
| Filters | Company M · Station O · Period M (D: Last month) · Tax account O · Products O |
| Columns | Station · Product · Tax rate · Taxable amount · Tax amount · Exempt or zero-rated amount · Invoices |
| Totals | T-ADD |
| Notes | Uses posted invoices only, so it equals ERPNext's tax ledgers; links to ERPNext's own tax reports |

### CMP-02 · Fiscal Submission Status [New]

| | |
|---|---|
| Answers | Were all invoices accepted by the fiscal system? |
| Users · use | Accountant daily |
| Type · source | Script · Sales Invoice fiscal fields set by the fiscal adapter (FMS-J07), Integration Inbox |
| Filters | Company M · Station O · Period M (D: Last 7 days) · Status O (Pending, Accepted, Rejected, Cancelled) |
| Columns | Invoice · Date · Station · Customer · Amount · Fiscal status · Fiscal number · Submitted at · Error · Attempts |
| Totals | T-REG by status |
| Summary | Invoices · Accepted · Pending · Rejected |

### CMP-03 · Regulatory Volume Return [New, country template]

| | |
|---|---|
| Answers | Opening stock, purchases, sales and closing stock per product per month, in the regulator's layout |
| Users · use | Accountant monthly |
| Type · source | Script · Wetstock Ledger, Stock Ledger, Purchase Receipts |
| Filters | Company M · Station M · Month M |
| Columns (generic) | Product · Opening stock (L) · Received (L) · Sold (L) · Own use (L) · Losses (L) · Closing stock (L) · Supplier(s) · Licence number (from Station) |
| Totals | T-BAL per product |
| Notes | Print format per country pack; the Station needs a licence-number field if the template asks for it (gap G-06) |

### CMP-04 · Regulated Price Compliance [Open]

| | |
|---|---|
| Answers | Where maximum retail prices are set by a regulator, did any sale exceed them? |
| Notes | Needs a master of regulated prices by product, zone and period, which the specs do not have. **[Open] Q-12**: build it as part of a country pack, or leave it out. |

---

## 23. Financial and management (FIN)

### FIN-01 · Station Profit and Loss [ERPNext]

ERPNext *Profit and Loss Statement* filtered by the **Station** accounting dimension; v16 custom financial statements for formula-driven layouts (fms.md 11.4). AFMS ships a saved layout *Station P&L* with fuel, shop and services income lines grouped by Item Group accounts.

### FIN-02 · Consolidated Financial Statements [ERPNext]

ERPNext consolidated statements across companies (v16), with presentation currency.

### FIN-03 · Station Comparison [Exists (ext.)]

| | |
|---|---|
| Answers | How does each station perform against the others? |
| Users · use | Area manager, director monthly |
| Type · source | Script · all ledgers, GL |
| Filters | Company O (multi) · Station group D · Period M (D: Last month) · Compare with O |
| Columns | Station · Litres per day · Sales · Margin per litre · Losses per 1,000 L · Shortage per 1,000 L · Mobile share % · Delivery variance % · Expenses per 1,000 L · Open items · Rank |
| Totals | T-RANK; network average row |
| Chart | Bar by station for a chosen measure |

### FIN-04 · Executive Summary [New]

| | |
|---|---|
| Answers | The business on one page for directors |
| Users · use | Director weekly and monthly; emailed |
| Type · source | Script · ledgers, GL |
| Filters | Company O (multi) · Station group O · Period M (D: Last week) · Compare with D (Previous period) |
| Sections | Volume and sales (with change) · Gross margin and per litre · Losses (wetstock, delivery, own use) · Cash position and banking delay · Receivables and over-limit · Exceptions and corrections · Top and bottom three stations |
| Totals | T-WTD per section |
| Notes | Print format for email; every figure links to its report |

### FIN-05 · Investor Statement [New]

| | |
|---|---|
| Answers | What an investor's company or stations did in the period |
| Users · use | Investor monthly and quarterly |
| Type · source | Script · ledgers, GL for the investor's companies |
| Filters | Company M (limited to the investor's) · Period M (D: Last quarter) |
| Columns | Station · Litres · Sales · Gross margin · Operating expenses · Station result · Cash generated · Receivables · Change vs prior period |
| Totals | T-WTD |
| Notes | What an investor may see is governed by User Permissions on Company (fms.md 14.2). Any profit-sharing or dealer commission calculation is not in the specs, **[Open] Q-13**. |

### FIN-06 · Station Scorecard [New]

| | |
|---|---|
| Answers | A monthly scorecard per station with the measures that matter |
| Type · source | Script · as FIN-03 |
| Filters | Company O · Station group D · Month M |
| Columns | Station · each measure of FIN-03 with its value, network average and a status word (*Better*, *In line*, *Worse*) |
| Totals | T-RANK |
| Notes | Without targets the comparison is against the network average. Targets per station are **[Open] Q-14**. |

---

## 24. Planning and forecasting (FCS)

### FCS-01 · Run-out Forecast [Exists (ext.)]

| | |
|---|---|
| Answers | Which tanks will run dry soon, and how much to order? |
| Users · use | Manager, accountant daily |
| Type · source | Script · Stock Ledger, Nozzle Ledger (sales history), Fuel Tank |
| Filters | Standard scope (multi) · Horizon D (3 days) · Sales window D (14 days) · Products O |
| Columns | Station · Tank · Product · Book stock · Average daily sales · Days of cover · Run-out date · Ullage to safe fill · Suggested order (L) · Open Purchase Orders (L) |
| Calculations | Suggested order = ullage to safe fill − open orders, rounded down to the truck compartment size when configured |
| Totals | T-REG; suggested litres per product |
| Notes (ext.) | Open Purchase Orders and compartment rounding added. Lead times and compartment sizes are not in the specs, **[Open] Q-15**. |

### FCS-02 · Sales Forecast [New]

| | |
|---|---|
| Answers | Expected sales per product next week or month, for supply and cash planning |
| Type · source | Script · Nozzle and Sales Ledgers |
| Filters | Standard scope (multi) · Horizon D (4 weeks) · Method D (Moving average 4 weeks; Same period last year with trend) · Products O |
| Columns | Period · Product · Forecast litres · Forecast sales · Last year · Recent trend % |
| Totals | T-ADD |
| Chart | Line: actual and forecast |
| Notes | Simple, explainable methods only; the method is shown in the footnote |

---

## 25. Integrations, devices and system health (INT)

### INT-01 · FMS Health [Exists]

Daily scheduled report (fms.md 15.4): stations with no shift in 24 hours, old draft shifts, nozzles without movement, impossible tank stock, old clearing items, failed inbox messages, missing charts. Emailed to administrators and area managers.

### INT-02 · Integration Inbox Log [New]

| | |
|---|---|
| Answers | What came in from providers and devices, and what failed? |
| Users · use | Administrator daily |
| Type · source | Script · Integration Inbox |
| Filters | Company O · Station O · Period M (D: Last 2 days) · Provider O · Direction O · Status D (Failed) |
| Columns | Received at · Provider · Direction · Message type · Status · Attempts · Error · Linked record |
| Totals | T-REG by status |
| Summary | Messages · Failed · Retrying · Oldest failure |

### INT-03 to INT-09 · Mode B reports [P] (fms-nonfuel.md 18.1)

| ID | Title | Key filters | Key columns |
|---|---|---|---|
| INT-03 | Live Sales by Station | Stations, Today | Station · Sales so far · Litres · Transactions · Last sale at |
| INT-04 | Unpaid FCC Transactions | Station M, Status D (Unpaid) | Transaction · Pump · Nozzle · Litres · Amount · Ended at · Attendant · Age |
| INT-05 | Nozzle Completeness | Station M, Period M | Nozzle · Totaliser movement · Transactions total · Gap (L) · Resolution |
| INT-06 | Unreceipted Sales by Cashier | Station M, Period M | Cashier · Unreceipted fuel · Unreceipted dry stock · Count · Value |
| INT-07 | Voids and Refunds | Station M, Period M, Cashier O | Sale · Void time · Cashier · Supervisor · Amount · Reason |
| INT-08 | Offline Sales | Station M, Period M, Device O | Device · Offline sales · Value · Longest offline period · Price-list mismatches |
| INT-09 | Device Health | Station O | Device · Type · Status · Last seen · Queue depth · App version |

---

## 26. Scheduled reports and distribution

Scheduled reports use the native **Auto Email Report** (fixtures, disabled by default, enabled per company).

| Report | Frequency | Time (station time zone) | Recipients | Format |
|---|---|---|---|---|
| SHF-02 Daily Station Report | Daily | 07:00 | Directors, area manager of the group | PDF |
| SHF-05 Open Items | Daily | 07:30 | Station managers (own station) | Inline HTML |
| INT-01 FMS Health | Daily | 06:30 | Administrators, area managers | Inline HTML |
| WET-03 Wetstock Variance, *outside tolerance, yesterday* | Daily | 07:00 | Area managers | Inline HTML, sent only when not empty |
| PAY-01 Payment Reconciliation | Daily | 08:00 | Accountants | Excel |
| FIN-04 Executive Summary | Weekly, Monday | 08:00 | Directors | PDF |
| CSH-02 Cashier Performance | Weekly | Monday 08:00 | Area managers | Excel |
| SHF-07 Monthly Station Report | Monthly, 2nd | 08:00 | Managers, directors, investors (own companies) | PDF |
| CRD-02 Customer Fuel Statement | Monthly, 3rd | 09:00 | Each credit customer's billing contact | PDF (through Process Statement of Accounts or a per-customer Auto Email Report) |
| FIN-05 Investor Statement | Quarterly | | Investors | PDF |

Rules: a scheduled report respects the recipient user's permissions (it runs as that user's role scope). Emails to customers go only through the customer's contacts in ERPNext. Times are suggestions; **[Open] Q-16**.

---

## 27. Report access by role

### 27.1 Matrix

Role names follow the UI/UX guide 17.1 mapping (final names open there). **R** = may run, **O** = own records only, **—** = no access.

| Domain | Administrator | Station manager | Supervisor | Cashier | Accountant | Area manager | Director | Investor |
|---|---|---|---|---|---|---|---|---|
| SHF | R | R | R (SHF-01, 03, 05) | — | R | R | R | SHF-07 |
| SAL | R | R | R | — | R | R | R | SAL-06, 07 |
| MTR | R | R | R | — | R | R | R | — |
| WET | R | R | R | — | R | R | R | WET-03 |
| DLV | R | R | — | — | R | R | R | — |
| PRC | R | PRC-01, 02 | — | — | R | R | R | PRC-03 |
| CSH | R | R | — | CSH-01 (O) | R | R | R | — |
| PAY | R | PAY-03, 05 | — | — | R | R | R | — |
| CRD | R | CRD-01, 04 | — | — | R | R | R | — |
| PUR | R | PUR-02 | — | — | R | R | R | — |
| DRY, LPG, SRV | R | R | R | — | R | R | R | — |
| EXP | R | R | — | — | R | R | R | — |
| STF | R | R | — | — | R | R | R | — |
| CTL | R | CTL-01 | — | — | R | R | R | — |
| CTL-06, CTL-08 | R | — | — | — | — | R | R | — |
| EQP | R | R | R | — | R | R | R | — |
| CMP | R | — | — | — | R | R | R | — |
| FIN | R | FIN-03 | — | — | R | R | R | FIN-02, 05 |
| FCS | R | R | — | — | R | R | R | — |
| INT | R | INT-01, 03 to 09 | — | — | R | R | — | — |

### 27.2 Row-level scope

Every report shows only the stations and companies the user is permitted (User Permissions on Station and Company, fms.md 14.2). Cashiers see only their own Employee's rows.

### 27.3 How Script Reports enforce it

Script Reports built with `frappe.qb` or SQL do not apply User Permissions by themselves. Every AFMS report:

1. Calls `forecourt.reports.common.permitted_stations(user)` and `permitted_companies(user)`.
2. Intersects them with the station and company filters (an empty intersection returns no rows and the message *You have no access to the selected stations*).
3. For cashier-scoped reports, restricts to the Employee linked to the user.
4. Is covered by the permission tests (extension of FMS-I05).

---

## 28. Performance, indexes and prepared reports

### 28.1 Targets **[Spec]** (FMS-H12)

| Run | Target |
|---|---|
| One station, one month | Under 3 seconds |
| Group, one year | Under 10 seconds |

### 28.2 Rules

| Rule | Detail |
|---|---|
| Query the ledgers with the indexed columns first | (`station`, `posting_date`), (`company`, `posting_date`), and the per-ledger indexes (catalogue 10) |
| No queries per row | Aggregate in SQL; one query per section |
| No joins to shift child tables for analytics | The ledgers carry every dimension (fms.md 10.4); registers that read child tables filter by submitted shifts in the date range first |
| Range limits | Detail registers: 366 days; aggregate reports: 3 years; longer through a prepared report (FMS-R802) |
| Prepared reports | Reports that may exceed the targets at group scale run as native **Prepared Reports** (background, result stored, user notified): WET-03, WET-04, CSH-02, CTL-06, FIN-03, FIN-04, FIN-06, SAL-06, PRC-03, PRC-04 when the scope is a group and the range is over 3 months |
| New indexes | Added only with an `EXPLAIN` showing the need: candidates `Sales Ledger Entry (customer, posting_date)` for CRD reports, `Nozzle Ledger Entry (pump, posting_date)` for MTR-03 |
| Caching | No custom caching. Dashboards use the Dashboard Chart cache (UI/UX guide 15.4). |

---

## 29. Testing reports

| Test | Rule |
|---|---|
| **Totals agree** (extends FMS-H11) | For the golden-month scenario data (FMS-K01): SAL-01 total = SHF-03 total = SHF-02 sum = GL income (net, after Q-08); WET-02 closing = WET-01 book = ERPNext Stock Balance for tank warehouses; CSH-01 closing = GL Staff Shortage Receivable; PAY-02 total = GL clearing balances; WET-08 value = Stock Balance value |
| **Weighted rates** | Every T-WTD report: the total row's rates equal the recomputed ratio, not the average of rows |
| **Corrections** | A meter correction moves litres between two shifts; MTR-01, SAL-01, WET-02 show corrected figures by default and both with *Include correction history* |
| **Permissions** | A station manager sees only their station; a cashier sees only their statement; an investor only their companies |
| **Currencies** | Two companies with different currencies: totals per currency, none across |
| **Filters** | Every dependent filter clears when its parent changes; invalid ranges show FMS-R80x |
| **Performance** | FMS-H12 data set: targets met; `EXPLAIN` shows index use |
| **Empty states** | Every report with no rows shows *No data for the selected filters* and keeps its filters |

---

## 30. Data gaps found while specifying reports

| # | Gap | Reports affected | Proposal | Status |
|---|---|---|---|---|
| G-01 | Water (mm, L) is not in the Wetstock Ledger | WET-05, WET-04 | Add `water_l` to Wetstock Ledger Entry, written at shift close and spot dip | [Open] Q-17 |
| G-02 | No time of sale within a shift in Mode A | SAL-08 | None: inherent to meter-based shifts; available in Mode B | Accepted limitation |
| G-03 | No `closed_at` / `closed_by` on Forecourt Shift | SHF-06, CTL-02 | Add both, set on submit; read Version until then | [Open] Q-17 |
| G-04 | Whether Sales Ledger `amount` includes tax is not stated | PRC-03, PRC-04, CMP-01, SAL reports | Document it; add `net_amount` if gross is stored | [Open] Q-08 |
| G-05 | Odometer is on Shift Credit Sale but not in the Sales Ledger | CRD-03 | Read Shift Credit Sale (registers may); no change needed | Accepted |
| G-06 | No licence number field on Station | CMP-03 | Add in the country pack | [Open] Q-11 |
| G-07 | No targets per station | FIN-06 | Compare with the network average until targets exist | [Open] Q-14 |
| G-08 | No lead times or truck compartments | FCS-01 | Optional fields on Supplier or Station | [Open] Q-15 |
| G-09 | No regulated price master | CMP-04 | Country pack master | [Open] Q-12 |
| G-10 | Payment fees and settlement only with the bank import | PAY-01, PAY-04 | Hide columns without data | Accepted |

---

## 31. Mapping to existing and earlier report lists

| Earlier name or source | This catalogue |
|---|---|
| Shift Report (catalogue 13.1) | SHF-01 |
| Daily Station Report | SHF-02 |
| Sales by Shift | SHF-03 Shift Summary |
| Sales by Product, Tank, Cashier | SAL-01, SAL-02, SAL-03 |
| Sales by Pump and Nozzle | MTR-03 Pump and Nozzle Performance |
| Payment Mix Matrix | SAL-04 |
| Sales Mix by Payment Type (fms.md 11.3) | SAL-05 |
| Tank Stock Position, Wetstock Variance, Delivery Variance, Meter Drift | WET-01, WET-03, DLV-02, MTR-02 |
| Cashier Statement, Cashier Variance Ranking | CSH-01, CSH-02 Cashier Performance |
| Credit Slips Register | CRD-01 |
| Clearing Account Ageing, Cash Position by Station | PAY-02, CSH-04 |
| Exception Register, Open Items, Station Comparison, Run-out Forecast, FMS Health | CTL-01, SHF-05, FIN-03, FCS-01, INT-01 |
| Volume and Margin Dashboard (fms.md 11.4) | Group Dashboard (UI/UX guide 15) using SAL-06, PRC-03 |
| UI/UX guide 14: Shift Reconciliation, Meter Movement, Tank Stock Movement, Payment Reconciliation, Cash Collection, Price History, Approvals Log | SHF-04, MTR-01, WET-02, PAY-01, CSH-03, PRC-01, CTL-02 |
| fms-nonfuel.md 18.1 non-fuel reports | DRY-01 to DRY-08, LPG-01, SRV-01 to SRV-03 |
| fms-nonfuel.md 18.1 Mode B reports | INT-03 to INT-09 |
| The brief: Attendant Performance | CSH-02 (attendants carry no balance) |
| The brief: Wetstock Reconciliation | WET-03 (period) and WET-02 (per tank) |
| The brief: Station Performance | FIN-03, FIN-06 |
| The brief: Variance and Exceptions | CTL-01 |

---

## 32. Build plan

Tasks for a new TASKS.md section **R. Reporting** (prefix FMS-R; FMS-R is unused in TASKS.md).

| Task | Scope | Depends on | Size |
|---|---|---|---|
| FMS-R01 | Review the 22 built reports against this catalogue; list differences | — | M |
| FMS-R02 | Shared framework: `reports/common.py` and `report_filters.js` (standard filters, presets, comparisons, permissions, currency, totals profiles, tree rows, footnotes, FMS-R80x); verify the total-row and Save As behaviour in v16 | R01 | L |
| FMS-R03 | Move the built reports onto the framework; apply the (ext.) changes of SHF-02, SHF-03, SAL-01, SAL-03, MTR-03, WET-03, DLV-02, CSH-02, CRD-01, CTL-01, FIN-03, FCS-01 | R02 | L |
| FMS-R04 | Shift and cash: SHF-04, SHF-06, SHF-07, CSH-03, CSH-05, CSH-06, CSH-07 | R02 | L |
| FMS-R05 | Meters and wetstock: MTR-01, MTR-04, MTR-05, WET-02, WET-04, WET-05, WET-06, WET-07, WET-08 | R02 | L |
| FMS-R06 | Deliveries and purchases: DLV-01, DLV-03, DLV-04, PUR-01, PUR-02, PUR-03, PUR-05 | R02 | M |
| FMS-R07 | Prices and margins: PRC-01 to PRC-05 (after Q-08) | R02 | M |
| FMS-R08 | Payments and credit: PAY-01, PAY-03 to PAY-06, CRD-02 to CRD-05 | R02 | L |
| FMS-R09 | Sales extras: SAL-05, SAL-06, SAL-07 | R02 | S |
| FMS-R10 | Expenses and staff: EXP-01 to EXP-03, STF-01, STF-02 | R02 | M |
| FMS-R11 | Control and audit: CTL-02 to CTL-08 | R02 | L |
| FMS-R12 | Equipment: EQP-01 to EQP-04 | R02 | S |
| FMS-R13 | Compliance: CMP-01, CMP-02; CMP-03 generic template | R02 | M |
| FMS-R14 | Management and planning: FIN-04 to FIN-06, FCS-02; saved P&L layout (FIN-01) | R03 | M |
| FMS-R15 | Integrations: INT-02 | R02 | S |
| FMS-R16 | Scheduled reports and saved filter sets (sections 26, 3.6) | R03 to R15 | S |
| FMS-R17 | Report tests (section 29) on the golden-month data | R03 to R15, K01 | L |
| FMS-R18 | Performance check at group scale; prepared-report settings (section 28) | R17 | M |
| Later | DRY, LPG, SRV and INT-03 to INT-09 with fms-nonfuel.md; SAL-08 with Mode B; CMP-04 if Q-12 says yes | | |

**Order.** R01 and R02 first. Then R03 (built reports on the new framework) and R04 and R05, which cover daily control. Finance-heavy reports (R07, R13) wait for Q-08.

---

## 33. Open questions

| # | Question | Default until answered |
|---|---|---|
| Q-01 | Accept the new error range FMS-R8xx for report filter messages? | Yes |
| Q-02 | Should the four dashboards (UI/UX guide 15) be built from these reports' figures only (no separate card queries)? | Yes, where a Report-based Number Card fits |
| Q-03 | Is the fiscal year the calendar year for all companies? (Presets use ERPNext's Fiscal Year either way.) | As set in ERPNext |
| Q-04 | Decimal precision for litres, money and percentages | 4.8 |
| Q-05 | When is a shift close "late"? | 12 hours after shift end |
| Q-06 | Payment-mix deviation that flags a cashier or station | 15 percentage points |
| Q-07 | Thresholds for leak indicators (WET-04) and cashier signals (CTL-06) | The defaults in those reports, reviewed after the pilot |
| Q-08 | Does the Sales Ledger `amount` include tax? Should a `net_amount` be added? | Margin reports read GL net income |
| Q-09 | Mask payer phone numbers for non-accountants? | Yes |
| Q-10 | Do calibration charts expire, and after how long? | No expiry |
| Q-11 | Content of country packs (regulatory return layout, licence fields) for the first country | Generic CMP-03 |
| Q-12 | Build a regulated price master for price-cap compliance? | No |
| Q-13 | Are there dealer commissions or investor profit-sharing to calculate? | No |
| Q-14 | Targets per station for the scorecard? | Network average |
| Q-15 | Lead times and truck compartment sizes for order suggestions? | Not used |
| Q-16 | Schedule times and recipients for automatic emails | Section 26 |
| Q-17 | Add `water_l` to the Wetstock Ledger and `closed_at`, `closed_by` to Forecourt Shift? | Read dip documents and Version |
