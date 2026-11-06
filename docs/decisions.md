# FMS Architecture Decisions

This file records owner decisions on deployment and architecture questions from the design guide.
Each entry shows the options considered, the decision made (once confirmed), and the date.

**Open decisions need owner sign-off before the related task is marked done.**

---

## D1 · Deployment model

**Status: OPEN — owner decision required**

See design guide section 4.2 for full discussion.

### Options

| | Option A: One shared site | Option B: Separate sites + group site |
|---|---|---|
| Shape | All companies and stations in one Frappe site (one DB) | One site per company/dealer; group site holds summaries |
| Consolidation | Native ERPNext consolidated statements | Group site imports trial balances periodically |
| Data isolation | User Permissions on Company and Station | Physical — each owner's data in its own database |
| Best for | Company-owned networks; investors happy to share one system | Independent dealers; different jurisdictions or hosting rules |
| Upgrades | One system to keep current | Many systems to keep on the same app version |
| Cost | Lowest | Higher (more servers, sync jobs) |
| Failure impact | Single outage affects all stations | Isolated outages |

A **mix** is also valid: company-owned stations on one site, each dealer on their own.

### Hosting platform options

| Platform | Notes |
|---|---|
| **Frappe Cloud** | Managed hosting, automatic upgrades, backups, SSL. Easiest to operate. Recommended for getting started. |
| **VPS + bench setup production** | Full control; requires Linux administration and ops expertise. Suitable if data sovereignty or cost is a priority. |
| **Docker (frappe_docker)** | Containerised; easiest to reproduce across environments. Requires Docker/k8s expertise. |

**Recommendation for pilot:** Frappe Cloud, shared site (Option A), single company. Migrate to Option B later if independent dealers join.

### Decision

- [ ] **Deployment model:** _________________
- [ ] **Hosting platform:** _________________
- [ ] **Single site or separate sites:** _________________
- [ ] **Date decided:** _________________
- [ ] **Owner signature in PR:** _________________

---

## D2 · HRMS installation

**Status: OPEN**

HRMS provides salary deductions for cashier shortages (D16 in design guide).

- Without HRMS: shortages charged to a Staff Shortage Receivable account; recovery via cash repayment (Payment Entry).
- With HRMS: shortages can be recovered through HRMS Additional Salary (salary deduction).

**Decision:** Install HRMS? Yes / No

---

## D16 · Cashier shortage recovery method

**Status: OPEN — depends on D2**

See design guide section 8.3.

- **Via HRMS Additional Salary** (requires HRMS installed) — salary deduction in next pay run
- **Via cash repayment** — cashier pays back by Payment Entry against Staff Shortage Receivable
- **Both** — manager chooses per case

---

## D17 · Account type for Staff Shortage Receivable

**Status: OPEN — confirmed in FMS-C03 task**

The account used for cashier shortages must accept party type *Employee*. The exact account type that permits this in ERPNext depends on the chart of accounts installed. Confirm during site setup in C03.

---

## D19 · Shift approval state field

**Status: DECIDED — 2026-10-20**

Decided: The controller sets `status` from data on every save. A Frappe Workflow drives only the approval step on a separate `approval_state` field (*Not Required*, *Pending Approval*, *Approved*, *Rejected*). The approver cannot be the user who prepared the shift.

---

## Decisions log

| ID | Topic | Status | Decided |
|---|---|---|---|
| D1 | Deployment model | **OPEN** | — |
| D2 | HRMS installation | **OPEN** | — |
| D16 | Cashier shortage recovery | **OPEN** | — |
| D17 | Staff Shortage Receivable account type | **OPEN** | — |
| D19 | Shift approval workflow | DECIDED | 2026-10-20 |
