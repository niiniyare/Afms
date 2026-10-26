# FMS DocType Catalogue

**Version:** 1.1 (documentation review: forward links, approval workflow, proposed decisions D16–D36 of the design guide)
**Date:** 2026-10-20
**App:** `forecourt` (Frappe Framework v16, ERPNext v16, HRMS v16 optional)
**Companion documents:** [fms.md](fms.md) (the design guide: the *why*), [../TASKS.md](../TASKS.md) (the task list: the *build order*), [../CLAUDE.md](../CLAUDE.md) (rules for developers and agents)

This catalogue lists every DocType the FMS app defines, every custom field it adds to ERPNext DocTypes, and how they are grouped in workspaces and navigation. DocTypes are ordered **from least dependent to most dependent**, which is also the order in which they are built (see the task list). A few fields link *forward* to a DocType built later; they are added by the later task (section 3.1). If this catalogue and the design guide disagree on a field name or a DocType name, this catalogue wins. The design guide wins on behaviour.

---

## Contents

1. [Conventions](#1-conventions)
2. [Modules and roles](#2-modules-and-roles)
3. [Dependency map](#3-dependency-map)
4. [Level 0: settings and simple masters](#4-level-0-settings-and-simple-masters)
5. [Level 1: Station](#5-level-1-station)
6. [Level 2: physical equipment and customer vehicles](#6-level-2-physical-equipment-and-customer-vehicles)
7. [Level 3: equipment details](#7-level-3-equipment-details)
8. [Level 4: station transactions outside the shift](#8-level-4-station-transactions-outside-the-shift)
9. [Level 5: Forecourt Shift](#9-level-5-forecourt-shift)
10. [Level 6: ledgers and corrections](#10-level-6-ledgers-and-corrections)
11. [Integrations](#11-integrations)
12. [Custom fields and records on ERPNext DocTypes](#12-custom-fields-and-records-on-erpnext-doctypes)
13. [Reports, number cards and charts](#13-reports-number-cards-and-charts)
14. [Workspaces and navigation](#14-workspaces-and-navigation)
15. [Summary table](#15-summary-table)

---

## 1. Conventions

### 1.1 Naming

| Rule | Example |
|---|---|
| DocType names are singular, Title Case, prefixed only when they could clash with ERPNext or HRMS | `Forecourt Shift` (HRMS already has `Shift Type`), `Fuel Tank`, `Nozzle` |
| Child tables start with the parent's short name | `Shift Meter Reading`, `Tank Calibration Row` |
| Fieldnames are `snake_case`, units in the name where useful | `capacity_l`, `dip_mm`, `variance_pct` |
| Custom fields on ERPNext DocTypes are prefixed `fms_` | `fms_forecourt_shift`, `fms_is_fuel` |
| Document names include the globally unique station code | `SH-KE-NBO-WSTL-2026-00042` |

### 1.2 Attribute shorthand

Each DocType section has an **attributes** table using the DocType JSON property names, so a developer or agent can set them directly.

| Property | Meaning |
|---|---|
| `module` | Module the DocType belongs to |
| `istable` / `issingle` / `is_tree` / `is_submittable` | Child table / single / tree / submittable |
| `autoname` | Naming rule (`field:x`, `format:…`, `hash`, `autoincrement`) |
| `title_field`, `show_title_field_in_link` | What is shown in links |
| `search_fields` | Extra fields shown and searched in link dropdowns |
| `sort_field`, `sort_order` | Default list order (v16 default is `creation desc`) |
| `track_changes` | Version history |
| `quick_entry`, `editable_grid` | Quick entry dialog; inline editing of child rows |
| `in_create` | Users cannot create from the UI (system-written records) |

### 1.3 Field table columns

`Fieldname · Type · Options · Flags · Notes`. Flags: **R** required, **RO** read only, **U** unique, **I** search index, **L** in list view, **F** in standard filter, **H** hidden, **FE** fetched (`fetch_from`), **D** default.

### 1.4 Permission shorthand

`R` read · `W` write · `C` create · `D` delete · `S` submit · `X` cancel · `A` amend · `Rp` report · `E` export · `P` print. Row-level restriction is by **User Permission** on Station and Company (design guide section 14.2). Permissions listed are role permissions at level 0.

---

## 2. Modules and roles

### 2.1 Modules

| Module | Folder | Contains |
|---|---|---|
| Forecourt Setup | `forecourt/forecourt_setup/` | Settings, Station, Station Group, reference masters |
| Wetstock | `forecourt/wetstock/` | Tanks, charts, dispensers, nozzles, dips, transfers, meter changes, GRN delivery dips |
| Forecourt Shift | `forecourt/forecourt_shift/` | Shift templates, Forecourt Shift and its child tables, price changes, corrections |
| Forecourt Finance | `forecourt/forecourt_finance/` | Ledgers, customer vehicles, finance reports |
| Forecourt Integrations | `forecourt/forecourt_integrations/` | Payment providers, Integration Inbox, Payment Feed Entry, imports |

### 2.2 Roles

#### Custom FMS roles (created as fixtures)

| Role | Desk access | Purpose |
|---|---|---|
| Business Executive | Yes | Group-level dashboards and reports; read-only across companies |
| Station Manager | Yes | Daily operations at their station(s); shift oversight |
| Assistant Station Manager | Yes | Day-to-day operations; deputises for Station Manager |
| Forecourt Supervisor | Yes | Shift supervision; nozzle and tank entry |
| Forecourt Sales Operator | Yes | Sales entry, meter readings, own-use recording |
| Site Cashier | Yes | Cash reconciliation on Desk; collection entry |
| Station Accountant | Yes | Reconciliation, GRN invoices, period close |
| Integration Service Account | No (API only) | M-Pesa, pump controllers, eTIMS integrations |

Integration accounts: create one dedicated service user per integration (M-Pesa, pump controller, eTIMS) with narrowly scoped permissions rather than sharing a single privileged account.

#### Standard ERPNext / Frappe roles (reused, not recreated as fixtures)

Assign these to FMS users where their permissions match the intended responsibilities. Verify each role's permission set in your installed version before assigning.

| Role | Typically assigned to |
|---|---|
| Sales User | Station Manager, Forecourt Sales Operator |
| Sales Manager | Station Manager, Area Manager |
| Stock User | Station Manager, Forecourt Supervisor |
| Stock Manager | Station Accountant |
| Accounts User | Station Accountant |
| Accounts Manager | Station Accountant (senior) |
| Employee | All staff users (HRMS integration) |
| HR User | Station Accountant, HR staff |
| HR Manager | Head-office HR staff |
| Customer | Customer portal users |
| Supplier | Supplier portal users |

---

## 3. Dependency map

```
Level 0  Forecourt Settings · Forecourt Company Settings · Station Group · Variance Reason
         Expense Type · Own Use Purpose · Payment Provider
            │
Level 1  Station (+ Station Payment Terminal)
            │
Level 2  Fuel Tank · Dispenser · Customer Vehicle (+ Customer Vehicle Driver)
            │
Level 3  Tank Calibration Chart (+ Tank Calibration Row) · Nozzle
            │
Level 4  Forecourt Shift Template (+ Shift Template Cashier, Shift Template Nozzle)
         Fuel Price Change (+ Fuel Price Change Item) · Meter Change · Tank Dip · Tank Transfer
         GRN Delivery Dip (child table used on Purchase Receipt)
            │
Level 5  Forecourt Shift (+ Shift Price, Shift Meter Reading, Shift Tank Dip, Shift Cashier,
         Shift Cash Count, Shift Credit Sale, Shift Item Sale, Shift Collection, Shift Resolution)
            │
Level 6  Wetstock Ledger Entry · Nozzle Ledger Entry · Sales Ledger Entry · Cashier Ledger Entry
         Shift Correction (+ Shift Correction Item)

Integrations (depend on Level 1; Payment Import Batch is built in Phase 1 with task J01,
the inbox and feeds in Phase 3):
         Integration Inbox · Payment Feed Entry · Payment Import Batch
```

### 3.1 Forward links

Frappe refuses to save a DocType or Custom Field whose Link points to a DocType that does not exist yet. These fields point to a DocType built later, so the task that builds the target adds them:

| Field | On | Links to | Added in task |
|---|---|---|---|
| `last_reading_shift` | Nozzle | Forecourt Shift | FMS-F01 |
| `fms_forecourt_shift` | Sales Invoice, POS Invoice, Delivery Note, Payment Entry, Journal Entry, Stock Entry, Stock Reconciliation, Purchase Receipt | Forecourt Shift | FMS-F01 |
| `applied_to_shift` | Fuel Price Change | Forecourt Shift | FMS-F07 |
| `import_batch` | Shift Collection | Payment Import Batch | FMS-J01 |
| `feed_entry` | Shift Collection | Payment Feed Entry | FMS-J04 |
| `superseded_by`, `correction` | the four ledgers | Shift Correction | FMS-G01 |

Ledger rows written by the Purchase Receipt hook (E03), Tank Dip (E06) and Meter Change (E08) are wired in FMS-F15, when the ledger DocTypes exist. All DocTypes that carry role permissions depend on the roles (FMS-C01).

---

## 4. Level 0: settings and simple masters

### 4.1 Forecourt Settings

Global defaults for the whole site. Company-specific values live in Forecourt Company Settings.

| Attribute | Value |
|---|---|
| module | Forecourt Setup |
| issingle | 1 |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W · System Manager: R W · all FMS roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| accountable_person_label | Select | Cashier / Salesperson | D Cashier | Label used in the UI |
| dip_entry_mode | Select | Depth via calibration chart / Litres entered directly | D chart | Default for stations |
| record_elec_cash | Check | | D 1 | Meters recorded by default |
| record_elec_meter | Check | | D 0 | |
| record_man_meter | Check | | D 0 | |
| sales_basis | Select | Elec Cash / Elec Meter / Man Meter / Highest | D Elec Cash | Must be a recorded meter (validated) |
| drift_tolerance_pct | Percent | | D 0.5 | |
| drift_tolerance_l | Float | | D 2 | |
| drift_requires_reason | Check | | D 1 | |
| price_change_mode | Select | Latest price with segments / Between shifts only | D Latest | |
| allow_estimated_segments | Check | | D 0 | Design guide 6.5a |
| background_close_threshold | Int | | D 200 | Payment rows above which close runs as a job |
| allow_backdated_shift_days | Int | | D 2 | |
| require_meter_reading_photo | Check | | D 0 | |
| require_expense_receipt | Check | | D 1 | |

**Controller:** `validate`: `sales_basis` must be one of the recorded meters; at least one meter recorded (FMS-M603).

### 4.2 Forecourt Company Settings

| Attribute | Value |
|---|---|
| module | Forecourt Setup |
| autoname | `field:company` |
| title_field | company |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · Forecourt Accountant: R W · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| company | Link | Company | R U | |
| staff_shortage_receivable_account | Link | Account | R | Must accept party type Employee; account type confirmed in FMS-C03 (design guide D17) |
| cash_short_account | Link | Account | R | Expense |
| cash_over_account | Link | Account | R | Income |
| fuel_stock_variance_account | Link | Account | R | Expense |
| delivery_shortage_claims_account | Link | Account | R | Current asset, **not** Receivable type (a Stock Entry cannot carry a party; design guide D18) |
| voucher_clearing_account | Link | Account | | |
| tank_tolerance_pct | Percent | | D 0.5 | |
| tank_tolerance_l | Float | | D 20 | |
| approval_multiplier | Float | | D 2 | Approval needed above tolerance × this |
| cumulative_tolerance_pct | Percent | | D 0.3 | Rolling 30 days |
| delivery_tolerance_pct | Percent | | D 0.3 | |
| small_difference_pct | Percent | | D 0.1 | Write-off limit without approval |
| small_difference_amount | Currency | | | Alternative fixed limit |
| post_tank_variance | Select | Every shift with dips / Last shift of day / Outside tolerance only | D Every shift | |
| sales_posting_mode | Select | Shift summary / Per transaction | D Shift summary | Design guide 12.3 |
| credit_invoicing | Select | Per customer per shift / Monthly | D Per shift | Monthly: the shift posts Delivery Notes (design guide D26) |
| price_cross_check_amount | Currency | | D 1 | Meter amount vs volume × price (design guide 5.6) |
| float_after_shift | Select | Stays in till / Returned to safe | D Stays in till | Design guide 7.5, D27 |
| allow_overlapping_shifts | Check | | D 0 | When set, FMS-S110 is skipped (D28) |
| temperature_compensation | Check | | D 0, RO | Reserved for backlog epic P7; Phases 0–3 only record temperature and density (D30) |

**Controller:** `validate`: every account belongs to `company` and has the right root and account type (FMS-M602).
**Whitelisted method:** `create_default_accounts` (button *Create default accounts*): creates any missing FMS account of design guide 8.1 under the company's chart and fills the mapping; code in `forecourt/setup/`.

### 4.3 Station Group

| Attribute | Value |
|---|---|
| module | Forecourt Setup |
| is_tree | 1 (`nsm_parent_field` = `parent_station_group`) |
| autoname | `field:station_group_name` |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · all FMS roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station_group_name | Data | | R U | |
| group_type | Select | Brand / Region / Area / Portfolio / Other | R | |
| parent_station_group | Link | Station Group | I | |
| is_group | Check | | | |
| lft, rgt, old_parent | Int / Int / Link | | H RO | Required by the tree |

**Fixture record:** root `All Station Groups`.
**Permission hook:** `has_permission` and `permission_query_conditions` expand a User Permission on a Station Group to all descendant stations (design guide 14.2). In v16 `has_permission` must return `True` explicitly.

### 4.4 Variance Reason

| Attribute | Value |
|---|---|
| module | Forecourt Setup |
| autoname | `field:reason` |
| quick_entry | 1 |
| Permissions | Forecourt Administrator: R W C D · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| reason | Data | | R U L | e.g. Dip error, Suspected leak, Meter fault |
| applies_to_tank | Check | | L | |
| applies_to_cashier | Check | | L | |
| applies_to_delivery | Check | | L | |
| applies_to_drift | Check | | L | |
| requires_approval | Check | | L | Always routes to the Area Manager |
| disabled | Check | | | |

**Fixtures:** Dip error, Suspected leak, Suspected theft, Meter fault, Temperature, Delivery, Counting error, Drive-off (cashier), Spillage (tank), Unknown (design guide D31).

### 4.5 Expense Type

| Attribute | Value |
|---|---|
| module | Forecourt Setup |
| autoname | `field:expense_type` |
| Permissions | Forecourt Administrator, Forecourt Accountant: R W C D · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| expense_type | Data | | R U L | Cleaning, Water, Minor repair… |
| accounts | Table | Expense Type Account | R | One row per company |
| max_per_line | Currency | | | Above this, the line is blocked (FMS-S109) |
| receipt_required | Check | | D 1 | |
| disabled | Check | | | |

**Child table `Expense Type Account`** (`istable` 1): `company` Link Company R · `expense_account` Link Account R.

### 4.6 Own Use Purpose

| Attribute | Value |
|---|---|
| module | Forecourt Setup |
| autoname | `field:purpose` |
| Permissions | Forecourt Administrator, Forecourt Accountant: R W C D · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| purpose | Data | | R U L | Generator, Company vehicle, Staff vehicle, Other |
| accounts | Table | Own Use Purpose Account | R | One expense account per company |
| requires_vehicle | Check | | | Vehicle or asset mandatory on the Stock Entry |
| disabled | Check | | | |

**Child table `Own Use Purpose Account`**: `company` Link Company R · `expense_account` Link Account R.

### 4.7 Payment Provider

| Attribute | Value |
|---|---|
| module | Forecourt Integrations |
| autoname | `field:provider_name` |
| Permissions | Forecourt Administrator: R W C D · Forecourt Accountant: R W · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| provider_name | Data | | R U L | M-Pesa, EVC Plus, Visa/Mastercard (Acquirer X)… |
| provider_type | Select | Mobile Money / Card / Voucher / Bank | R L | |
| mode_of_payment | Link | Mode of Payment | R | Its company accounts are the clearing accounts |
| country | Link | Country | | |
| adapter | Data | | | Phase 3. Name of an adapter module under `forecourt_integrations/payment_adapters/`, validated against the adapter registry. Provider names stay out of core DocType JSON (CLAUDE.md 5.11) |
| import_format | Select | None / CSV mapping / Excel mapping | | Phase 1 statement import |
| import_mapping | JSON | | | Column mapping for the statement import |
| reference_pattern | Data | | | Optional regex to validate references |
| disabled | Check | | | |

---

## 5. Level 1: Station

### 5.1 Station

| Attribute | Value |
|---|---|
| module | Forecourt Setup |
| autoname | `field:station_code` |
| title_field | station_name, `show_title_field_in_link` 1 |
| search_fields | station_name, company, station_group |
| track_changes | 1 |
| image_field | — |
| Permissions | Forecourt Administrator: R W C D · Area Manager, Station Manager, Accountant, Director, Investor: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station_code | Data | | R U L | Globally unique, e.g. `KE-NBO-WSTL` (pattern validated) |
| station_name | Data | | R L | |
| company | Link | Company | R I L F | |
| station_group | Link | Station Group | R I F | Leaf or group |
| brand | Data | | F | |
| region | Data | | F | |
| country | Link | Country | R F | |
| ownership_type | Select | Company-owned / Dealer-owned / Investor-owned / Franchise | R F | |
| timezone | Autocomplete | (time zones) | R | Shift windows use it |
| status | Select | Active / Inactive | D Active, L F | |
| *Section: Stock* | | | | |
| warehouse_group | Link | Warehouse | R | Group warehouse; tank warehouses are created under it |
| shop_warehouse | Link | Warehouse | | Non-fuel stock |
| price_list | Link | Price List | R | Selling, station-specific |
| walk_in_customer | Link | Customer | RO | Created on insert: *Walk-in – {station_name}* |
| cost_center | Link | Cost Center | R | Default cost centre |
| *Section: Cash* | | | | |
| till_accounts | Table | Station Till Account | R | One per currency |
| safe_account | Link | Account | R | |
| cash_in_transit_account | Link | Account | | |
| default_float | Currency | | | |
| *Section: Payments* | | | | |
| payment_terminals | Table | Station Payment Terminal | | Tills and card terminals |
| *Section: Policy overrides* (blank = use settings) | | | | |
| dip_entry_mode | Select | (blank) / Depth via calibration chart / Litres entered directly | | |
| record_elec_cash, record_elec_meter, record_man_meter | Check | | | Overrides; a "use settings" check controls whether they apply |
| use_settings_meters | Check | | D 1 | |
| sales_basis | Select | (blank) / Elec Cash / Elec Meter / Man Meter / Highest | | |
| price_change_mode | Select | (blank) / Latest price with segments / Between shifts only | | |
| tank_tolerance_pct, tank_tolerance_l | Percent / Float | | | Override company tolerances (blank = company) |
| delivery_dips_required | Check | | D 1 | The only place this setting lives (design guide 5.4) |

**Child table `Station Till Account`**: `currency` Link Currency R · `account` Link Account R (Cash type, same company).

**Child table `Station Payment Terminal`**: `provider` Link Payment Provider R · `till_or_terminal` Data R · `default_cashier` Link Employee · `active` Check D 1. Unique per provider + till (validated).

**Controller:**
- `validate`: code pattern `^[A-Z]{2}-[A-Z0-9]{2,5}-[A-Z0-9]{2,6}$` (FMS-M601); accounts and warehouses belong to `company` (FMS-M602); meter overrides consistent with the sales basis (FMS-M603).
- `after_insert`: create the walk-in customer (code in `forecourt/setup/`, design guide D34). The Accounting Dimension links to Station, so no dimension value has to be created.

**Indexes:** `company`, `station_group`.

---

## 6. Level 2: physical equipment and customer vehicles

### 6.1 Fuel Tank

| Attribute | Value |
|---|---|
| module | Wetstock |
| autoname | `format:{station}-{tank_code}` |
| title_field | tank_label |
| search_fields | station, item |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · Station Manager, Area Manager: R · Accountant: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R I L F | |
| company | Link | Company | FE station.company, RO I | |
| tank_code | Data | | R | T1, T2… |
| tank_label | Data | | | e.g. "T1 PMS 30k" |
| item | Link | Item | R L F | Filter: `fms_is_fuel` = 1 |
| warehouse | Link | Warehouse | RO U | Created on insert under the station's warehouse group |
| capacity_l | Float | | R | |
| safe_fill_l | Float | | | Default 95% of capacity |
| dead_stock_l | Float | | | |
| manifold_group | Data | | | Tanks with the same value are reconciled together |
| dip_entry_mode | Select | (blank) / Depth via calibration chart / Litres entered directly | | Overrides the station |
| tolerance_pct, tolerance_l | Percent / Float | | | Overrides company settings |
| status | Select | Active / Out of service / Decommissioned | D Active, L F | |

**Controller:**
- `validate`: item is fuel; capacity > 0; safe fill ≤ capacity (FMS-M604).
- `after_insert`: create the Warehouse with `warehouse_name` = `{tank_code} - {station_code}` (non-group, parent = station warehouse group; code in `forecourt/setup/`); ERPNext appends the company abbreviation, so the record is named `T1 - KE-NBO-WSTL - DPL`; set `warehouse`.
- `on_trash`: blocked if any stock ledger entry exists for the warehouse.

### 6.2 Dispenser

| Attribute | Value |
|---|---|
| module | Wetstock |
| autoname | `format:{station}-{dispenser_code}` |
| title_field | dispenser_code |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · operations roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R I L F | |
| dispenser_code | Data | | R L | D01, D02… |
| island | Data | | L F | Island 1… |
| make, model, serial_no | Data | | | |
| meters_override | Check | | | Older pumps without electronic meters |
| record_elec_cash, record_elec_meter, record_man_meter | Check | | depends_on meters_override | |
| sales_basis | Select | Elec Cash / Elec Meter / Man Meter / Highest | depends_on meters_override, R when override | Must be one of this dispenser's recorded meters (FMS-M603; design guide D23) |
| status | Select | Active / Out of service | D Active, L F | |

### 6.3 Customer Vehicle

| Attribute | Value |
|---|---|
| module | Forecourt Finance |
| autoname | `format:{customer}-{plate_no}` |
| title_field | plate_no, `show_title_field_in_link` 1 |
| search_fields | customer, plate_no |
| quick_entry | 1 |
| track_changes | 1 |
| Permissions | Station Manager, Accountant: R W C · Forecourt Administrator: R W C D · Area Manager: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| customer | Link | Customer | R I L F | |
| plate_no | Data | | R L | Normalised to upper case without spaces |
| description | Data | | | Make, model |
| allowed_items | Table MultiSelect | Customer Vehicle Item | | Blank = any fuel |
| monthly_limit_l | Float | | | |
| drivers | Table | Customer Vehicle Driver | | |
| active | Check | | D 1, L F | |

Child tables: `Customer Vehicle Item` (`item` Link Item) · `Customer Vehicle Driver` (`driver_name` Data R, `id_no` Data, `phone` Data).

**Indexes:** unique (`customer`, `plate_no`) via the name; `plate_no` search index.

---

## 7. Level 3: equipment details

### 7.1 Tank Calibration Chart

| Attribute | Value |
|---|---|
| module | Wetstock |
| autoname | `format:CAL-{tank}-{valid_from}` |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · operations roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| tank | Link | Fuel Tank | R I L F | |
| valid_from | Date | | R L | |
| source | Data | | | Calibration company, certificate number |
| certificate | Attach | | | |
| rows | Table | Tank Calibration Row | R | Product chart |
| water_rows | Table | Tank Calibration Row | | Optional water chart |
| max_depth_mm | Float | | RO | Computed |
| max_volume_l | Float | | RO | Computed |

**Child table `Tank Calibration Row`**: `depth_mm` Float R · `volume_l` Float R. `editable_grid` 1. Bulk paste from spreadsheet supported by the standard grid upload.

**Controller:** `validate`: depths and volumes strictly increasing (FMS-M605); warn if `max_volume_l` differs from tank capacity by more than 2%. Interpolation lives in `forecourt/calc/calibration.py` (pure Python).

### 7.2 Nozzle

| Attribute | Value |
|---|---|
| module | Wetstock |
| autoname | `format:{dispenser}-N{nozzle_no}` |
| title_field | nozzle_label |
| search_fields | dispenser, tank, item |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · operations roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| dispenser | Link | Dispenser | R I L F | |
| station | Link | Station | FE dispenser.station, RO I F | |
| nozzle_no | Int | | R L | |
| nozzle_label | Data | | | e.g. "D01 N1 PMS" |
| tank | Link | Fuel Tank | R L F | Filter: same station |
| item | Link | Item | FE tank.item, RO L | |
| ecash_max, evol_max, mvol_max | Float | | | Rollover maxima per meter |
| decimals_volume, decimals_cash | Int | | D 2 | |
| last_ecash, last_evol, last_mvol | Float | | RO | Updated by shift close and Meter Change |
| last_reading_shift | Link | Forecourt Shift | RO | Added in FMS-F01 (section 3.1) |
| max_test_volume_l | Float | | | Per-shift pump test limit; blank = no limit (FMS-S115, design guide D29) |
| status | Select | Active / Out of service | D Active, L F | |

**Controller:** `validate`: tank belongs to the same station (FMS-M606); `last_*` fields are only writable by system code (`self.flags.from_fms`, FMS-M607).

---

## 8. Level 4: station transactions outside the shift

### 8.1 Forecourt Shift Template

| Attribute | Value |
|---|---|
| module | Forecourt Shift |
| autoname | `format:{station}-{template_name}` |
| title_field | template_name |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · Station Manager: R W · Area Manager: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R I L F | |
| template_name | Data | | R L | Day, Night… |
| start_time | Time | | R L | |
| end_time | Time | | R L | May be earlier than start (overnight) |
| dips_required | Check | | D 1 | |
| sequence | Int | | | Order within the day |
| cashiers | Table | Shift Template Cashier | | Roster |
| nozzle_assignments | Table | Shift Template Nozzle | | |
| active | Check | | D 1 | |

Child tables: `Shift Template Cashier` (`cashier` Link Employee R, filter `fms_is_forecourt_cashier`; `float_amount` Currency) · `Shift Template Nozzle` (`nozzle` Link Nozzle R; `cashier` Link Employee R; `attendant` Link Employee).

### 8.2 Fuel Price Change

| Attribute | Value |
|---|---|
| module | Forecourt Shift |
| is_submittable | 1 |
| autoname | `format:FPC-{station}-{YYYY}-{#####}` |
| track_changes | 1 |
| Workflow | Draft → Pending Approval → Approved (submit) / Rejected |
| Permissions | Station Manager: R W C · Area Manager: R W C S · Forecourt Director: R S · Accountant: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R I L F | |
| company | Link | Company | FE station.company, RO | |
| effective_at | Datetime | | R L | Default now; may not be later than the moment of submission (design guide D24) |
| reason | Small Text | | R | Regulator change, supplier change… |
| reference | Data | | | Regulator notice number |
| items | Table | Fuel Price Change Item | R | |
| applied_to_shift | Link | Forecourt Shift | RO | Set on submit when a segment is added; added in FMS-F07 |

**Child `Fuel Price Change Item`**: `item` Link Item R · `old_price` Currency RO · `new_price` Currency R.

**Controller:** `on_submit`: write Item Price on the station price list (valid_from = effective date; Item Price has no time, so a `validate` hook on Sales Invoice and POS Invoice sets fuel rates from the Fuel Price Change in force at the posting date and time, section 12); in *Latest price with segments* mode, add a segment to the open shift and mark its nozzles as needing change-time readings. `on_cancel`: blocked once a shift using the segment is closed.

### 8.3 Meter Change

| Attribute | Value |
|---|---|
| module | Wetstock |
| is_submittable | 1 |
| autoname | `format:MC-{station}-{YYYY}-{#####}` |
| Permissions | Station Manager: R W C S · Area Manager: R W C S X · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| nozzle | Link | Nozzle | R I L | |
| station | Link | Station | FE nozzle.station, RO I | |
| changed_at | Datetime | | R | |
| technician | Data | | R | |
| reason | Select | Replacement / Reset / Calibration / Repair | R | |
| old_final_ecash, old_final_evol, old_final_mvol | Float | | | |
| new_start_ecash, new_start_evol, new_start_mvol | Float | | | |
| certificate | Attach | | | |

**Controller:** `on_submit`: update `Nozzle.last_*` to the new start values; write a Nozzle Ledger Entry of type *Meter Change* through `posting/ledgers.py` (wired in FMS-F15). Validation: no open shift may straddle `changed_at` without a segment.

### 8.4 Tank Dip (spot dip)

| Attribute | Value |
|---|---|
| module | Wetstock |
| is_submittable | 1 |
| autoname | `format:DIP-{station}-{YYYY}-{#####}` |
| Permissions | Station Manager, Area Manager: R W C S · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| tank | Link | Fuel Tank | R I L | |
| station | Link | Station | FE tank.station, RO I | |
| dipped_at | Datetime | | R L | |
| dip_entry_mode | Data | | FE / computed, RO | |
| dip_mm, water_mm | Float | | | Chart mode |
| volume_l, water_l | Float | | | Computed in chart mode, entered in litres mode |
| book_volume_l | Float | | RO | From the stock ledger at `dipped_at` |
| difference_l | Float | | RO | |
| dipped_by, witness | Link | Employee / User | | |
| purpose | Select | Audit / Handover / Pre-delivery check / Other | | |
| temperature_c, density | Float / Float | | | Optional, recorded only (design guide D30) |

Does not post stock. Writes a Wetstock Ledger Entry of type *Spot Dip* for analysis through `posting/ledgers.py` (wired in FMS-F15).

### 8.5 Tank Transfer

| Attribute | Value |
|---|---|
| module | Wetstock |
| is_submittable | 1 |
| autoname | `format:TT-{station}-{YYYY}-{#####}` |
| Permissions | Station Manager: R W C · Area Manager: R W C S X |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| from_tank, to_tank | Link | Fuel Tank | R | Same item and station |
| volume_l | Float | | R | |
| transferred_at | Datetime | | R | |
| reason | Small Text | | R | |
| stock_entry | Link | Stock Entry | RO | Material Transfer created on submit |

### 8.6 GRN Delivery Dip (child table on Purchase Receipt)

| Attribute | Value |
|---|---|
| module | Wetstock |
| istable | 1 |
| editable_grid | 1 |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| tank | Link | Fuel Tank | R | Must match the item row's warehouse |
| item | Link | Item | FE tank.item, RO | |
| dip_entry_mode | Data | | RO | |
| dip_before_mm, dip_after_mm | Float | | | Chart mode |
| volume_before_l, volume_after_l | Float | | R (litres mode) / RO (chart mode) | |
| sales_during_drop_l | Float | | | From nozzle readings at start and end of the drop |
| received_l | Float | | RO | after − before + sales during drop |
| invoiced_l | Float | | RO | Sum of GRN item rows for this tank |
| variance_l, variance_pct | Float / Percent | | RO | |
| reason | Link | Variance Reason | | Required beyond tolerance (FMS-T205) |
| temperature_c, density | Float / Float | | | Optional, recorded only (design guide D30) |
| shortage_stock_entry | Link | Stock Entry | RO | Set when *Record delivery shortage* is used |

Added to Purchase Receipt as the custom field `fms_delivery_dips` (section 12).

---

## 9. Level 5: Forecourt Shift

### 9.1 Forecourt Shift

| Attribute | Value |
|---|---|
| module | Forecourt Shift |
| is_submittable | 1 |
| autoname | `format:SH-{station}-{YYYY}-{#####}` |
| title_field | shift_title (e.g. "Westlands · Day · 2026-10-20") |
| search_fields | station, shift_date, shift_template, status |
| sort_field / sort_order | shift_start / desc |
| track_changes | 1 |
| editable_grid (children) | 1 |
| Status | `status` is set by the controller: Open → Counting → Reconciled → (Pending Approval) → Closing → Closed (submit). Corrected is set by Shift Correction. |
| Workflow | *Forecourt Shift Approval* on `approval_state` only: Not Required / Pending Approval → Approved or Rejected (design guide 6.2, D19) |
| Permissions | Station Manager: R W C S P · Area Manager: R W S P (approval transition) · Accountant: R P Rp E · Director, Investor: R Rp · Forecourt Administrator: R W C D S · System Manager: X (whole-shift cancellation only, design guide 6.8) |

**Header fields**

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R I L F | Default from user's station |
| company | Link | Company | FE station.company, RO I F | |
| shift_template | Link | Forecourt Shift Template | R F | Filter by station |
| shift_date | Date | | R I L F | Date of `shift_start` in the station's time zone (design guide D20) |
| shift_start, shift_end | Datetime | | R | From template and date, station time zone |
| status | Select | Open / Counting / Reconciled / Pending Approval / Closing / Closed / Corrected | RO L F, allow_on_submit | Set by the controller |
| approval_state | Select | Not Required / Pending Approval / Approved / Rejected | RO F | Workflow state field; set to Pending Approval or Not Required by the controller, moved by the approval workflow |
| approved_by_user | Link | User | RO | Set by the *Approve* transition; must differ from the preparer |
| previous_shift | Link | Forecourt Shift | RO | Found on insert |
| shift_title | Data | | RO H | |
| dip_entry_mode, sales_basis, price_change_mode | Data | | RO | Snapshot of the station's effective settings at creation; tanks and dispensers may override (rows carry their own values) |
| record_elec_cash, record_elec_meter, record_man_meter | Check | | RO | Snapshot of the station default; a column is shown when any row records that meter |

**Tables (tabs in this order)**

| Tab | Fieldname | Child DocType |
|---|---|---|
| Prices | prices | Shift Price |
| Meters | meter_readings | Shift Meter Reading |
| Tanks | tank_dips | Shift Tank Dip |
| Credit | credit_sales | Shift Credit Sale |
| Items | item_sales | Shift Item Sale |
| Cashiers | cashiers, cash_counts, collections | Shift Cashier, Shift Cash Count, Shift Collection |
| Review | resolutions | Shift Resolution |

**Totals (read only)**: `total_fuel_volume`, `total_fuel_amount`, `total_item_amount`, `total_credit`, `total_mobile`, `total_card`, `total_cash`, `total_expenses`, `total_difference`, `total_tank_variance_l`, `posting_summary` (HTML, the reconciliation summary).

**Controller outline**

| Event | Behaviour |
|---|---|
| `before_insert` | Find previous shift; copy roster; create reading rows (opening values locked); create tank rows; create first price segment; snapshot settings |
| `validate` | Recompute everything through `forecourt/calc/*`; set `status` and `approval_state`; run gates that apply to drafts (continuity, ranges) |
| `before_submit` | All gates FMS-S1xx, FMS-T2xx, FMS-W1xx (design guide 6.6) |
| `on_submit` | `forecourt/posting/*` builds and submits native documents, then writes the four ledgers; updates `Nozzle.last_*` |
| `on_cancel` | Allowed only with System Manager + director approval flag and only for the latest shift (FMS-C503); cancels generated docs in reverse order; marks ledgers cancelled |
| `on_update_after_submit` | Only `status` (Corrected) may change |

**Indexes:** (`station`, `shift_start`), (`company`, `shift_date`), `status`.

**Connections (dashboard):** Sales Invoice, Delivery Note, Payment Entry, Journal Entry, Stock Entry, Stock Reconciliation, Purchase Receipt (by `fms_forecourt_shift`), Shift Correction, ledger entries.

### 9.2 Child tables of Forecourt Shift

All are `istable` 1, `editable_grid` 1, module Forecourt Shift.

**Shift Price**

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| item | Link | Item | R RO | |
| segment_no | Int | | RO | 1, 2… per item |
| price | Currency | | RO | |
| effective_from, effective_to | Datetime | | RO | |
| fuel_price_change | Link | Fuel Price Change | RO | Blank for the opening segment |

**Shift Meter Reading** (one row per nozzle × cashier × price segment)

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| nozzle | Link | Nozzle | R RO | |
| tank, item | Link | Fuel Tank / Item | FE, RO | |
| cashier | Link | Employee | R | |
| attendant | Link | Employee | | Information only |
| segment_no | Int | | RO | |
| price | Currency | | RO | From the segment |
| rec_elec_cash, rec_elec_meter, rec_man_meter | Check | | RO | Meters recorded for this nozzle (dispenser override, else station); drive `mandatory_depends_on` of the closings |
| row_sales_basis | Data | | RO | Sales basis for this nozzle (dispenser override, else station) |
| opening_elec_cash, closing_elec_cash | Float | | depends_on rec_elec_cash | Opening RO |
| opening_elec_meter, closing_elec_meter | Float | | depends_on rec_elec_meter | |
| opening_man_meter, closing_man_meter | Float | | depends_on rec_man_meter | |
| rollover_elec_cash, rollover_elec_meter, rollover_man_meter | Check | | | |
| basis_meter | Data | | RO | Which meter drove sales |
| basis_volume_l | Float | | RO | |
| test_volume_l | Float | | | |
| own_use_l | Float | | RO | Pulled from Fuel Own Use entries |
| net_volume_l | Float | | RO | |
| amount | Currency | | RO | |
| drift_evol_mvol_l, drift_ecash_evol_l, drift_ecash_mvol_l | Float | | RO | |
| drift_breach | Check | | RO | 1 when any drift pair exceeds the tolerance; gates check this before requiring a reason |
| drift_reason | Link | Variance Reason | | Required when `drift_breach = 1` and `drift_requires_reason` is on |
| photo | Attach Image | | | Mandatory when settings require |
| source | Select | Manual / Handheld / FCC / Import | D Manual | |

**Shift Tank Dip**

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| tank | Link | Fuel Tank | R RO | |
| item | Link | Item | FE, RO | |
| dip_entry_mode | Data | | RO | Effective mode for this tank (tank override, else station) |
| opening_l | Float | | RO | Previous closing dip |
| receipts_l | Float | | RO | Pulled from GRNs |
| sales_l | Float | | RO | From readings |
| own_use_l | Float | | RO | |
| transfers_l | Float | | RO | |
| expected_l | Float | | RO | |
| dip_mm, water_mm | Float | | | Chart mode |
| dip_l, water_l | Float | | | Entered in litres mode, computed in chart mode |
| variance_l, variance_pct | Float / Percent | | RO | |
| within_tolerance | Check | | RO | |
| needs_approval | Check | | RO | 1 when variance exceeds tolerance × approval_multiplier, or reason requires approval |
| reason | Link | Variance Reason | | Required outside tolerance |
| approved_by | Link | User | RO | Set by the approval transition; must differ from last editor (segregation of duties) |
| temperature_c, density | Float / Float | | | Optional, recorded only (design guide D30) |
| source | Select | Manual / ATG / Import | D Manual | |

**Shift Cashier**

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| cashier | Link | Employee | R | |
| float_amount | Currency | | | |
| fuel_amount, item_amount, debt_receipts | Currency | | RO | |
| expected | Currency | | RO | |
| cash_counted | Currency | | RO | Sum of Shift Cash Count rows, base currency |
| mobile, card, credit, voucher, expenses, drops | Currency | | RO | Sums of collections |
| accounted | Currency | | RO | |
| difference | Currency | | RO | |
| resolved | Check | | RO | Difference fully covered by resolution lines |

**Shift Cash Count** (Frappe child tables cannot nest, so counts are a sibling table keyed by cashier)

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| cashier | Link | Employee | R | |
| currency | Link | Currency | R | |
| denomination | Currency | | | Optional |
| count | Int | | | |
| amount | Currency | | R | count × denomination, or typed |
| exchange_rate | Float | | RO | |
| base_amount | Currency | | RO | |

**Shift Credit Sale**

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| cashier | Link | Employee | R | |
| customer | Link | Customer | R | |
| vehicle | Link | Customer Vehicle | | Filter by customer |
| driver | Data | | | |
| item | Link | Item | R | |
| nozzle | Link | Nozzle | | Optional, improves reporting |
| qty | Float | | R | Litres or units |
| rate | Currency | | RO | From the price segment at `sold_at` |
| amount | Currency | | RO | |
| slip_no | Data | | R | Unique per customer (validated) |
| sold_at | Datetime | | | |
| odometer | Int | | | |
| over_limit | Check | | RO | 1 when this cashier's running total exceeds the customer's credit limit |
| over_limit_approved_by | Link | User | RO | |
| sales_invoice | Link | Sales Invoice | RO | Set on close (Sales Invoice mode) |
| delivery_note | Link | Delivery Note | RO | Set on close (monthly invoicing mode) |

**Shift Item Sale**

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| cashier | Link | Employee | R | |
| item | Link | Item | R | Non-fuel |
| qty, rate, amount | Float / Currency / Currency | | R | Rate from station price list |
| warehouse | Link | Warehouse | | Default station shop warehouse |
| pos_doctype | Select | POS Invoice / Sales Invoice | RO | ERPNext v16 POS creates either (design guide D25) |
| pos_invoice | Dynamic Link | pos_doctype | RO | Set when pulled from POS (then excluded from posting) |

**Shift Collection** (one row per mobile money or card transaction, per drop, per expense, per voucher, per debt receipt)

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| cashier | Link | Employee | R | |
| collection_type | Select | Mobile Money / Card / Voucher / Expense / Drop / Debt Receipt | R | |
| paid_by | Select | Cash / Mobile Money / Card | depends_on Debt Receipt, D Cash | Design guide 7.2, D21 |
| provider | Link | Payment Provider | depends_on Mobile/Card, or Debt Receipt not paid in cash | |
| mode_of_payment | Link | Mode of Payment | FE provider.mode_of_payment | |
| till_or_terminal | Data | | | |
| reference | Data | | R for Mobile/Card and non-cash Debt Receipt, I | Unique per provider across the site (FMS-S114) |
| transaction_time | Datetime | | | |
| payer | Data | | | Phone or masked card |
| customer | Link | Customer | depends_on Debt Receipt | |
| expense_type | Link | Expense Type | depends_on Expense | |
| amount | Currency | | R | |
| attachment | Attach | | | Receipt image |
| feed_entry | Link | Payment Feed Entry | RO | When from a feed; added in FMS-J04 |
| import_batch | Link | Payment Import Batch | RO | When from an import; added in FMS-J01 |
| payment_entry | Link | Payment Entry | RO | Set on close |

**Shift Resolution**

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| resolution_for | Select | Cashier / Tank / Drift / Credit / Delivery | R | |
| cashier | Link | Employee | depends_on Cashier | |
| tank | Link | Fuel Tank | depends_on Tank | |
| action | Select | Charge to cashier / Write off / Record excess / Accept variance / Approve over-limit | R | |
| amount | Currency | | | |
| volume_l | Float | | | |
| reason | Link | Variance Reason | R | |
| note | Small Text | | R when the reason requires | |
| needs_approval | Check | | RO | |
| approved_by | Link | User | RO | |
| journal_entry | Link | Journal Entry | RO | Set on close |

---

## 10. Level 6: ledgers and corrections

The four ledgers share these attributes:

| Attribute | Value |
|---|---|
| module | Forecourt Finance (Wetstock Ledger Entry in Wetstock) |
| autoname | `hash` |
| in_create | 1 |
| track_changes | 0 |
| Permissions | All FMS desk roles: R Rp E · no W/C/D for anyone (written by code with `ignore_permissions`) |
| Common fields | `company` (I), `station` (I), `posting_date` (I), `forecourt_shift` (I), `voucher_type`, `voucher_no` (I), `is_cancelled`, `superseded_by` (Link Shift Correction), `correction` (Link Shift Correction); the last two are added in FMS-G01 |
| Writers | Only `forecourt/posting/ledgers.py` and `forecourt/corrections/` |
| Composite indexes | (`station`, `posting_date`), (`company`, `posting_date`), plus the per-ledger ones below, created in `on_doctype_update` |

### 10.1 Wetstock Ledger Entry

Extra fields: `tank` (I), `item`, `entry_type` (Shift / Delivery / Spot Dip / Transfer / Meter Change / Adjustment), `shift_start`, `shift_end`, `opening_l`, `receipt_l`, `sales_l`, `test_l`, `own_use_l`, `transfer_l`, `expected_l`, `dip_l`, `variance_l`, `variance_pct`, `invoiced_l`, `delivery_variance_l`, `supplier`, `transporter`, `driver`, `cashiers`, `reason`, `approved_by`, `dip_entry_mode`, `source`, `valuation_rate`, `variance_value`.
Composite index: (`tank`, `posting_date`).

### 10.2 Nozzle Ledger Entry

Extra fields: `shift_template`, `island`, `dispenser`, `nozzle` (I), `tank`, `item`, `cashier` (I), `attendant`, `segment_no`, `price`, `opening_*`/`closing_*` for each meter, `ecash_delta`, `evol_delta`, `mvol_delta`, `basis_meter`, `gross_l`, `test_l`, `own_use_l`, `net_l`, `amount`, the three drift fields, `source`.
Composite index: (`nozzle`, `posting_date`).

### 10.3 Sales Ledger Entry

Extra fields: `shift_template`, `cashier` (I), `item` (I), `item_group`, `is_fuel`, `nozzle`, `dispenser`, `island`, `tank`, `payment_type` (Cash / Mobile Money / Card / Credit / Voucher), `mode_of_payment`, `customer`, `customer_vehicle`, `qty`, `amount`, `basis` (Exact / Attributed).
Composite indexes: (`item`, `posting_date`), (`cashier`, `posting_date`).

### 10.4 Cashier Ledger Entry

Extra fields: `cashier` (I), `fuel_l`, `fuel_amount`, `item_amount`, `debt_receipts`, `float_amount`, `cash`, `mobile`, `card`, `credit`, `voucher`, `expenses`, `drops`, `expected`, `accounted`, `difference`, `resolution_action`, `resolution_amount`, `reason`.
Composite index: (`cashier`, `posting_date`).

### 10.5 Shift Correction

| Attribute | Value |
|---|---|
| module | Forecourt Shift |
| is_submittable | 1 |
| autoname | `format:COR-{forecourt_shift}-{##}` |
| track_changes | 1 |
| Workflow | Draft → Pending Director Approval → Approved → Applied (submit) / Rejected |
| Permissions | Station Manager, Area Manager: R W C · Forecourt Director: R W S (approve, apply) · Accountant: R · Forecourt Administrator: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| forecourt_shift | Link | Forecourt Shift | R I L | Must be submitted |
| station, company | Link | | FE, RO I | |
| correction_type | Select | Native document / Meter reading / Dip / Cashier count / Reclassification / Whole-shift cancellation | R L | |
| reason | Small Text | | R | |
| evidence | Attach | | | |
| items | Table | Shift Correction Item | R | |
| next_shift | Link | Forecourt Shift | RO | Affected by meter corrections |
| resolutions | Table | Shift Resolution | | New differences created by the correction |
| approved_by | Link | User | RO | |
| applied_documents | Small Text | | RO | List of cancelled, amended and new documents |

**Child `Shift Correction Item`**: `target_type` (Select: Meter Reading / Tank Dip / Credit Sale / Collection / Cash Count / Resolution / Document) · `target_row` (Data, child row name) · `target_doctype` (Link DocType) · `target_name` (Dynamic Link) · `field` (Data) · `old_value` (Data, RO) · `new_value` (Data, R).

**Controller:** `on_submit` (apply) runs the correction in one transaction (design guide 6.8): cancel and amend native documents, write superseding ledger rows, adjust the next shift, set the shift status to *Corrected*. `on_cancel`: not allowed; a wrong correction is fixed by another correction.

---

## 11. Integrations

### 11.1 Integration Inbox

| Attribute | Value |
|---|---|
| module | Forecourt Integrations |
| autoname | `hash` |
| in_create | 1 |
| track_changes | 0 |
| Permissions | Forecourt Administrator, Forecourt Accountant: R W (retry button) · System Manager: R W D |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| provider | Link | Payment Provider | R I L F | Or device bridge in Phase 5 |
| direction | Select | In / Out | R L F | |
| message_type | Data | | L F | e.g. c2b_confirmation, settlement_file, atg_reading |
| external_id | Data | | R I | Unique together with provider (composite unique index) |
| payload | JSON | | R | |
| status | Select | Received / Processed / Failed / Ignored | R I L F | |
| error | Long Text | | | |
| attempts | Int | | D 0 | |
| processed_doctype | Link | DocType | | |
| processed_name | Dynamic Link | processed_doctype | | |
| received_at | Datetime | | R I | |

### 11.2 Payment Feed Entry

| Attribute | Value |
|---|---|
| module | Forecourt Integrations |
| autoname | `hash` |
| in_create | 1 |
| Permissions | Accountant, Station Manager: R W (assign cashier) · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| provider | Link | Payment Provider | R I L F | |
| station | Link | Station | I L F | Resolved from till mapping |
| till_or_terminal | Data | | R I | |
| reference | Data | | R I | Unique with provider |
| transaction_time | Datetime | | R I L | |
| amount | Currency | | R L | |
| payer | Data | | | |
| cashier | Link | Employee | | From terminal default or manual |
| status | Select | Unmatched / Matched / Ignored | R I L F | |
| forecourt_shift | Link | Forecourt Shift | RO I | |
| inbox | Link | Integration Inbox | RO | |

### 11.3 Payment Import Batch

Phase 1 statement import (before feeds exist).

| Attribute | Value |
|---|---|
| module | Forecourt Integrations |
| autoname | `format:IMP-{station}-{YYYY}-{#####}` |
| Permissions | Station Manager, Accountant: R W C |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R | |
| forecourt_shift | Link | Forecourt Shift | | Target shift (optional; else matched by time) |
| provider | Link | Payment Provider | R | Its `import_mapping` is used |
| file | Attach | | R | CSV or Excel export |
| rows_read, rows_created, rows_duplicate, rows_rejected | Int | | RO | |
| log | Long Text | | RO | Row-level errors |

**Whitelisted method:** `forecourt.forecourt_integrations.statement_import.run(batch)` parses the file and creates Shift Collection rows (or Payment Feed Entries when no shift is given), skipping duplicates by reference. (The module is not named `import.py` because `import` is a Python keyword.)

---

## 12. Custom fields and records on ERPNext DocTypes

All shipped as fixtures (`Custom Field`, `Property Setter`) filtered by `module = Forecourt …`. Prefix `fms_`. The `fms_forecourt_shift` fields are added in FMS-F01 (section 3.1).

| DocType | Custom fields | Purpose |
|---|---|---|
| Item | `fms_is_fuel` (Check, I) | Fuel items |
| Employee | `fms_is_forecourt_cashier` (Check, I), `fms_default_station` (Link Station) | Cashier selection |
| Customer | `fms_is_walk_in` (Check), `fms_station` (Link Station) | Walk-in customer per station |
| Sales Invoice | `fms_forecourt_shift` (Link, I, RO), `fms_cashier` (Link Employee, I) | Generated invoices, and POS sales when POS creates Sales Invoices |
| Delivery Note | `fms_forecourt_shift` (Link, I, RO), `fms_cashier` (Link Employee) | Credit sales when the company invoices monthly (design guide D26) |
| POS Invoice | `fms_forecourt_shift` (Link, I), `fms_cashier` (Link Employee, I) | Pulling shop sales |
| Payment Entry | `fms_forecourt_shift` (Link, I, RO), `fms_cashier` (Link Employee), `fms_provider` (Link Payment Provider), `fms_till_or_terminal` (Data), `fms_transaction_time` (Datetime) | Per-transaction reconciliation; `reference_no` and `reference_date` are standard |
| Journal Entry | `fms_forecourt_shift` (Link, I, RO) | Resolutions and expenses |
| Stock Reconciliation | `fms_forecourt_shift` (Link, I, RO) | Tank variance |
| Stock Entry | `fms_forecourt_shift` (Link, I), `fms_nozzle` (Link Nozzle), `fms_attendant` (Link Employee), `fms_use_purpose` (Link Own Use Purpose), `fms_vehicle_or_asset` (Data), `fms_purchase_receipt` (Link Purchase Receipt) | Fuel Own Use and delivery shortage; `station` is the accounting dimension field (added by fixture, not a custom field) |
| Purchase Receipt | `fms_delivery_note_no`, `fms_truck`, `fms_driver`, `fms_transporter` (Link Supplier), `fms_seals`, `fms_witness` (Link Employee), `fms_delivery_dips` (Table → GRN Delivery Dip), `fms_forecourt_shift` (Link, RO, set when pulled into a shift) | Manual GRN with dips; `station` is the accounting dimension field (added by fixture, not a custom field) |

**Records shipped as fixtures**

| DocType | Record | Notes |
|---|---|---|
| Accounting Dimension | Station (document_type = Station) | Adds `station` to all GL-posting DocTypes and GL Entry |
| Stock Entry Type | Fuel Own Use (purpose Material Issue) | Section 5.10 of the design guide |
| Role | The seven FMS roles | |
| Workflow, Workflow State, Workflow Action Master | Forecourt Shift Approval (on `approval_state`), Fuel Price Change, Shift Correction | |
| Variance Reason, Own Use Purpose | Default lists | |
| Number Card, Dashboard Chart, Workspace | Section 13 and 14 | |

**Controller hooks on ERPNext DocTypes** (`doc_events` in `hooks.py`, never class overrides)

| DocType | Event | FMS handler |
|---|---|---|
| Purchase Receipt | `validate` | Compute delivery dips; require dips for fuel lines when the station requires them (FMS-T206); reason beyond tolerance (FMS-T205) |
| Purchase Receipt | `on_submit` / `on_cancel` | Write / cancel Wetstock Ledger Entry (Delivery) through `posting/ledgers.py` (wired in FMS-F15); block cancel if a closed shift used the GRN |
| Stock Entry | `validate` | For *Fuel Own Use*: mandatory narration, purpose, nozzle; expense account from purpose |
| Stock Entry | `on_cancel` | Block if a closed shift used it |
| Payment Entry, Sales Invoice, Delivery Note, Journal Entry, Stock Reconciliation | `on_cancel` | Block when `fms_forecourt_shift` is set, unless the cancel comes from a Shift Correction (`frappe.flags.fms_correction`) (FMS-C502) |
| POS Invoice, Sales Invoice | `validate` | For fuel items at a station: set the rate from the Fuel Price Change in force at the posting date and time (design guide D24). For POS sales: default `fms_cashier` from the Employee whose `user_id` is the POS user |

---

## 13. Reports, number cards and charts

### 13.1 Reports

| Report | Type | Module | Main source |
|---|---|---|---|
| Shift Report | Print Format (Forecourt Shift) | Forecourt Shift | Shift document |
| Daily Station Report | Script | Forecourt Shift | Ledgers |
| Sales by Product | Script | Forecourt Finance | Sales Ledger |
| Sales by Tank | Script | Wetstock | Sales Ledger, Wetstock Ledger |
| Sales by Pump and Nozzle | Script | Wetstock | Nozzle Ledger, Sales Ledger |
| Sales by Shift | Script | Forecourt Shift | Sales Ledger |
| Sales by Cashier | Script | Forecourt Finance | Sales Ledger, Cashier Ledger |
| Payment Mix Matrix | Script (pivot) | Forecourt Finance | Sales Ledger |
| Tank Stock Position | Script | Wetstock | Stock Ledger, Wetstock Ledger |
| Wetstock Variance | Script | Wetstock | Wetstock Ledger |
| Delivery Variance | Script | Wetstock | Wetstock Ledger (Delivery) |
| Meter Drift | Script | Wetstock | Nozzle Ledger |
| Cashier Statement | Script | Forecourt Finance | Cashier Ledger, GL (Staff Shortage Receivable) |
| Cashier Variance Ranking | Script | Forecourt Finance | Cashier Ledger |
| Credit Slips Register | Query | Forecourt Finance | Shift Credit Sale |
| Clearing Account Ageing | Script | Forecourt Finance | Payment Entry, GL |
| Cash Position by Station | Script | Forecourt Finance | GL |
| Exception Register | Script | Forecourt Shift | Shift Resolution, Shift Correction, approvals |
| Run-out Forecast | Script | Wetstock | Stock Ledger, Sales Ledger |
| Station Comparison | Script | Forecourt Finance | All ledgers |
| Open Items | Script | Forecourt Shift | Draft shifts, draft GRNs, unmatched feeds |
| FMS Health | Script (emailed daily) | Forecourt Setup | Various |

### 13.2 Number cards

| Card | DocType / method | Function | Filter |
|---|---|---|---|
| Open shifts | Forecourt Shift | Count | docstatus 0 |
| Shifts awaiting approval | Forecourt Shift | Count | status Pending Approval |
| Litres sold today | Nozzle Ledger Entry | Sum net_l | posting_date today, not cancelled |
| Fuel sales today | Sales Ledger Entry | Sum amount | today, is_fuel 1 |
| Tank variance this month (L) | Wetstock Ledger Entry | Sum variance_l | this month, entry_type Shift |
| Cash short this month | Cashier Ledger Entry | Sum difference where < 0 | this month (custom method) |
| Unmatched payments | Payment Feed Entry | Count | status Unmatched |
| Corrections pending | Shift Correction | Count | Pending Director Approval |
| Tanks below reorder | Custom method | | Run-out within 2 days |

### 13.3 Dashboard charts

| Chart | Type | Source |
|---|---|---|
| Litres per day by product (30 days) | Line | Nozzle Ledger Entry, group by item |
| Payment mix (30 days) | Donut | Sales Ledger Entry, group by payment_type |
| Cumulative tank variance % | Line | Custom method over Wetstock Ledger |
| Cashier differences (30 days) | Bar | Cashier Ledger Entry, group by cashier |
| Delivery variance by supplier | Bar | Wetstock Ledger Entry (Delivery) |
| Station comparison: litres per day | Bar | Nozzle Ledger Entry, group by station |

All cards and charts respect User Permissions, so the same card shows one station to a manager and the whole group to a director.

---

## 14. Workspaces and navigation

### 14.1 Workspace tree (sidebar)

In v16 the Desk sidebar lists workspaces by app; FMS workspaces set `app` = `forecourt` and use `parent_page` for nesting, with `sequence_id` for order. Each public workspace sets `module` and `roles` so it only appears to the right people.

```
Forecourt                      (parent, Station Manager home)
├── Shifts                     (daily operations)
├── Wetstock                   (tanks, pumps, deliveries)
├── Forecourt Finance          (cash, payments, credit)
├── Forecourt Operations       (area manager: approvals, exceptions, comparisons)
├── Forecourt Group            (directors and investors: dashboards)
└── Forecourt Setup            (administrator)
```

### 14.2 Workspace contents

**Forecourt** (module Forecourt Shift; roles Station Manager, Area Manager, Forecourt Administrator; icon `fuel` or nearest available)

| Block | Content |
|---|---|
| Number cards | Open shifts · Litres sold today · Fuel sales today · Unmatched payments |
| Shortcuts | **New Shift** (Forecourt Shift, new) · **Open Shifts** (list, docstatus 0) · **New GRN** (Purchase Receipt, new) · **Fuel Own Use** (Stock Entry, new, type Fuel Own Use) · **Spot Dip** (Tank Dip, new) · **Daily Station Report** |
| Chart | Litres per day by product |
| Quick list | Recent Forecourt Shifts (status, station) |
| Link cards | *Today*: Forecourt Shift, Purchase Receipt (fuel), Stock Entry (Fuel Own Use), Payment Import Batch · *Reports*: Shift Report, Daily Station Report, Open Items |

**Shifts** (module Forecourt Shift; roles Station Manager, Area Manager)

| Block | Content |
|---|---|
| Shortcuts | New Shift · Shifts awaiting approval · Fuel Price Change · Shift Correction |
| Link cards | *Shift*: Forecourt Shift, Forecourt Shift Template, Fuel Price Change, Shift Correction · *Reports*: Sales by Shift, Sales by Cashier, Exception Register |

**Wetstock** (module Wetstock; roles Station Manager, Area Manager, Forecourt Administrator)

| Block | Content |
|---|---|
| Number cards | Tank variance this month (L) · Tanks below reorder |
| Chart | Cumulative tank variance % · Delivery variance by supplier |
| Link cards | *Equipment*: Fuel Tank, Tank Calibration Chart, Dispenser, Nozzle · *Movements*: Purchase Receipt (fuel), Tank Dip, Tank Transfer, Meter Change, Stock Entry (Fuel Own Use) · *Reports*: Tank Stock Position, Wetstock Variance, Delivery Variance, Meter Drift, Sales by Tank, Sales by Pump and Nozzle, Run-out Forecast |

**Forecourt Finance** (module Forecourt Finance; roles Forecourt Accountant, Area Manager, Station Manager read)

| Block | Content |
|---|---|
| Number cards | Unmatched payments · Cash short this month |
| Chart | Payment mix (30 days) · Cashier differences |
| Link cards | *Payments*: Payment Feed Entry, Payment Import Batch, Payment Entry, Bank Reconciliation Tool · *Credit*: Customer, Customer Vehicle, Process Statement of Accounts · *Reports*: Sales by Product, Payment Mix Matrix, Cashier Statement, Clearing Account Ageing, Cash Position by Station, Credit Slips Register, Accounts Receivable |

**Forecourt Operations** (module Forecourt Shift; roles Area Manager, Forecourt Director)

| Block | Content |
|---|---|
| Number cards | Shifts awaiting approval · Corrections pending · Tank variance this month |
| Chart | Station comparison: litres per day |
| Link cards | *Approvals*: Forecourt Shift (Pending Approval), Fuel Price Change (Pending), Shift Correction (Pending) · *Reports*: Exception Register, Station Comparison, Cashier Variance Ranking, Wetstock Variance, Meter Drift |

**Forecourt Group** (module Forecourt Finance; roles Forecourt Director, Forecourt Investor)

| Block | Content |
|---|---|
| Number cards | Fuel sales today · Litres sold today · Cash position (custom) · Receivables (ERPNext card) |
| Charts | Station comparison · Litres per day by product · Payment mix |
| Link cards | *Financials*: Profit and Loss Statement, Balance Sheet, Consolidated Trial Balance, Accounts Receivable · *FMS*: Station Comparison, Daily Station Report, Wetstock Variance |

**Forecourt Setup** (module Forecourt Setup; roles Forecourt Administrator, System Manager)

| Block | Content |
|---|---|
| Link cards | *Settings*: Forecourt Settings, Forecourt Company Settings · *Network*: Station Group, Station · *Masters*: Variance Reason, Expense Type, Own Use Purpose, Payment Provider · *Integrations*: Integration Inbox · *Health*: FMS Health |
| Onboarding | Module Onboarding steps: create company settings → station → tanks → charts → dispensers → nozzles → shift template → first shift |

### 14.3 Other navigation

- **Awesomebar shortcuts:** "New Forecourt Shift", "New GRN" through standard search; `search_fields` above make stations, tanks and nozzles findable by code.
- **Form links:** every child row's link fields open the master; the shift's Connections tab lists generated documents; GRN, Payment Entry and Stock Entry show a "Forecourt Shift" link at the top when set.
- **List view settings:** Forecourt Shift list shows station, date, template, status colour indicator (Open grey, Counting orange, Reconciled blue, Pending Approval red, Closed green, Corrected purple).

---

## 15. Summary table

| # | DocType | Level | Module | Kind | Submittable | Naming |
|---|---|---|---|---|---|---|
| 1 | Forecourt Settings | 0 | Forecourt Setup | Single | | — |
| 2 | Forecourt Company Settings | 0 | Forecourt Setup | Master | | field:company |
| 3 | Station Group | 0 | Forecourt Setup | Tree | | field |
| 4 | Variance Reason | 0 | Forecourt Setup | Master | | field |
| 5 | Expense Type (+ Expense Type Account) | 0 | Forecourt Setup | Master | | field |
| 6 | Own Use Purpose (+ Own Use Purpose Account) | 0 | Forecourt Setup | Master | | field |
| 7 | Payment Provider | 0 | Forecourt Integrations | Master | | field |
| 8 | Station (+ Station Till Account, Station Payment Terminal) | 1 | Forecourt Setup | Master | | field:station_code |
| 9 | Fuel Tank | 2 | Wetstock | Master | | format |
| 10 | Dispenser | 2 | Wetstock | Master | | format |
| 11 | Customer Vehicle (+ Item, Driver) | 2 | Forecourt Finance | Master | | format |
| 12 | Tank Calibration Chart (+ Tank Calibration Row) | 3 | Wetstock | Master | | format |
| 13 | Nozzle | 3 | Wetstock | Master | | format |
| 14 | Forecourt Shift Template (+ Cashier, Nozzle) | 4 | Forecourt Shift | Master | | format |
| 15 | Fuel Price Change (+ Item) | 4 | Forecourt Shift | Transaction | ✓ | format |
| 16 | Meter Change | 4 | Wetstock | Transaction | ✓ | format |
| 17 | Tank Dip | 4 | Wetstock | Transaction | ✓ | format |
| 18 | Tank Transfer | 4 | Wetstock | Transaction | ✓ | format |
| 19 | GRN Delivery Dip | 4 | Wetstock | Child table used on Purchase Receipt (listed here because no FMS DocType owns it) | | — |
| 20 | Forecourt Shift (+ 9 child tables) | 5 | Forecourt Shift | Transaction | ✓ | format |
| 21 | Wetstock Ledger Entry | 6 | Wetstock | Ledger | | hash |
| 22 | Nozzle Ledger Entry | 6 | Forecourt Finance | Ledger | | hash |
| 23 | Sales Ledger Entry | 6 | Forecourt Finance | Ledger | | hash |
| 24 | Cashier Ledger Entry | 6 | Forecourt Finance | Ledger | | hash |
| 25 | Shift Correction (+ Item) | 6 | Forecourt Shift | Transaction | ✓ | format |
| 26 | Integration Inbox | Int | Forecourt Integrations | Log | | hash |
| 27 | Payment Feed Entry | Int | Forecourt Integrations | Log | | hash |
| 28 | Payment Import Batch | Int | Forecourt Integrations | Transaction | | format |

Child tables of FMS DocTypes (20): Expense Type Account, Own Use Purpose Account, Station Till Account, Station Payment Terminal, Customer Vehicle Item, Customer Vehicle Driver, Tank Calibration Row, Shift Template Cashier, Shift Template Nozzle, Fuel Price Change Item, Shift Price, Shift Meter Reading, Shift Tank Dip, Shift Cashier, Shift Cash Count, Shift Credit Sale, Shift Item Sale, Shift Collection, Shift Resolution (also used on Shift Correction), Shift Correction Item.

**Totals:** 28 numbered DocTypes in the table above (27 standalone DocTypes plus GRN Delivery Dip), 20 further child tables, custom fields on 11 ERPNext DocTypes, 22 reports (one is a print format), 9 number cards, 6 charts, 7 workspaces, 3 workflows.

