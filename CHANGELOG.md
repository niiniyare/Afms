# Changelog

All notable changes to the Forecourt Management System app are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] — 2026-10-27

### Summary

First deployable release of the Forecourt Management System on Frappe v16 + ERPNext v16.
Covers the complete Phase 0–J feature set: station and equipment setup, shift lifecycle,
wetstock and cashier reconciliation, payment integrations, fiscal receipting, and all
FMS reports.

### Added

#### Foundation (Phase 0)
- Station, Station Group, Fuel Tank, Pump, Nozzle, Meter Reading, Tank Dip DocTypes
- Forecourt Company Settings with fiscal and payment adapter configuration
- Workspace for FMS Forecourt module

#### Calculation core
- Pure-Python `calc/` package: meters, drift, calibration, reconciliation, attribution,
  cashier, properties — all tested with unit tests and edge cases

#### Station movements
- Tank Dip, Meter Change, Fuel Own Use, Tank Transfer DocTypes
- Wetstock Ledger Entry and Stock Ledger integration

#### Forecourt Shift (Phase 1)
- Full shift lifecycle: Open → Counting → Reconciled → Closed
- Meter reading modes (E-cash, E-vol, M-vol, Highest)
- Tank reconciliation with tolerance gates
- Cashier accountability and cash count
- Credit sales with over-limit flags
- Price change management (Fuel Price Change DocType)
- Background close for large shifts
- Shift Report print format
- Shift gates: FMS-S101 through FMS-S116

#### Shift Correction
- Director-approved correction workflow
- Supersede-and-rewrite pattern for ledger entries
- Cancel guard (`fms_correction` flag) on generated documents

#### Reports and workspaces
- Daily Station Report, Sales by Shift, Cashier Statement, Wetstock Variance
- Cash Position by Station, Clearing Account Ageing, Sales by Product
- Station Comparison, Payment Mix Matrix, Exception Register
- Open Items (outstanding credit and debt)
- FMS Health Check

#### Approvals, roles and permissions
- Role: Station Manager, Area Manager, Forecourt Accountant, Forecourt Director
- Station and Station Group User Permissions
- Shift approval workflow with email notifications
- Permission tests

#### Payment integrations
- Payment Import Batch (CSV statement import)
- Integration Inbox (inbound and outbound async queue)
- Payment Feed Entry and shift matching
- M-Pesa C2B callback adapter (sandbox + production)

#### Fiscal integrations
- FiscalAdapter protocol (`submit`, `status`, `cancel`)
- Kenya eTIMS Lite adapter (VSCU/OSDC)
- Sales Invoice on_submit → Integration Inbox → eTIMS POST
- Fiscal custom fields on Sales Invoice (fms_fiscal_status, fms_fiscal_receipt_no,
  fms_fiscal_signature, fms_fiscal_qr)

#### CI/CD
- GitHub Actions: unit tests (calc, no bench) + integration tests (bench + MariaDB)
- Linter: pre-commit + semgrep Frappe rules + pip-audit

#### Documentation
- Bank statement import and reconciliation guide
- Golden-month scenario test script (`forecourt/tests/golden.py`)

### Technical notes
- Requires Frappe v16 and ERPNext v16 (`version-16` branches)
- Python 3.14+, Node 24+, MariaDB
- No core ERPNext overrides; all extensions via custom fields and `doc_events`
- All arithmetic in `forecourt/calc/` — no `frappe` imports in calc layer
- `frappe.db.commit()` never called in controllers or hooks

---

[0.1.0]: https://github.com/niiniyare/Afms/releases/tag/v0.1.0
[Unreleased]: https://github.com/niiniyare/Afms/compare/v0.1.0...HEAD
