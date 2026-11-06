# FMS DocType Catalogue

**Version:** 1.2 (grouping of modules and DocTypes, workspaces, dashboards, navigation and shortcuts; proposed non-fuel and Mode B DocTypes listed)
**Date:** 2026-11-06
**App:** `forecourt` (Frappe Framework v16, ERPNext v16, HRMS v16 optional)
**Companion documents:** [fms.md](fms.md) (the design guide: the *why*), [../TASKS.md](../TASKS.md) (the task list: the *build order*), [../CLAUDE.md](../CLAUDE.md) (rules for developers and agents)

This catalogue lists every DocType the FMS app defines, every custom field it adds to ERPNext DocTypes, and how they are grouped in workspaces and navigation. DocTypes are ordered **from least dependent to most dependent**, which is also the order in which they are built (see the task list). A few fields link *forward* to a DocType built later; they are added by the later task (section 3.1). If this catalogue and the design guide disagree on a field name or a DocType name, this catalogue wins. The design guide wins on behaviour.

**Changes in 1.2**

| Change | Where |
|---|---|
| Modules table gains **Forecourt Services** (proposed, from [fms-nonfuel.md](fms-nonfuel.md)) and the Mode B DocTypes in Forecourt Integrations | 2.1 |
| New: **DocTypes grouped by module and by user task**, with where each one is reached in the Desk | 2.3, 2.4 |
| New: **personas mapped to roles**. Workspaces in 1.1 named roles that section 2.2 does not define (Area Manager, Forecourt Administrator, Forecourt Director, Forecourt Investor). 1.2 uses the 2.2 roles and proposes two new ones. | 2.5 |
| Proposed number cards and charts for non-fuel, services and Mode B | 13.2, 13.3 |
| Section 14 rewritten: navigation principles, workspace tree, every workspace's layout, **dashboards**, form navigation, list views, shortcuts, notifications, onboarding, tablet use | 14 |
| Totals: current totals unchanged, proposed totals added | 15 |

**Status marks used in 1.2.** Items marked **(P)** are *proposed*: they come from fms-nonfuel.md (decisions D37 to D62) or from this revision, and are not yet accepted. They are listed so that navigation can be designed once. They are built only after the owner confirms them, and the task list gets their tasks then (prefix FMS-Q, fms-nonfuel.md section 20).

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
14. [Workspaces, dashboards and navigation](#14-workspaces-dashboards-and-navigation)
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

A module is where a DocType's code lives (its folder) and which workspace it belongs to by default. Users never see module names directly: they see workspaces (section 14). The module split therefore follows **who maintains the code**, and the workspace split follows **who does the work**.

| Module | Folder | Contains | Main workspace |
|---|---|---|---|
| Forecourt Setup | `forecourt/forecourt_setup/` | Settings, Station, Station Group, reference masters | Forecourt Setup |
| Wetstock | `forecourt/wetstock/` | Tanks, charts, islands, pumps, nozzles, dips, transfers, meter changes, GRN delivery dips, the Wetstock Ledger. **(P)** Dry Stock Count, the shelf counterpart of Tank Dip | Wetstock |
| Forecourt Shift | `forecourt/forecourt_shift/` | Shift templates, Forecourt Shift and its child tables, price changes, corrections | Forecourt, Shifts |
| Forecourt Finance | `forecourt/forecourt_finance/` | Ledgers (Nozzle, Sales, Cashier), customer vehicles, finance reports. **(P)** Dry Stock Ledger Entry | Forecourt Finance |
| Forecourt Integrations | `forecourt/forecourt_integrations/` | Payment providers, Integration Inbox, Payment Feed Entry, imports. **(P)** Forecourt Device, FCC Transaction (Mode B) | Devices and Integrations |
| **(P)** Forecourt Services | `forecourt/forecourt_services/` | Service Type, Service Job (car wash, tyre services), from fms-nonfuel.md section 8 | Shop and Services |

Six modules (five accepted, one proposed). Seven workspaces in 1.1, nine in 1.2, ten with the proposals (section 14.2). A module can feed more than one workspace (Forecourt Shift feeds *Forecourt* and *Shifts*), and a workspace can show DocTypes from several modules (*Shop and Services* shows Wetstock's Dry Stock Count next to Forecourt Services).

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

### 2.3 DocTypes by module

Every FMS DocType, grouped by module, with its kind and the place a user reaches it from. Child tables are listed under their parent. *Ws* is the workspace (section 14), *Dash* a dashboard (14.5), *Form* a button or the Connections tab of another form (14.6).

**Forecourt Setup**

| DocType | Kind | Reached from |
|---|---|---|
| Forecourt Settings | Single | Ws Forecourt Setup |
| Forecourt Company Settings | Master | Ws Forecourt Setup |
| Station Group | Tree | Ws Forecourt Setup |
| Station (+ Station Till Account, Station Payment Terminal, **(P)** Station Stock Location) | Master | Ws Forecourt Setup; awesomebar by station code; every station-linked form |
| Variance Reason | Master | Ws Forecourt Setup |
| Expense Type (+ Expense Type Account) | Master | Ws Forecourt Setup |
| Own Use Purpose (+ Own Use Purpose Account) | Master | Ws Forecourt Setup |
| **(P)** Stock Adjustment Reason (+ Stock Adjustment Reason Account) | Master | Ws Forecourt Setup |
| **(P)** LPG Product | Master | Ws Shop and Services |

**Wetstock**

| DocType | Kind | Reached from |
|---|---|---|
| Fuel Tank | Master | Ws Wetstock; Form: Station Connections |
| Tank Calibration Chart (+ Tank Calibration Row) | Master | Ws Wetstock; Form: Fuel Tank Connections |
| Island | Master | Ws Wetstock; Form: Station Connections |
| Pump | Master | Ws Wetstock; Form: Island Connections |
| Nozzle | Master | Ws Wetstock; Form: Pump and Fuel Tank Connections |
| Meter Change | Transaction | Ws Wetstock; Form: Nozzle button *Meter Change* |
| Tank Dip | Transaction | Ws Forecourt (*Spot Dip*), Ws Wetstock; Form: Fuel Tank button *Spot Dip* |
| Tank Transfer | Transaction | Ws Wetstock |
| GRN Delivery Dip | Child of Purchase Receipt | Purchase Receipt form, *Fuel Delivery* section |
| Wetstock Ledger Entry | Ledger | Reports only (Wetstock Variance, Tank Stock Position) |
| **(P)** Dry Stock Count (+ Dry Stock Count Item) | Transaction | Ws Shop and Services; Ws Forecourt Operations (*Spot Audit*) |

**Forecourt Shift**

| DocType | Kind | Reached from |
|---|---|---|
| Forecourt Shift Template (+ Shift Template Cashier, Shift Template Nozzle, **(P)** Shift Template Item Assignment) | Master | Ws Shifts |
| Fuel Price Change (+ Fuel Price Change Item) | Transaction | Ws Shifts, Ws Forecourt Operations (approval) |
| Forecourt Shift (+ Shift Price, Shift Meter Reading, Shift Tank Dip, Shift Cashier, Shift Cash Count, Shift Credit Sale, Shift Item Sale, Shift Collection, Shift Resolution; **(P)** Shift Stock Count, Shift Stock Count Detail, Shift Service, Shift FCC Exception) | Transaction | Ws Forecourt (*New Shift*, *Open Shifts*), Ws Shifts; Form: Station button *New Shift* |
| Shift Correction (+ Shift Correction Item) | Transaction | Ws Shifts; Form: Forecourt Shift button *Correct* |

**Forecourt Finance**

| DocType | Kind | Reached from |
|---|---|---|
| Customer Vehicle (+ Customer Vehicle Item, Customer Vehicle Driver) | Master | Ws Forecourt Finance; Form: Customer Connections |
| Nozzle Ledger Entry | Ledger | Reports only |
| Sales Ledger Entry | Ledger | Reports only |
| Cashier Ledger Entry | Ledger | Reports only (Cashier Statement) |
| **(P)** Dry Stock Ledger Entry | Ledger | Reports only |

**Forecourt Integrations**

| DocType | Kind | Reached from |
|---|---|---|
| Payment Provider | Master | Ws Devices and Integrations |
| Integration Inbox | Log | Ws Devices and Integrations; FMS Health |
| Payment Feed Entry | Log | Ws Forecourt Finance (*Unmatched payments*); Form: Shift Collection row |
| Payment Import Batch | Transaction | Ws Forecourt (*Import Payments*), Ws Forecourt Finance |
| **(P)** Forecourt Device | Master | Ws Devices and Integrations; Form: Station Connections |
| **(P)** FCC Transaction | Log | Ws Devices and Integrations; Form: Forecourt Shift (*Unpaid fuel*), Nozzle Connections |

**(P) Forecourt Services**

| DocType | Kind | Reached from |
|---|---|---|
| Service Type (+ Service Type Consumable) | Master | Ws Shop and Services |
| Service Job (+ Service Job Line, Service Job Part) | Transaction | Ws Shop and Services (*New Service Job*), Ws Forecourt; Form: Forecourt Shift *Services* tab |

**ERPNext DocTypes the FMS puts in its workspaces** (not FMS DocTypes, opened with FMS filters or Stock Entry types): Purchase Receipt (fuel and shop GRNs), Stock Entry (*Fuel Own Use*, **(P)** *Dry Stock Adjustment*, *Service Consumption*), Sales Invoice, Delivery Note, POS Invoice, Payment Entry, Journal Entry, Customer, Item, Item Price, Bank Reconciliation Tool, Process Statement of Accounts, Employee.

### 2.4 DocTypes by user task

The same DocTypes, grouped the way people think about their work. Workspaces (section 14) are laid out in these groups, so a user looks for a *task*, not a *module*.

| Task group | When | DocTypes and records | Workspace |
|---|---|---|---|
| **Run the shift** | Every shift | Forecourt Shift; Payment Import Batch; Tank Dip (spot); **(P)** Dry Stock Count (Handover) | Forecourt, Shifts |
| **Receive stock** | Each delivery | Purchase Receipt (fuel, with GRN Delivery Dips; shop items); Stock Entry (delivery shortage) | Forecourt, Wetstock, Shop and Services |
| **Record what is not a sale** | When it happens | Stock Entry: Fuel Own Use; **(P)** Dry Stock Adjustment; Tank Transfer; Meter Change | Forecourt, Wetstock, Shop and Services |
| **Sell services** **(P)** | During the day | Service Job | Shop and Services |
| **Change prices** | When EPRA or the company changes them | Fuel Price Change; Item Price | Shifts |
| **Approve** | Daily | Forecourt Shift (Pending Approval), Fuel Price Change, Shift Correction, **(P)** large adjustments | Forecourt Operations |
| **Fix a closed shift** | Rarely | Shift Correction | Shifts |
| **Money and credit** | Daily, monthly | Payment Feed Entry, Payment Entry, Customer, Customer Vehicle, Sales Invoice (credit), bank reconciliation | Forecourt Finance |
| **Check stock** | Daily, monthly | Tank Dip, **(P)** Dry Stock Count (Spot Audit, Full Stock Take), stock reports | Wetstock, Shop and Services, Forecourt Operations |
| **Watch devices** **(P)** | Mode B, daily | Forecourt Device, FCC Transaction, Integration Inbox | Devices and Integrations |
| **Set up a station** | Once, then rarely | Station, Fuel Tank, Tank Calibration Chart, Island, Pump, Nozzle, Forecourt Shift Template, masters, settings | Forecourt Setup |
| **See how the business is doing** | Daily, weekly | Reports, dashboards | Forecourt Group, dashboards |

### 2.5 Personas, roles and home workspaces

fms.md section 14.1 and section 2.2 above use different role names (fms-nonfuel.md review item R21). Workspaces are built on the **2.2 roles**. The table maps each persona to them, so every workspace's `roles` list is something that actually exists.

| Persona | Role(s) in 2.2 | Name in fms.md 14.1 | Home workspace (`default_workspace`) |
|---|---|---|---|
| Station manager | Station Manager, Assistant Station Manager | Station Manager | **Forecourt** |
| Shift supervisor | Forecourt Supervisor | (Supervisor) | **Shifts** |
| Cashier on the Desk | Site Cashier | Forecourt Cashier | **My Shift** |
| Sales operator, attendant | Forecourt Sales Operator | (Forecourt Cashier) | **My Shift** |
| Accountant | Station Accountant | Station Accountant | **Forecourt Finance** |
| Area manager | **(P) Area Manager** (new custom role) | Area Manager | **Forecourt Operations** |
| Director, investor | Business Executive | Forecourt Director, Forecourt Investor | **Forecourt Group** |
| Administrator | **(P) Forecourt Administrator** (new custom role), System Manager | Forecourt Administrator | **Forecourt Setup** |
| Integration user | Integration Service Account | | none (API only) |

**Proposed role additions (P).** *Area Manager* and *Forecourt Administrator* are used throughout the design guide (approvals, masters) and have no 2.2 role. Approvals in particular need a role that is not the Station Manager (segregation of duties, design guide 6.2). They are added to the role fixtures when R21 is settled. *Business Executive* covers both directors and investors for workspace access; the director's approval of Shift Corrections is a workflow permission given to the users concerned. Some DocType permission rows in sections 8 and 10 (Fuel Price Change, Shift Correction) still use the fms.md names *Area Manager*, *Forecourt Director* and *Accountant*; they are renamed to the 2.2 roles in the same change that settles R21.

**Setting the home workspace.** The user's **default workspace** is set when the user is created, from the first matching role in the table above (a small `after_insert` hook on User, or set by the administrator). The user can change it. *To verify in the build task:* the exact v16 field name for the user's default workspace and default app.

---

## 3. Dependency map

```
Level 0  Forecourt Settings · Forecourt Company Settings · Station Group · Variance Reason
         Expense Type · Own Use Purpose · Payment Provider
            │
Level 1  Station (+ Station Payment Terminal)
            │
Level 2  Fuel Tank · Island · Pump · Customer Vehicle (+ Customer Vehicle Driver)
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
| sales_basis | Select | Elec Cash / Elec Mtr / Man Mtr / Highest | D Elec Cash | Must be a recorded meter (validated) |
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
| Permissions | Forecourt Administrator: R W C D · Station Accountant: R W · others: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| company | Link | Company | R U | |
| staff_shortage_receivable_account | Link | Account | R | Account type **Payable**, root type Liability — ERPNext maps party type Employee → Payable (D17, decided in FMS-C03) |
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
| Permissions | Forecourt Administrator, Station Accountant: R W C D · others: R |

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
| Permissions | Forecourt Administrator, Station Accountant: R W C D · others: R |

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
| Permissions | Forecourt Administrator: R W C D · Station Accountant: R W · others: R |

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
| sales_basis | Select | (blank) / Elec Cash / Elec Mtr / Man Mtr / Highest | | |
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
| opening_dip_l | Float | | | Opening stock in litres |
| opening_dip_date | Date | | | Date of opening dip reading |
| status | Select | Active / Out of service / Decommissioned | D Active, L F | |

**Controller:**
- `validate`: item is fuel; capacity > 0; safe fill ≤ capacity (FMS-M604); opening dip fields blocked from change once a Stock Ledger Entry exists for the tank's warehouse (FMS-M610).
- `after_insert`: create the Warehouse with `warehouse_name` = `{tank_code} - {station_code}` (non-group, parent = station warehouse group; code in `forecourt/setup/`); ERPNext appends the company abbreviation, so the record is named `T1 - KE-NBO-WSTL - DPL`; set `warehouse`.
- `on_trash`: blocked if any stock ledger entry exists for the warehouse (FMS-M608).

### 6.2 Island

| Attribute | Value |
|---|---|
| module | Wetstock |
| autoname | `format:{station}-{island_code}` |
| title_field | island_label |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · operations roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R I L F | |
| company | Link | Company | FE station.company, RO I | |
| island_code | Data | | R L | I01, I02… |
| island_label | Data | | | e.g. "Island 1 (PMS/AGO)" |
| status | Select | Active / Out of service | D Active, L F | |

Island is a physical grouping of two or more pumps on a shared concrete plinth. Used for reporting (how much all pumps on an island sold together) and optionally for cashier assignment (a cashier is responsible for an entire island).

### 6.3 Pump

| Attribute | Value |
|---|---|
| module | Wetstock |
| autoname | `format:{station}-{pump_code}` |
| title_field | pump_code |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · operations roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| station | Link | Station | R I L F | |
| company | Link | Company | FE station.company, RO I | |
| pump_code | Data | | R L | P01, P02… |
| island | Link | Island | L F | Which island this pump belongs to |
| make, model, serial_no | Data | | | |
| meters_override | Check | | | Tick for older pumps without electronic meters |
| record_elec_cash | Check | | depends_on meters_override | Elec Cash meter fitted |
| record_elec_meter | Check | | depends_on meters_override | Elec Mtr fitted |
| record_man_meter | Check | | depends_on meters_override | Man Mtr fitted |
| sales_basis | Select | Elec Cash / Elec Mtr / Man Mtr / Highest | depends_on meters_override, R when override | Must be one of this pump's recorded meters (FMS-M603; design guide D23) |
| status | Select | Active / Out of service | D Active, L F | |

**Controller:** `validate`: when `meters_override` is ticked, the selected `sales_basis` must map to a meter check that is also ticked (FMS-M603).

### 6.4 Customer Vehicle

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
| station | Link | Station | FE tank.station, RO I F | |
| company | Link | Company | FE tank.company, RO I | |
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
| autoname | `format:{pump}-N{nozzle_no}` |
| title_field | nozzle_label |
| search_fields | pump, tank, item |
| track_changes | 1 |
| Permissions | Forecourt Administrator: R W C D · operations roles: R |

| Fieldname | Type | Options | Flags | Notes |
|---|---|---|---|---|
| pump | Link | Pump | R I L F | |
| station | Link | Station | FE pump.station, RO I F | |
| company | Link | Company | FE pump.company, RO I | |
| nozzle_no | Int | | R L | |
| nozzle_label | Data | | | e.g. "P01 N1 PMS" |
| tank | Link | Fuel Tank | R L F | Filter: same station |
| item | Link | Item | FE tank.item, RO L | |
| ecash_max | Float | | | Elec Cash Max — rollover maximum |
| evol_max | Float | | | Elec Mtr Max — rollover maximum |
| mvol_max | Float | | | Man Mtr Max — rollover maximum |
| decimals_volume, decimals_cash | Int | | D 2 | |
| last_ecash | Float | | RO | Last Elec Cash — updated by shift close and Meter Change |
| last_evol | Float | | RO | Last Elec Mtr — updated by shift close and Meter Change |
| last_mvol | Float | | RO | Last Man Mtr — updated by shift close and Meter Change |
| last_reading_shift | Link | Forecourt Shift | RO | Added in FMS-F01 (section 3.1) |
| opening_date | Date | | | Opening reading date (first shift uses this if no prior shift) |
| opening_ecash | Float | | | Opening Elec Cash |
| opening_evol | Float | | | Opening Elec Mtr |
| opening_mvol | Float | | | Opening Man Mtr |
| max_test_volume_l | Float | | | Per-shift pump test limit; blank = no limit (FMS-S115, design guide D29) |
| status | Select | Active / Out of service | D Active, L F | |

**Controller:** `validate`: tank belongs to the same station (FMS-M606); `last_*` fields are only writable by system code (`self.flags.from_fms`, FMS-M607); opening reading fields (`opening_ecash`, `opening_evol`, `opening_mvol`, `opening_date`) are blocked from change once a Nozzle Ledger Entry exists for this nozzle (FMS-M609).

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
| dip_entry_mode, sales_basis, price_change_mode | Data | | RO | Snapshot of the station's effective settings at creation; tanks and pumps may override (rows carry their own values) |
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
| rec_elec_cash, rec_elec_meter, rec_man_meter | Check | | RO | Meters recorded for this nozzle (pump override, else station); drive `mandatory_depends_on` of the closings |
| row_sales_basis | Data | | RO | Sales basis for this nozzle (pump override, else station) |
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

Extra fields: `shift_template`, `island`, `pump`, `nozzle` (I), `tank`, `item`, `cashier` (I), `attendant`, `segment_no`, `price`, `opening_*`/`closing_*` for each meter, `ecash_delta`, `evol_delta`, `mvol_delta`, `basis_meter`, `gross_l`, `test_l`, `own_use_l`, `net_l`, `amount`, the three drift fields, `source`.
Composite index: (`nozzle`, `posting_date`).

### 10.3 Sales Ledger Entry

Extra fields: `shift_template`, `cashier` (I), `item` (I), `item_group`, `is_fuel`, `nozzle`, `pump`, `island`, `tank`, `payment_type` (Cash / Mobile Money / Card / Credit / Voucher), `mode_of_payment`, `customer`, `customer_vehicle`, `qty`, `amount`, `basis` (Exact / Attributed).
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
| Permissions | Forecourt Administrator, Station Accountant: R W (retry button) · System Manager: R W D |

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
| Sales Invoice | `fms_forecourt_shift` (Link, I, RO), `fms_cashier` (Link Employee, I), `fms_fiscal_status` (Select: Pending/Submitted/Failed/Cancelled, RO), `fms_fiscal_receipt_no` (Data, RO), `fms_fiscal_signature` (Small Text, RO), `fms_fiscal_qr` (Small Text, Hidden, RO) | Generated invoices, and POS sales when POS creates Sales Invoices; fiscal fields store eTIMS / KRA receipt data |
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
| Number Card, Dashboard Chart, Workspace, Dashboard | Sections 13 and 14 | |
| Notification, Auto Email Report | Section 14.9 and 14.5 | Disabled by default, enabled per company |
| Module Profile | Forecourt Station Staff, Forecourt Accounts, Forecourt Executive (section 14.11) | |
| Module Onboarding, Onboarding Step | Section 14.10 | |

**Controller hooks on ERPNext DocTypes** (`doc_events` in `hooks.py`, never class overrides)

| DocType | Event | FMS handler |
|---|---|---|
| Purchase Receipt | `validate` | Compute delivery dips; require dips for fuel lines when the station requires them (FMS-T206); reason beyond tolerance (FMS-T205) |
| Purchase Receipt | `on_submit` / `on_cancel` | Write / cancel Wetstock Ledger Entry (Delivery) through `posting/ledgers.py` (wired in FMS-F15); block cancel if a closed shift used the GRN |
| Stock Entry | `validate` | For *Fuel Own Use*: mandatory narration, purpose, nozzle; expense account from purpose |
| Stock Entry | `on_cancel` | Block if a closed shift used it |
| Payment Entry, Sales Invoice, Delivery Note, Journal Entry, Stock Reconciliation | `on_cancel` | Block when `fms_forecourt_shift` is set, unless the cancel comes from a Shift Correction (`frappe.flags.fms_correction`) (FMS-C502) |
| POS Invoice, Sales Invoice | `validate` | For fuel items at a station: set the rate from the Fuel Price Change in force at the posting date and time (design guide D24). For POS sales: default `fms_cashier` from the Employee whose `user_id` is the POS user |
| Sales Invoice | `on_submit` | If `Forecourt Company Settings.fiscal_adapter` is set, enqueue an outbound Integration Inbox row (`fiscal_submit`) which the background worker sends to the fiscal adapter (eTIMS, ZATCA, etc.) and stores `fms_fiscal_receipt_no`, `fms_fiscal_signature`, `fms_fiscal_qr` on the invoice |
| Sales Invoice | `on_cancel` (fiscal) | If the invoice was fiscalised, enqueue `fiscal_cancel` via Integration Inbox to reverse the fiscal record |

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
| Draft GRNs | Purchase Receipt | Count | docstatus 0, station dimension set (new in 1.2) |
| My open shift (cashier) | Forecourt Shift | Count | docstatus 0, current user's Employee in Shift Cashier (custom method, new in 1.2) |
| My balance (cashier) | Cashier Ledger Entry | Sum of difference | current user's Employee, this month (custom method, new in 1.2) |
| **(P)** Dry stock sales today | Dry Stock Ledger Entry (Mode A), Sales Ledger Entry (Mode B) | Sum | today |
| **(P)** Service sales today | Sales Ledger Entry | Sum amount | today, `quantity_source` Service Job |
| **(P)** Open Service Jobs | Service Job | Count | docstatus 0 |
| **(P)** Items below reorder | Custom method | | ERPNext reorder levels, station locations |
| **(P)** Count exceptions this month | Dry Stock Ledger Entry | Count | this month, flags set |
| **(P)** Live sales now (Mode B) | Sales Invoice | Sum grand_total | today, `fms_sale_source` Device |
| **(P)** Unpaid fuel transactions (Mode B) | FCC Transaction | Count | status Unpaid |
| **(P)** Devices offline (Mode B) | Forecourt Device | Count | Active, `last_seen` older than 10 minutes (custom method) |
| Failed integration messages | Integration Inbox | Count | status Failed (new in 1.2) |

### 13.3 Dashboard charts

| Chart | Type | Source |
|---|---|---|
| Litres per day by product (30 days) | Line | Nozzle Ledger Entry, group by item |
| Payment mix (30 days) | Donut | Sales Ledger Entry, group by payment_type |
| Cumulative tank variance % | Line | Custom method over Wetstock Ledger |
| Cashier differences (30 days) | Bar | Cashier Ledger Entry, group by cashier |
| Delivery variance by supplier | Bar | Wetstock Ledger Entry (Delivery) |
| Station comparison: litres per day | Bar | Nozzle Ledger Entry, group by station |
| Sales by hour today | Bar | Sales Ledger Entry, group by hour (custom method, new in 1.2) |
| **(P)** Sales by stream (30 days): fuel, dry stock, services | Donut | Sales Ledger Entry |
| **(P)** Shop margin by item group (30 days) | Bar | Sales Ledger Entry, GL (custom method) |
| **(P)** Service jobs per day by type | Line | Service Job |
| **(P)** Tank and shelf variance by station | Bar | Wetstock and Dry Stock Ledgers (custom method) |
| **(P)** Unreceipted sales by cashier (Mode B) | Bar | Sales Ledger Entry, `quantity_source` Unreceipted |

All cards and charts respect User Permissions, so the same card shows one station to a manager and the whole group to a director.

---

## 14. Workspaces, dashboards and navigation

The aim of this section: **a user opens the Desk and sees, on one screen, what needs doing now, and reaches any daily task in three clicks or fewer.** It applies Frappe's standard tools (Workspaces, Number Cards, Dashboard Charts, Dashboards, Connections, list settings, Notifications, Module Onboarding, Module Profiles). No custom navigation framework is built.

### 14.1 Navigation principles

| # | Principle | In practice |
|---|---|---|
| U1 | **One home per persona** | Each user lands on the workspace of their role (2.5). A cashier never starts on the setup screen. |
| U2 | **To-do first** | The first shortcuts of a working workspace show live counts (`stats_filter`): *Open Shifts 2*, *Pending Approval 1*, *Unmatched Payments 14*. A count of zero means nothing is waiting. |
| U3 | **Three clicks** | Home → shortcut → document for every daily task. Anything used less than weekly is a link card, not a shortcut. |
| U4 | **Same words everywhere** | *New X* creates. *Open X* lists drafts. *Pending X* lists items waiting for approval. *X Register* lists all. *Approve X* is the approver's list. |
| U5 | **Daily work apart from setup** | Masters are created in *Forecourt Setup*. Working workspaces show a master only as a link where people need to look it up. |
| U6 | **Ledgers are read through reports** | Ledger DocTypes (`in_create`) never appear as shortcuts. Users read them through reports and dashboards. |
| U7 | **Station first** | Each station user has a default Station (User Permission with *Is Default*). New documents fill the station in. Lists, cards and charts show only the user's stations. |
| U8 | **Show only what the user can use** | Workspaces carry `roles`. A Module Profile hides ERPNext modules station staff do not use (14.11). Mode B items live in their own workspace until a station uses them. |
| U9 | **One layout to learn** | Working workspaces: shortcuts, then number cards, then quick list, then link cards. Management workspaces: number cards, then charts, then shortcuts, then link cards. Link cards always in the order *Today*, *Records*, *Reports*, *Setup*. |
| U10 | **No dead ends** | Every generated document links back to its shift. Every master links to its transactions (Connections, 14.6). Every report row opens its source. |

### 14.2 Workspace tree (sidebar)

In v16 the Desk sidebar lists workspaces by app; FMS workspaces set `app` = `forecourt` and use `parent_page` for nesting, with `sequence_id` for order. Each public workspace sets `module` and `roles` so it only appears to the right people.

```
Forecourt                         (parent; Station Manager home)
├── My Shift                      (cashiers and sales operators)                     new in 1.2
├── Shifts                        (supervisor home; shifts, prices, corrections)
├── Wetstock                      (tanks, pumps, deliveries, dips)
├── Shop and Services             (dry stock, counts, Service Jobs, LPG)              (P)
├── Forecourt Finance             (accountant home; payments, cash, credit)
├── Forecourt Operations          (area manager home; approvals, exceptions, audits)
├── Forecourt Group               (executives; dashboards and financials)
├── Devices and Integrations      (inbox, providers, imports; Mode B devices)       new in 1.2
└── Forecourt Setup               (administrator; settings and masters)
```

| seq | Workspace | `module` | `roles` (2.5) | For |
|---|---|---|---|---|
| 1 | Forecourt | Forecourt Shift | Station Manager, Assistant Station Manager, Forecourt Supervisor, (P) Area Manager | Running the station today |
| 2 | My Shift | Forecourt Shift | Site Cashier, Forecourt Sales Operator | A cashier's own shift and statement |
| 3 | Shifts | Forecourt Shift | Station Manager, Assistant Station Manager, Forecourt Supervisor, (P) Area Manager | Shift records, templates, prices, corrections |
| 4 | Wetstock | Wetstock | Station Manager, Assistant Station Manager, Forecourt Supervisor, Station Accountant, (P) Area Manager | Fuel stock and equipment |
| 5 | (P) Shop and Services | Forecourt Services | Station Manager, Assistant Station Manager, Forecourt Supervisor, Forecourt Sales Operator, Site Cashier, (P) Area Manager | Non-fuel stock and services (fms-nonfuel.md). Replaces the *Services* workspace named in fms-nonfuel.md 18.3. |
| 6 | Forecourt Finance | Forecourt Finance | Station Accountant, Station Manager (read), (P) Area Manager | Money, credit, cashier balances |
| 7 | Forecourt Operations | Forecourt Shift | (P) Area Manager, Business Executive (read) | Approvals, exceptions, audits, comparisons |
| 8 | Forecourt Group | Forecourt Finance | Business Executive | Group performance |
| 9 | Devices and Integrations | Forecourt Integrations | (P) Forecourt Administrator, Station Accountant, Station Manager (read) | Integration health; Mode B devices |
| 10 | Forecourt Setup | Forecourt Setup | (P) Forecourt Administrator, System Manager | Settings, network, equipment, masters |

**Icons.** Each workspace sets an icon from the v16 icon set, chosen once and reused on its dashboard: fuel pump (Forecourt), user (My Shift), clock (Shifts), droplet (Wetstock), shopping bag (Shop and Services), wallet (Finance), check-circle (Operations), bar chart (Group), plug (Devices and Integrations), settings (Setup). *To verify in the build task:* the nearest names in the installed icon set.

### 14.3 Workspace contents

Each workspace is listed with its blocks in screen order. In the shortcut tables, **Count** is the `stats_filter` shown on the shortcut, and **Colour** follows 14.4.

#### Forecourt (Station Manager home)

| Block | Content |
|---|---|
| Shortcuts | see table |
| Number cards | Open shifts · Litres sold today · Fuel sales today · Unmatched payments |
| Chart | Sales by hour today (or Litres per day by product) |
| Quick list | Forecourt Shift: last 5, with station, template and status |
| Link cards | *Today*: Forecourt Shift, Purchase Receipt (fuel), Stock Entry (Fuel Own Use), Tank Dip, Payment Import Batch · *Records*: Customer, Customer Vehicle, Fuel Price Change · *Reports*: Shift Report, Daily Station Report, Open Items, Sales by Cashier |

| Shortcut | Opens | Count | Colour |
|---|---|---|---|
| **New Shift** | Forecourt Shift, new | | Blue |
| **Open Shifts** | Forecourt Shift list, docstatus 0 | docstatus 0 | Orange |
| **Pending Approval** | Forecourt Shift list, `approval_state` Pending Approval | same | Red |
| **Import Payments** | Payment Import Batch, new | | Blue |
| **New GRN** | Purchase Receipt, new | | Blue |
| **Draft GRNs** | Purchase Receipt list, docstatus 0 | docstatus 0 | Orange |
| **Fuel Own Use** | Stock Entry, new, type Fuel Own Use | | Blue |
| **Spot Dip** | Tank Dip, new | | Blue |
| **(P) New Service Job** | Service Job, new | | Blue |
| **Daily Station Report** | Report | | Grey |

#### My Shift (cashiers and sales operators) — new in 1.2

Desk users with the Site Cashier or Forecourt Sales Operator role (2.2) see only their own work. Rows are limited to their own Employee by a permission query on the ledgers and a User Permission on Employee.

| Block | Content |
|---|---|
| Shortcuts | **My Open Shift** (Forecourt Shift list where the user's Employee is in Shift Cashier, docstatus 0; count) · **My Statement** (Cashier Statement, filtered to the user) · **My Credit Slips** (Credit Slips Register, filtered) · **Fuel Own Use** (Stock Entry, new, type Fuel Own Use; Forecourt Sales Operator only) · **(P) New Service Job** · **(P) Stock Count** (Dry Stock Count, new, type Handover) |
| Number cards | My open shift · My balance |
| Link cards | *Reports*: Cashier Statement, Sales by Cashier (own) |

In Mode B the cashier works on the PDQ or POS app, not the Desk (fms-nonfuel.md section 11). This workspace stays for statements and for stations still on Mode A.

#### Shifts (supervisor home)

| Block | Content |
|---|---|
| Shortcuts | **New Shift** · **Open Shifts** (count, orange) · **Pending Approval** (count, red) · **Shift Templates** · **New Price Change** (Fuel Price Change, new) · **Pending Price Changes** (count, red) · **Shift Corrections** (list; count of drafts) · **Exception Register** |
| Number cards | Open shifts · Shifts awaiting approval |
| Quick list | Fuel Price Change: last 5 |
| Link cards | *Today*: Forecourt Shift, Fuel Price Change · *Records*: Forecourt Shift Template, Shift Correction · *Reports*: Sales by Shift, Sales by Cashier, Exception Register, Shift Report · *Setup*: Variance Reason, Expense Type |

#### Wetstock

| Block | Content |
|---|---|
| Shortcuts | **New GRN** (fuel) · **Draft GRNs** (count, orange) · **Spot Dip** · **Tank Transfer** · **Meter Change** · **Fuel Own Use** · **Tank Stock Position** · **Wetstock Variance** |
| Number cards | Tank variance this month (L) · Tanks below reorder |
| Charts | Cumulative tank variance % · Delivery variance by supplier |
| Link cards | *Today*: Purchase Receipt (fuel), Tank Dip, Stock Entry (Fuel Own Use) · *Records*: Fuel Tank, Tank Calibration Chart, Island, Pump, Nozzle, Meter Change, Tank Transfer · *Reports*: Tank Stock Position, Wetstock Variance, Delivery Variance, Meter Drift, Sales by Tank, Sales by Pump and Nozzle, Run-out Forecast |

#### (P) Shop and Services

| Block | Content |
|---|---|
| Shortcuts | **New Service Job** · **Open Service Jobs** (count, orange) · **Stock Count** (Dry Stock Count, new) · **Stock Adjustment** (Stock Entry, new, type Dry Stock Adjustment) · **New Shop GRN** (Purchase Receipt, new) · **Shop Stock Position** · **Items below reorder** (count) |
| Number cards | Dry stock sales today · Service sales today · Open Service Jobs · Items below reorder |
| Charts | Sales by stream (30 days) · Service jobs per day by type |
| Link cards | *Today*: Service Job, Dry Stock Count, Stock Entry (Dry Stock Adjustment) · *Records*: Service Type, LPG Product, Item, Item Price, Stock Adjustment Reason · *Reports*: Dry Stock Sales by Cashier, Dry Stock Count Exceptions, Shop Stock Position, Expiry and Batch, Service Sales by Type, Job Ticket Register, Consumables Yield, LPG Cylinder Reconciliation, Slow Movers and Dead Stock |

#### Forecourt Finance (accountant home)

| Block | Content |
|---|---|
| Number cards | Unmatched payments · Cash short this month · Accounts Receivable (ERPNext card) · Failed integration messages |
| Charts | Payment mix (30 days) · Cashier differences (30 days) |
| Shortcuts | **Unmatched Payments** (Payment Feed Entry, status Unmatched; count, orange) · **Import Payments** · **Bank Reconciliation Tool** · **Cashier Statement** · **Credit Slips Register** · **Clearing Account Ageing** · **Statement of Accounts** (Process Statement of Accounts) |
| Link cards | *Today*: Payment Feed Entry, Payment Import Batch, Payment Entry · *Records*: Customer, Customer Vehicle, Sales Invoice, Journal Entry · *Reports*: Sales by Product, Payment Mix Matrix, Cashier Statement, Clearing Account Ageing, Cash Position by Station, Credit Slips Register, Accounts Receivable, (P) Margin by Item Group |

#### Forecourt Operations (area manager home)

| Block | Content |
|---|---|
| Number cards | Shifts awaiting approval · Corrections pending · Tank variance this month (L) · (P) Count exceptions this month |
| Charts | Station comparison: litres per day · (P) Tank and shelf variance by station |
| Shortcuts | **Approve Shifts** (count, red) · **Approve Price Changes** (count, red) · **Approve Corrections** (count, red) · **Spot Dip** · **(P) Spot Audit** (Dry Stock Count, new, type Spot Audit) · **Exception Register** · **Station Comparison** · **Operations Dashboard** |
| Link cards | *Approvals*: Forecourt Shift (Pending Approval), Fuel Price Change (Pending), Shift Correction (Pending) · *Reports*: Exception Register, Station Comparison, Cashier Variance Ranking, Wetstock Variance, Meter Drift, (P) Dry Stock Count Exceptions, (P) Write-off and Adjustment Trend, (P) Unreceipted Sales by Cashier |

#### Forecourt Group (executives)

| Block | Content |
|---|---|
| Number cards | Fuel sales today · Litres sold today · Cash position (custom) · Accounts Receivable (ERPNext card) · (P) Live sales now |
| Charts | Station comparison: litres per day · Litres per day by product · Payment mix · (P) Sales by stream |
| Shortcuts | **Group Dashboard** · **Station Comparison** · **Daily Station Report** · **Profit and Loss** · **Balance Sheet** |
| Link cards | *Financials*: Profit and Loss Statement, Balance Sheet, Consolidated Trial Balance, Accounts Receivable · *FMS*: Station Comparison, Daily Station Report, Wetstock Variance, (P) Margin by Item Group |

#### Devices and Integrations — new in 1.2

Integration Inbox and Payment Provider move here from *Forecourt Setup*, so integration problems are watched where they are fixed. *Forecourt Setup* keeps a link to this workspace.

| Block | Content |
|---|---|
| Number cards | Failed integration messages · Unmatched payments · (P) Devices offline · (P) Unpaid fuel transactions |
| Shortcuts | **Failed Messages** (Integration Inbox, status Failed; count, red) · **Payment Providers** · **FMS Health** · **(P) Devices** (Forecourt Device list) · **(P) Unpaid Fuel** (FCC Transaction, status Unpaid; count, orange) · **(P) Device Health Dashboard** |
| Link cards | *Integrations*: Integration Inbox, Payment Provider, Payment Feed Entry, Payment Import Batch · *(P) Devices*: Forecourt Device, FCC Transaction · *Reports*: FMS Health, (P) Device Health, (P) Nozzle Completeness, (P) Offline Sales, (P) Voids and Refunds |

#### Forecourt Setup (administrator)

| Block | Content |
|---|---|
| Shortcuts | **New Station** · **Station onboarding** (the onboarding panel, 14.10) · **Forecourt Settings** · **Company Settings** |
| Link cards | *Settings*: Forecourt Settings, Forecourt Company Settings · *Network*: Station Group, Station · *Equipment*: Fuel Tank, Tank Calibration Chart, Island, Pump, Nozzle, Forecourt Shift Template · *Masters*: Variance Reason, Expense Type, Own Use Purpose, (P) Stock Adjustment Reason, (P) Service Type, (P) LPG Product · *Integrations*: Devices and Integrations workspace · *Health*: FMS Health |
| Onboarding | Module Onboarding (14.10) |

Equipment appears both here (to create it) and in *Wetstock* (to look it up). That is the one deliberate duplication: setup and daily use are different moments for different people.

### 14.4 Shortcut conventions

| Item | Rule |
|---|---|
| Label | Verb first, at most three words: *New Shift*, *Open Shifts*, *Approve Corrections* |
| Type | `DocType` with `doc_view` *New* for create shortcuts, *List* for lists; `Report` for reports; `Dashboard` for dashboards |
| Count | `stats_filter` in JSON, same filter as the list it opens, `format` = `{} open`, `{} waiting`, `{} failed` |
| Colour | **Blue**: create · **Orange**: work waiting for this user · **Red**: approval waiting or something blocked · **Grey**: report or reference |
| Limit | At most 10 shortcuts per workspace. The first four are the most frequent tasks of the home persona. |
| Filters on lists | Shortcuts to lists pass filters through `stats_filter` and the list opens with the same filters, so the count and the list always agree |

### 14.5 Dashboards

Workspaces are for **doing**; dashboards are for **looking**. Each dashboard is a standard Frappe **Dashboard** record (shipped as a fixture) made of the number cards and charts of section 13, opened from the shortcut of the same name. Every card and chart respects User Permissions, so the same dashboard shows one station to a manager and the whole group to an executive.

| Dashboard | Opened from | For | Number cards | Charts |
|---|---|---|---|---|
| **Station Dashboard** | Forecourt; Station form (*View → Station Dashboard*) | Station Manager | Open shifts · Litres sold today · Fuel sales today · Unmatched payments · Draft GRNs · Tanks below reorder | Sales by hour today · Litres per day by product · Payment mix · Cashier differences |
| **Wetstock Dashboard** | Wetstock | Station Manager, Area Manager | Tank variance this month · Tanks below reorder | Cumulative tank variance % · Delivery variance by supplier · Litres per day by product |
| **(P) Shop and Services Dashboard** | Shop and Services | Station Manager | Dry stock sales today · Service sales today · Open Service Jobs · Items below reorder · Count exceptions this month | Sales by stream · Shop margin by item group · Service jobs per day by type |
| **Cash and Payments Dashboard** | Forecourt Finance | Station Accountant | Unmatched payments · Cash short this month · Accounts Receivable · Failed integration messages | Payment mix · Cashier differences |
| **Operations Dashboard** | Forecourt Operations | Area Manager | Shifts awaiting approval · Corrections pending · Tank variance this month · Count exceptions this month | Station comparison · Cumulative tank variance % · Tank and shelf variance by station · Unreceipted sales by cashier |
| **Group Dashboard** | Forecourt Group | Business Executive | Fuel sales today · Litres sold today · Cash position · Accounts Receivable · Live sales now | Station comparison · Litres per day by product · Payment mix · Sales by stream |
| **(P) Device Health Dashboard** | Devices and Integrations | Administrator, Station Manager | Devices offline · Unpaid fuel transactions · Failed integration messages | Live sales by hour (Mode B) |

**Chart defaults.** Time-series charts: last 30 days, daily, with *Station* as the first filter. Charts that compare stations group by station and are hidden from single-station users by role. Number cards that are money show the company currency; litres show `L`.

**Scheduled reports.** The *Daily Station Report* is sent by **Auto Email Report** to Business Executive users every morning, and *FMS Health* to the administrator (design guide 12.6 and 15.4). Both are fixtures, disabled by default, switched on per company.

### 14.6 Form navigation

**Connections tab.** Each FMS DocType declares its `links` in the DocType JSON, so its form shows the related documents with counts and a *New* button. Child-table links use `parent_doctype` and `table_fieldname`.

| Form | Connections (grouped) |
|---|---|
| Station | *Equipment*: Fuel Tank, Island, Pump, Nozzle · *Shifts*: Forecourt Shift, Forecourt Shift Template · *Stock*: Purchase Receipt, Tank Dip, (P) Dry Stock Count · *(P) Services and devices*: Service Job, Forecourt Device |
| Fuel Tank | Tank Calibration Chart, Nozzle, Tank Dip, Tank Transfer, Purchase Receipt (through GRN Delivery Dip) |
| Pump | Nozzle |
| Nozzle | Meter Change, Forecourt Shift (through Shift Meter Reading), (P) FCC Transaction |
| Forecourt Shift Template | Forecourt Shift |
| Forecourt Shift | *Generated*: Sales Invoice, Delivery Note, Payment Entry, Journal Entry, Stock Reconciliation, Stock Entry · *Pulled*: Purchase Receipt, (P) Service Job, (P) Dry Stock Count, (P) FCC Transaction · *After close*: Shift Correction |
| Fuel Price Change | Forecourt Shift (`applied_to_shift`) |
| Customer | Customer Vehicle (plus the standard ERPNext connections) |
| Employee | Forecourt Shift (through Shift Cashier) |
| (P) Service Type | Service Job |
| (P) Service Job | Sales Invoice |
| (P) Forecourt Device | Sales Invoice (`fms_device`), FCC Transaction (`controller`) |

**Buttons on forms.** Custom buttons are grouped under *Create* and *View* so they sit in the same place on every form.

| Form | Create | View | Other |
|---|---|---|---|
| Station | New Shift · Spot Dip · New GRN | Station Dashboard · Daily Station Report · Tank Stock Position | |
| Forecourt Shift | Shift Correction (closed shifts only) | Shift Report · Exception Register (this shift) · Sales by Cashier (this shift) | **Validate** (runs the gates and lists errors with their FMS codes) · **Import Payments** · **Refresh pulled documents** |
| Fuel Tank | Spot Dip · Tank Transfer | Wetstock Variance · Tank Stock Position | |
| Nozzle | Meter Change | Meter Drift · Sales by Pump and Nozzle | |
| Purchase Receipt (fuel) | Record delivery shortage (design guide 5.4) | Delivery Variance · Forecourt Shift (when pulled) | |
| Customer | Customer Vehicle | Credit Slips Register · Statement of Accounts | |
| Employee (cashier) | | Cashier Statement | |
| (P) Service Job | | Sales Invoice (when paid) | Print job card |
| (P) Dry Stock Count | | Dry Stock Count Exceptions | |

**Back to the shift.** Every native document with `fms_forecourt_shift` set shows the shift as a link at the top of the form (a form indicator), so nobody is stranded inside a generated invoice.

### 14.7 List views

| DocType | List columns (`in_list_view`) | Standard filters | Indicator | Saved filters (shipped) | Other views |
|---|---|---|---|---|---|
| Forecourt Shift | station, shift_date, shift_template, status, approval_state | station, shift_date, status | Open grey, Counting orange, Reconciled blue, Pending Approval red, Closed green, Corrected purple | *Today* · *Open* · *Pending approval* · *This week* | Calendar on `shift_start`; Kanban by `status` for the area manager |
| Fuel Price Change | station, effective_at, workflow state | status, effective_at | Draft grey, Pending red, Approved green | *Pending* | |
| Shift Correction | forecourt_shift, correction_type, status | status | Draft grey, Pending Director Approval red, Applied green | *Pending* | |
| Tank Dip | tank, dipped_at, volume_l, difference_l, purpose | station, tank, purpose | | *This week* | |
| Purchase Receipt (FMS filter) | supplier, station, posting_date, status | station | standard | *Draft fuel GRNs* | |
| Payment Feed Entry | provider, amount, transaction_time, status | status, provider, station | Unmatched orange, Matched green, Ignored grey, (P) Used green | *Unmatched* | |
| Integration Inbox | provider, direction, status, attempts | status, provider | Failed red, Received grey, Processed green, Ignored grey | *Failed* | |
| (P) Service Job | ticket_no, service, vehicle_plate, cashier, total_amount, status | station, status, performed_at | Draft grey, Submitted orange, Paid green, Used by shift blue | *Open* · *Today* | Kanban by status at the bay |
| (P) Dry Stock Count | count_type, station, counted_at | count_type, station | | *Spot audits this month* | |
| (P) Forecourt Device | device_type, station, status, last_seen | station, status | Active green, Suspended orange, Revoked red | *Offline* | |
| (P) FCC Transaction | pump, nozzle, volume, amount, status, ended_at | station, status | Unpaid orange, Paid green, Unreceipted red | *Unpaid* | |

Default sort is `creation desc` (v16 default) except Forecourt Shift (`shift_start desc`) and Tank Dip (`dipped_at desc`).

### 14.8 Search and keyboard shortcuts

**Awesomebar.** `search_fields` make records findable by what people know: station code, shift number, tank code, nozzle number, vehicle plate (Customer Vehicle), (P) ticket number (Service Job) and device id (Forecourt Device). Typing *new shift*, *new grn* or *spot dip* offers the create action through the standard search.

**Standard Desk shortcuts.** The Desk's built-in keyboard shortcuts apply on every FMS form, for example *Ctrl+S* to save and *Ctrl+B* for a new document of the current type. The Desk's *Keyboard Shortcuts* dialog lists them. *To verify in the build task:* the full list in the installed version.

**FMS shortcuts on the Forecourt Shift form** (registered with `frappe.ui.keys.add_shortcut`, so they also appear in the Keyboard Shortcuts dialog):

| Keys | Action |
|---|---|
| *Enter* in a reading, dip, count or cash grid | Next row, same column (design guide 6.4) |
| *Alt+1* to *Alt+7* | Jump to the shift's tabs in screen order |
| *Ctrl+Shift+V* | Validate: run the gates and show the error list |
| *Ctrl+Shift+I* | Import payments |
| *Ctrl+Shift+R* | Open the Shift Report |

These are checked for clashes with the browser and the tablet keyboard in the tablet review task (FMS-K03) before release.

### 14.9 Notifications and to-dos

The bell and the email inbox tell people what needs them, so they do not have to look.

| Event | Who | How |
|---|---|---|
| Shift sent for approval | Area Manager of the station's group | Workflow Action (standard) and email |
| Shift approved or rejected | User who prepared it | Notification, system and email |
| Fuel Price Change waiting for approval | Area Manager | Workflow Action |
| Shift Correction waiting for a director | Users with director approval rights | Workflow Action |
| Tank variance beyond the approval threshold | Station Manager and Area Manager | Notification on Wetstock Ledger Entry insert (custom method) |
| Shift still open 2 hours after its template's end time | Station Manager | Scheduled Notification |
| Integration message failed three times | Administrator | Notification on Integration Inbox |
| (P) Device offline for 30 minutes | Station Manager | Scheduled job and Notification |
| Daily summaries | Executives, administrator | Auto Email Report (14.5) |

All are shipped as **Notification** fixtures, disabled by default, and enabled per company. Exceptions that need follow-up are assigned as **ToDo** to a person from the Exception Register.

### 14.10 Onboarding

Each working workspace carries a short **Module Onboarding** panel that disappears once its steps are done.

| Workspace | Steps |
|---|---|
| Forecourt Setup | Company settings → station → tanks → calibration charts → islands → pumps → nozzles → shift template → (P) stock locations and count policies → (P) service types → first shift |
| Forecourt | Open the first shift → enter readings → enter dips → enter cash → validate → submit |
| Forecourt Finance | Map tills and terminals on the Station → import the first mobile money statement → match a payment → run the Cashier Statement |
| (P) Devices and Integrations | Register a device → set its POS Profile → test a sale on the training station |

### 14.11 Hiding what people do not need

- **Module Profiles** (fixtures): *Forecourt Station Staff* hides the ERPNext modules station users do not use (for example Manufacturing, Projects, Quality, Support, Website, CRM). *Forecourt Accounts* keeps Accounts, Stock, Buying and Selling. *Forecourt Executive* keeps only read access to Accounts and the FMS workspaces. Each FMS user gets the profile of their persona (2.5).
- Standard ERPNext workspaces (Accounting, Stock, Selling, Buying) stay available to accountants and administrators, who need them.
- **Default app.** Station users have the `forecourt` app as their default app, so the Desk opens on FMS workspaces. *To verify in the build task:* the v16 setting for the default app per user.

### 14.12 Tablets and small screens

- On a tablet the workspace becomes one column, so block order matters. Working workspaces put **shortcuts first** (principle U9), so the manager's first screen is the task list.
- The shift form keeps its tab order and the *Enter*-moves-down grids. Shift close in under 10 minutes on a tablet is a release check (design guide 16.3).
- When the dedicated **Shift Close page** is built (design guide 16.4, backlog epic P4), the *Open Shifts* shortcut opens it instead of the Desk form. Nothing else in the navigation changes.
- Mode B cashiers use the PDQ or POS app, which has its own screens (fms-nonfuel.md 11.4).

### 14.13 Build notes

| Item | Where |
|---|---|
| Workspaces, Number Cards, Dashboard Charts, Dashboards | Fixtures, filtered by `module = Forecourt …` (section 12) |
| Notifications, Auto Email Reports, Module Profiles, Module Onboarding | Fixtures, disabled where noted |
| Connections | `links` in each DocType JSON |
| Form buttons and keyboard shortcuts | Client scripts in `forecourt/public/js/` (one file per DocType) |
| Default workspace on user creation | `after_insert` hook on User (2.5) |
| Count shortcuts | `stats_filter` in workspace JSON; checked in the workspace task so each count equals its list |
| Tasks | Section H of TASKS.md (reports and workspaces). (P) items go to FMS-Q when accepted. |

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
| 10 | Island | 2 | Wetstock | Master | | format |
| 10b | Pump | 2 | Wetstock | Master | | format |
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

**Totals (accepted):** 28 numbered DocTypes in the table above (27 standalone DocTypes plus GRN Delivery Dip), 20 further child tables, custom fields on 11 ERPNext DocTypes, 22 reports (one is a print format), 13 number cards, 7 charts, 9 workspaces, 5 dashboards, 3 workflows. (1.1 had 9 cards, 6 charts, 7 workspaces and no dashboards; 1.2 adds the cards *Draft GRNs*, *My open shift*, *My balance* and *Failed integration messages*, the chart *Sales by hour today*, the workspaces *My Shift* and *Devices and Integrations*, and the dashboards of 14.5.)

**Proposed (P), not yet accepted** (from [fms-nonfuel.md](fms-nonfuel.md), decisions D37 to D62). Numbers are given when the owner accepts them.

| # | DocType | Level | Module | Kind | Submittable | Naming |
|---|---|---|---|---|---|---|
| P1 | Stock Adjustment Reason (+ Stock Adjustment Reason Account) | 0 | Forecourt Setup | Master | | field:reason |
| P2 | LPG Product | 0 | Forecourt Setup | Master | | field:name |
| P3 | Service Type (+ Service Type Consumable) | 1 | Forecourt Services | Master | | field:service_type |
| P4 | Forecourt Device | 1 | Forecourt Integrations | Master | | field:device_id |
| P5 | Dry Stock Count (+ Dry Stock Count Item) | 4 | Wetstock | Transaction | ✓ | format:DSC-{station}-{YYYY}-{#####} |
| P6 | Service Job (+ Service Job Line, Service Job Part) | 4 | Forecourt Services | Transaction | ✓ | format:SJ-{station}-{YYYY}-{#####} |
| P7 | FCC Transaction | Int | Forecourt Integrations | Log | | format:FCC-{station}-{#######} |
| P8 | Dry Stock Ledger Entry | 6 | Forecourt Finance | Ledger | | hash |

Proposed child tables (11): Stock Adjustment Reason Account, Service Type Consumable, Station Stock Location, Shift Template Item Assignment, Dry Stock Count Item, Service Job Line, Service Job Part, Shift Stock Count, Shift Stock Count Detail, Shift Service, Shift FCC Exception.

**Totals with the proposals:** 36 numbered DocTypes, 31 further child tables, 6 modules, 22 number cards, 12 charts, 10 workspaces, 7 dashboards, 2 new roles (Area Manager, Forecourt Administrator). The proposed reports are listed in fms-nonfuel.md section 18.1.
