# Bank Statement Import and Reconciliation Guide

This guide explains how to import provider and bank statements into ERPNext and reconcile them against the Payment Entries the FMS creates at shift close.

---

## Background

At shift close the FMS posts one **Payment Entry** per mobile money transaction and per card transaction. Each entry carries:

- the provider's transaction reference (M-Pesa transaction ID, card approval code, RRN)
- the amount
- the posting time
- the station as an accounting dimension
- a credit to the relevant **clearing account** (e.g., *Mobile Money Clearing – M-Pesa*, *Card Clearing – Visa*)

The accountant's daily task is to reconcile these clearing accounts against the provider statements or bank statements, then record the actual settlement or payout.

---

## Step 1: Configure Bank Accounts

For each payment rail create one ERPNext **Bank Account**:

| Rail | Bank Account Name | Account (GL) |
|---|---|---|
| M-Pesa (Safaricom) | M-Pesa Clearing | Mobile Money Clearing – M-Pesa |
| Visa/Mastercard | Card Acquirer Clearing | Card Clearing – {Acquirer} |
| Company bank account | {Bank} – {Branch} | Bank – {Bank} |

In ERPNext: **Accounting → Bank → Bank Account → New**

Set:
- **Bank** – the financial institution
- **Account** – the corresponding GL account from your chart of accounts
- **Is Company Account** – checked for real bank accounts; leave unchecked for clearing accounts

---

## Step 2: Create Bank Statement Import Mapping

Each provider/bank exports statements in a different CSV format. ERPNext **Bank Statement Import** lets you map columns once and reuse the mapping.

### M-Pesa Business Pay Bill statement

Typical M-Pesa Pay Bill CSV columns:

| CSV Column | ERPNext Field |
|---|---|
| `Transaction ID` | `Reference Number` |
| `Completion Time` | `Date` |
| `Amount` | `Withdrawal` (money leaving your till) or `Deposit` (money arriving) |
| `Details` | `Description` |
| `Balance` | *(ignored)* |

To create the mapping:
1. **Accounting → Bank → Bank Statement Import → New**
2. Select the **Bank Account** (e.g., M-Pesa Clearing)
3. Under **Mapped Items**, add one row per column you want to capture, mapping each CSV header to its ERPNext field
4. Save as a named mapping (e.g., `M-Pesa Pay Bill`)

Repeat for each provider format.

### Equity / KCB / Co-op bank statement

Typical CSV columns from Kenyan bank online banking exports:

| CSV Column | ERPNext Field |
|---|---|
| `Value Date` | `Date` |
| `Description` / `Narration` | `Description` |
| `Debit` | `Withdrawal` |
| `Credit` | `Deposit` |
| `Reference` | `Reference Number` |

Create a mapping per bank, named e.g., `Equity Bank Statement`.

---

## Step 3: Import a Statement

1. Download the CSV/XLSX from the provider portal or bank's internet banking
2. **Accounting → Bank → Bank Statement Import → New**
3. Select the **Bank Account**
4. Upload the file
5. Select the **Mapping** you created
6. Click **Map Columns** and verify the preview rows
7. Click **Start Import**

ERPNext creates unmatched **Bank Transaction** records for each row.

---

## Step 4: Reconcile with the Bank Reconciliation Tool

1. **Accounting → Bank → Bank Reconciliation Tool**
2. Select **Bank Account** and **Date Range**
3. The tool shows bank transactions on the left and unreconciled Payment Entries on the right

### Matching by reference

Because every FMS Payment Entry carries the provider's transaction ID as its reference number, the Bank Reconciliation Tool's **Auto Reconcile** button finds matches automatically:

- **M-Pesa**: statement `Transaction ID` = Payment Entry `reference_no`
- **Card**: statement `Approval Code` or `RRN` = Payment Entry `reference_no`

For each matched pair, click **Reconcile** (or let Auto Reconcile do it in bulk).

### Batch card settlements

Card acquirers often pay out daily batches. Each batch covers many transactions. To reconcile:

1. Select all Payment Entries in the batch
2. Select the single settlement bank transaction
3. Click **Reconcile** — ERPNext groups them

---

## Step 5: Record the Provider Payout

When the provider transfers funds to your bank account:

1. **Accounting → Banking → Payment Entry → New**
2. **Payment Type** = Internal Transfer
3. **From Account** = M-Pesa Clearing (or card clearing)
4. **To Account** = Company Bank Account
5. **Reference Number** = provider's payout reference
6. Amount = net payout (after provider fees)

For provider fees, add a **Deduction** row on the Payment Entry:
- **Account** = Bank Charges (or Mobile Money Fees) expense account
- **Amount** = fee amount

---

## Step 6: Verify the Clearing Account Balance

After each daily reconciliation the clearing account should return to zero (or show only today's uncleared transactions).

Check: **Accounting → Financial Statements → Trial Balance**

Filter by:
- Account = M-Pesa Clearing
- Date = yesterday

A non-zero balance means either:
- a transaction was declared in a shift but the provider did not pay it out (possible fraud or error), or
- a provider payment arrived but no matching Payment Entry exists in ERPNext.

The **Clearing Account Ageing** report (FMS-H09) shows this per station per provider.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Statement row not matched | Reference format differs (spaces, dashes) | Edit the Bank Transaction's Reference Number to match the Payment Entry exactly |
| Duplicate import | Same file imported twice | Delete duplicate Bank Transactions before reconciling |
| Amount mismatch | Provider deducted fees before showing amount | Reconcile net amount, record fee as bank charge on the payout entry |
| Missing Payment Entry | Shift not yet closed, or payment not imported from the provider during shift entry | Close the shift first; check the shift's Payment Import Batch |

---

## Owner verification checklist (UI test)

- [ ] Import a sample M-Pesa Pay Bill CSV (5–10 rows)
- [ ] Bank Reconciliation Tool shows the imported transactions
- [ ] Auto Reconcile matches at least one transaction to a Payment Entry by reference
- [ ] After reconciling, clearing account balance equals sum of unreconciled transactions only
- [ ] Provider payout Payment Entry posts cleanly and brings clearing balance to zero
