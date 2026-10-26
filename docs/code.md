# FMS Code Deep Dive

Reference code for the `forecourt` Frappe app (ERPNext v16): the algorithms, global helpers, shift logic, posting, hooks, permissions, corrections, import and tests that the development tasks build on. Claude Code copies these files into the app while working through `FMS_Development_Tasks.md`; each block names the file path and the task IDs it serves.

Companion documents: `FMS_ERPNext_Design_Guide.md` (why), `FMS_DocType_Catalogue.md` (field names), `FMS_Development_Tasks.md` (order of work), `CLAUDE.md` (rules for the repository).

*Version 1.0 · 2026-10-26*

---

## Contents

1. [Calculation core (`forecourt/calc`)](#1-calculation-core-forecourtcalc)
2. [Errors and gates (`forecourt/errors.py`)](#2-errors-and-gates-forecourterrorspy)
3. [Global helpers (`forecourt/utils`)](#3-global-helpers-forecourtutils)
4. [Shift: pre-fill, sources, recompute, gates](#4-shift-pre-fill-sources-recompute-gates)
5. [Shift controller and form](#5-shift-controller-and-form)
6. [Posting (`forecourt/posting`)](#6-posting-forecourtposting)
7. [Document events on ERPNext DocTypes (`forecourt/events`) and hooks](#7-document-events-on-erpnext-doctypes-forecourtevents-and-hooks)
8. [Permissions (`forecourt/permissions`)](#8-permissions-forecourtpermissions)
9. [Corrections (`forecourt/corrections`)](#9-corrections-forecourtcorrections)
10. [Integrations: statement import](#10-integrations-statement-import)
11. [Tests: factories and the shift scenario](#11-tests-factories-and-the-shift-scenario)
12. [Verification status and what to check on a bench](#12-verification-status-and-what-to-check-on-a-bench)

---

## 0. How to use this document

**Layout.** Paths are relative to the app repository root (`apps/forecourt/`), so `forecourt/calc/meters.py` is `apps/forecourt/forecourt/calc/meters.py`. DocType folders follow Frappe's layout (`forecourt/<module>/doctype/<doctype>/`).

```
forecourt/
├── hooks.py, tasks.py, errors.py
├── calc/              pure arithmetic, no frappe imports, unit-tested
├── utils/             settings, time, shifts, pricing, stock helpers
├── forecourt_shift/
│   ├── shift/         prefill, sources, compute, gates
│   └── doctype/       forecourt_shift (.py, .js), shift_correction
├── posting/           native documents and ledgers on close
├── events/            doc_events on ERPNext DocTypes
├── permissions/       station group row-level access
├── corrections/       Shift Correction apply step
├── forecourt_integrations/statement_import.py
├── public/js/         form scripts for ERPNext DocTypes
└── tests/             test_calc (pure), factories, test_shift_close
```

**Dependency rule.** `calc` imports nothing from Frappe. `utils` imports `calc`. `forecourt_shift/shift` imports `utils` and `calc`. `posting` imports all three. Controllers, events and JS only call into these packages. If a controller starts doing arithmetic, move it into `calc` with a test.

**Task tags.** Each file's heading lists the task IDs from `FMS_Development_Tasks.md`. When starting a task, search this document for its ID.

**Conventions** (from `CLAUDE.md`): tabs; type hints; `frappe._()` around user text; field names exactly as in the catalogue; no `frappe.db.commit()` in document hooks; Query Builder or `frappe.get_all` instead of raw SQL; `ignore_permissions` only in system code that has already checked the caller.

**Status at a glance.** 43 files. The calculation core is run and tested. The Frappe layer compiles (`py_compile`, `node --check`) and follows v16 APIs, but has **not yet run on a bench**; section 12 lists the calls to verify first.

---

## 1. Calculation core (`forecourt/calc`)

Pure Python with **no Frappe imports**. Every number the FMS shows or posts is produced here, so the arithmetic can be unit-tested in milliseconds and read in one place. Controllers convert documents into these dataclasses, call one function and copy the result back. Errors are `CalcError(code, message)`; the Frappe layer turns them into coded messages with `forecourt.errors.from_calc_error`.

**Status:** all modules in this section run under `python3 -m unittest forecourt.tests.test_calc` (30 tests, passing), including 300 randomised attribution cases.

### 1.1 `forecourt/calc/errors.py`

**Tasks:** FMS-D01 · 17 lines

One exception type for the whole core. The `code` matches the error catalogue.

```python
# forecourt/calc/errors.py
"""Calculation errors. Pure Python: no frappe imports.

Each error carries an FMS code from the design guide's error catalogue, so the
Frappe layer can turn it into a user message without parsing strings.
"""

from __future__ import annotations


class CalcError(ValueError):
	"""A calculation could not be done with the given inputs."""

	def __init__(self, code: str, message: str, **context: object) -> None:
		super().__init__(f"{code}: {message}")
		self.code = code
		self.message = message
		self.context = context
```

### 1.2 `forecourt/calc/numbers.py`

**Tasks:** FMS-D01 · 41 lines

Half-up decimal rounding and minor units. Never use Python's `round()` for money: it rounds half to even.

```python
# forecourt/calc/numbers.py
"""Rounding helpers shared by every calc module.

Money is rounded to the currency precision, volumes to the volume precision.
Never compare two floats directly: use `is_zero` or compare rounded values.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

VOLUME_PRECISION = 3  # litres, three decimals
MONEY_PRECISION = 2  # most currencies; pass the real precision where it differs


def rnd(value: float, precision: int) -> float:
	"""Round half up (commercial rounding), unlike Python's banker's rounding."""
	if value is None:
		return 0.0
	q = Decimal(1).scaleb(-precision)
	return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def money(value: float, precision: int = MONEY_PRECISION) -> float:
	return rnd(value, precision)


def litres(value: float, precision: int = VOLUME_PRECISION) -> float:
	return rnd(value, precision)


def to_minor(value: float, precision: int = MONEY_PRECISION) -> int:
	"""Money as an integer number of minor units (cents). Used for exact splits."""
	return int(Decimal(str(rnd(value, precision))).scaleb(precision))


def from_minor(units: int, precision: int = MONEY_PRECISION) -> float:
	return float(Decimal(units).scaleb(-precision))


def is_zero(value: float, precision: int = MONEY_PRECISION) -> bool:
	return rnd(value, precision) == 0
```

### 1.3 `forecourt/calc/calibration.py`

**Tasks:** FMS-D02, FMS-C12, FMS-E03, FMS-E06 · 87 lines

Linear interpolation on a tank chart, chart validation, and product volume with a water bottom.

```python
# forecourt/calc/calibration.py
"""Tank calibration (strapping) charts: depth in mm -> volume in litres.

Used by: Tank Calibration Chart validation (FMS-C12), shift tank dips (FMS-F05),
GRN delivery dips (FMS-E03), spot dips (FMS-E06).
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass

from .errors import CalcError
from .numbers import litres


@dataclass(frozen=True)
class ChartRow:
	depth_mm: float
	volume_l: float


def validate_chart(rows: Sequence[ChartRow], capacity_l: float | None = None) -> list[str]:
	"""Raise on an unusable chart; return non-blocking warnings.

	Rules: at least two rows, depths and volumes strictly increasing, no negatives.
	Warning when the last volume differs from the tank capacity by more than 2%.
	"""
	if len(rows) < 2:
		raise CalcError("FMS-T205", "A calibration chart needs at least two rows")
	for prev, cur in zip(rows, rows[1:]):
		if cur.depth_mm <= prev.depth_mm:
			raise CalcError("FMS-T205", f"Depth {cur.depth_mm} mm is not greater than {prev.depth_mm} mm")
		if cur.volume_l <= prev.volume_l:
			raise CalcError("FMS-T205", f"Volume at {cur.depth_mm} mm is not greater than the row before")
	if rows[0].depth_mm < 0 or rows[0].volume_l < 0:
		raise CalcError("FMS-T205", "Depths and volumes cannot be negative")

	warnings: list[str] = []
	if capacity_l:
		gap = abs(rows[-1].volume_l - capacity_l) / capacity_l
		if gap > 0.02:
			warnings.append(
				f"Chart maximum {rows[-1].volume_l:,.0f} L differs from tank capacity {capacity_l:,.0f} L by {gap:.1%}"
			)
	return warnings


def volume_at(depth_mm: float, rows: Sequence[ChartRow]) -> float:
	"""Linear interpolation between the two chart rows around `depth_mm`.

	Depth equal to a row returns that row's volume. Depth outside the chart raises
	FMS-T202 (a dip can never be deeper than the chart; below the first row is an error
	unless the first row is 0 mm).
	"""
	if depth_mm < rows[0].depth_mm or depth_mm > rows[-1].depth_mm:
		raise CalcError(
			"FMS-T202",
			f"Dip {depth_mm} mm is outside the chart ({rows[0].depth_mm}–{rows[-1].depth_mm} mm)",
			depth_mm=depth_mm,
		)
	depths = [r.depth_mm for r in rows]
	i = bisect_left(depths, depth_mm)
	if depths[i] == depth_mm:
		return litres(rows[i].volume_l)
	lo, hi = rows[i - 1], rows[i]
	share = (depth_mm - lo.depth_mm) / (hi.depth_mm - lo.depth_mm)
	return litres(lo.volume_l + share * (hi.volume_l - lo.volume_l))


def product_volume(
	total_depth_mm: float,
	water_depth_mm: float,
	rows: Sequence[ChartRow],
	water_rows: Sequence[ChartRow] | None = None,
) -> tuple[float, float]:
	"""Return (product litres, water litres) for one dip.

	The dipstick measures the total liquid height; water sits at the bottom. Product
	volume is the volume at the total height minus the volume of the water layer. A
	separate water chart is used when the tank has one (more rows near the bottom).
	"""
	if water_depth_mm < 0 or water_depth_mm > total_depth_mm:
		raise CalcError("FMS-T202", "Water depth must be between 0 and the product depth")
	total = volume_at(total_depth_mm, rows)
	water = volume_at(water_depth_mm, water_rows or rows) if water_depth_mm else 0.0
	return litres(total - water), litres(water)
```

### 1.4 `forecourt/calc/meters.py`

**Tasks:** FMS-D03, FMS-D04, FMS-F04 · 153 lines

Meter deltas with rollover, conversion of E-cash to litres, the sales basis (E-cash, E-vol, M-vol or Highest), drift between meters, and test and own-use deductions.

```python
# forecourt/calc/meters.py
"""Nozzle meters: deltas, rollover, sales basis and drift.

Used by: Shift Meter Reading rows (FMS-F03, FMS-F04), Nozzle Ledger (FMS-F15),
meter corrections (FMS-G03). Design guide section 5.3.

Meter kinds:
  ecash - electronic cash totaliser (money)
  evol  - electronic volume totaliser (litres)
  mvol  - manual / mechanical volume totaliser (litres)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .errors import CalcError
from .numbers import litres, money

MeterKind = Literal["ecash", "evol", "mvol"]
Basis = Literal["ecash", "evol", "mvol", "highest"]
METER_KINDS: tuple[MeterKind, ...] = ("ecash", "evol", "mvol")


@dataclass(frozen=True)
class MeterPair:
	"""Opening and closing value of one totaliser.

	`modulus` is the value at which the counter returns to zero (for a 6+2 digit
	volume display that is 1,000,000.00). It is only used when `rollover` is ticked.
	"""

	opening: float
	closing: float
	rollover: bool = False
	modulus: float | None = None


@dataclass(frozen=True)
class SegmentInput:
	"""One nozzle, one cashier, one price segment."""

	price: float
	meters: dict[MeterKind, MeterPair]
	basis: Basis = "ecash"
	test_l: float = 0.0
	own_use_l: float = 0.0
	drift_tolerance_l: float = 2.0
	drift_tolerance_pct: float = 0.5


@dataclass
class SegmentResult:
	deltas: dict[MeterKind, float]
	volumes: dict[MeterKind, float]  # every recorded meter expressed in litres
	basis_meter: MeterKind
	basis_volume_l: float
	net_volume_l: float
	amount: float
	drift: dict[str, float] = field(default_factory=dict)  # "evol_mvol", "ecash_evol", "ecash_mvol"
	drift_breaches: list[str] = field(default_factory=list)


def meter_delta(pair: MeterPair, label: str = "") -> float:
	"""Units counted between opening and closing, handling rollover.

	closing >= opening and no rollover -> closing - opening
	closing <  opening and rollover     -> (modulus - opening) + closing
	anything else                       -> FMS-S101 (or FMS-W102 for a bad modulus)
	"""
	if pair.closing is None:
		raise CalcError("FMS-S101", f"{label} has no closing reading")
	if not pair.rollover:
		if pair.closing < pair.opening:
			raise CalcError(
				"FMS-S101",
				f"{label} closing {pair.closing} is below opening {pair.opening}. "
				"Correct it, or tick Rollover if the meter passed its maximum.",
			)
		return pair.closing - pair.opening
	if not pair.modulus or pair.modulus <= pair.opening:
		raise CalcError("FMS-W102", f"{label} rollover needs the meter maximum on the nozzle")
	if pair.closing >= pair.opening:
		raise CalcError("FMS-S101", f"{label} is marked as rollover but closing is not below opening")
	return (pair.modulus - pair.opening) + pair.closing


def to_litres(kind: MeterKind, delta: float, price: float) -> float:
	if kind == "ecash":
		if price <= 0:
			raise CalcError("FMS-S112", "A cash meter needs a price greater than zero")
		return delta / price
	return delta


def choose_basis(basis: Basis, volumes: dict[MeterKind, float]) -> MeterKind:
	"""Which meter drives sales. 'highest' picks the largest volume; ties keep METER_KINDS order."""
	if basis != "highest":
		if basis not in volumes:
			raise CalcError("FMS-S115", f"Sales basis {basis} is not one of the recorded meters")
		return basis
	return max((k for k in METER_KINDS if k in volumes), key=lambda k: volumes[k])


def drift_limit(volume_l: float, tolerance_l: float, tolerance_pct: float) -> float:
	"""The larger of the absolute and the percentage tolerance."""
	return max(tolerance_l, abs(volume_l) * tolerance_pct / 100)


def compute_drift(volumes: dict[MeterKind, float]) -> dict[str, float]:
	"""Litre differences between every pair of recorded meters (design guide 5.3)."""
	pairs = (("evol", "mvol"), ("ecash", "evol"), ("ecash", "mvol"))
	return {f"{a}_{b}": litres(volumes[a] - volumes[b]) for a, b in pairs if a in volumes and b in volumes}


def compute_segment(seg: SegmentInput, label: str = "") -> SegmentResult:
	"""Full calculation for one reading row.

	net litres = basis litres - test - own use
	amount     = net litres x price, except on an E-cash basis where the cash meter is
	             exact: amount = delta cash - (test + own use) x price
	"""
	if not seg.meters:
		raise CalcError("FMS-S101", f"{label} has no meter readings")
	deltas = {k: meter_delta(p, f"{label} {k}".strip()) for k, p in seg.meters.items()}
	volumes = {k: litres(to_litres(k, d, seg.price)) for k, d in deltas.items()}
	basis = choose_basis(seg.basis, volumes)
	basis_l = volumes[basis]

	net = litres(basis_l - seg.test_l - seg.own_use_l)
	if net < 0:
		raise CalcError(
			"FMS-S116",
			f"{label} test and own-use litres ({seg.test_l + seg.own_use_l}) exceed metered litres ({basis_l})",
		)
	if basis == "ecash":
		amount = money(deltas["ecash"] - (seg.test_l + seg.own_use_l) * seg.price)
	else:
		amount = money(net * seg.price)

	drift = compute_drift(volumes)
	limit = drift_limit(basis_l, seg.drift_tolerance_l, seg.drift_tolerance_pct)
	breaches = [name for name, value in drift.items() if abs(value) > limit]
	return SegmentResult(
		deltas={k: round(v, 6) for k, v in deltas.items()},
		volumes=volumes,
		basis_meter=basis,
		basis_volume_l=basis_l,
		net_volume_l=net,
		amount=amount,
		drift=drift,
		drift_breaches=breaches,
	)
```

### 1.5 `forecourt/calc/segments.py`

**Tasks:** FMS-F07, FMS-F08 · 69 lines

Splits a shift into price segments from the Fuel Price Changes that fall inside it, and finds the price in force at a moment.

```python
# forecourt/calc/segments.py
"""Price segments inside a shift (design guide 6.5a).

Used by: shift pre-fill (FMS-F02), Fuel Price Change -> open shift (FMS-F07),
credit sale pricing (FMS-F08).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from .errors import CalcError


@dataclass(frozen=True)
class PriceChange:
	effective_at: datetime
	price: float
	source: str | None = None  # Fuel Price Change name


@dataclass(frozen=True)
class Segment:
	segment_no: int
	price: float
	start: datetime
	end: datetime
	source: str | None = None


def build_segments(
	opening_price: float,
	shift_start: datetime,
	shift_end: datetime,
	changes: Sequence[PriceChange] = (),
) -> list[Segment]:
	"""Split [shift_start, shift_end) into price segments for one item.

	`opening_price` is the price in force at shift_start. Changes outside the window are
	ignored; two changes at the same instant keep the later one in the list. A change to
	the same price does not start a new segment.
	"""
	if shift_end <= shift_start:
		raise CalcError("FMS-S110", "Shift end must be after shift start")
	inside = sorted((c for c in changes if shift_start < c.effective_at < shift_end), key=lambda c: c.effective_at)

	segments: list[Segment] = []
	cur_start, cur_price, cur_src = shift_start, opening_price, None
	for change in inside:
		if change.effective_at == cur_start:  # same instant: replace
			cur_price, cur_src = change.price, change.source
			continue
		if change.price == cur_price:
			continue
		segments.append(Segment(len(segments) + 1, cur_price, cur_start, change.effective_at, cur_src))
		cur_start, cur_price, cur_src = change.effective_at, change.price, change.source
	segments.append(Segment(len(segments) + 1, cur_price, cur_start, shift_end, cur_src))
	return segments


def price_at(moment: datetime, segments: Sequence[Segment]) -> Segment:
	"""Segment in force at `moment` (start inclusive, end exclusive; the shift end belongs to the last)."""
	for seg in segments:
		if seg.start <= moment < seg.end:
			return seg
	if segments and moment == segments[-1].end:
		return segments[-1]
	raise CalcError("FMS-S117", f"{moment} is outside the shift")
```

### 1.6 `forecourt/calc/wetstock.py`

**Tasks:** FMS-D05, FMS-E03, FMS-F05 · 139 lines

Tank reconciliation (expected vs dipped), tolerance and approval limits, manifolded tanks, and delivery variance.

```python
# forecourt/calc/wetstock.py
"""Tank reconciliation, tolerances and delivery variance.

Used by: Shift Tank Dip rows (FMS-F05), GRN delivery dips (FMS-E03), Wetstock Ledger
(FMS-F15), wetstock reports (FMS-H04). Design guide sections 5.4–5.6.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import CalcError
from .numbers import litres


@dataclass(frozen=True)
class Tolerance:
	pct: float = 0.5  # percent of sales
	litres: float = 20.0  # absolute floor
	approval_multiplier: float = 2.0

	def limit(self, base_l: float) -> float:
		return max(self.litres, abs(base_l) * self.pct / 100)


@dataclass(frozen=True)
class TankMovement:
	tank: str
	opening_l: float
	receipts_l: float = 0.0
	sales_l: float = 0.0
	own_use_l: float = 0.0
	transfers_l: float = 0.0  # in minus out
	dip_l: float | None = None
	manifold_group: str | None = None


@dataclass
class TankResult:
	tank: str
	expected_l: float
	dip_l: float | None
	variance_l: float | None
	variance_pct: float | None
	limit_l: float
	within_tolerance: bool
	needs_reason: bool
	needs_approval: bool


def expected_closing(m: TankMovement) -> float:
	return litres(m.opening_l + m.receipts_l - m.sales_l - m.own_use_l + m.transfers_l)


def reconcile(m: TankMovement, tol: Tolerance) -> TankResult:
	"""Expected vs dipped stock for one tank.

	variance  = dip - expected  (negative = loss)
	variance% = variance / sales x 100 (None when nothing was sold)
	Outside the limit a reason is needed; beyond limit x multiplier, an approval.
	"""
	expected = expected_closing(m)
	limit = tol.limit(m.sales_l)
	if m.dip_l is None:
		return TankResult(m.tank, expected, None, None, None, limit, True, False, False)
	if m.dip_l < 0:
		raise CalcError("FMS-T202", f"Dip for {m.tank} cannot be negative")
	variance = litres(m.dip_l - expected)
	pct = round(variance / m.sales_l * 100, 3) if m.sales_l else None
	within = abs(variance) <= limit
	return TankResult(
		tank=m.tank,
		expected_l=expected,
		dip_l=litres(m.dip_l),
		variance_l=variance,
		variance_pct=pct,
		limit_l=limit,
		within_tolerance=within,
		needs_reason=not within,
		needs_approval=abs(variance) > limit * tol.approval_multiplier,
	)


def reconcile_manifolds(movements: Iterable[TankMovement], tol: Tolerance) -> dict[str, TankResult]:
	"""Tanks joined by a manifold share product, so only their total is meaningful.

	Returns one result per tank for unmanifolded tanks and one per manifold group
	(keyed "manifold:<group>") for the rest.
	"""
	results: dict[str, TankResult] = {}
	groups: dict[str, list[TankMovement]] = defaultdict(list)
	for m in movements:
		if m.manifold_group:
			groups[m.manifold_group].append(m)
		else:
			results[m.tank] = reconcile(m, tol)
	for group, members in groups.items():
		dips = [m.dip_l for m in members]
		total = TankMovement(
			tank=f"manifold:{group}",
			opening_l=sum(m.opening_l for m in members),
			receipts_l=sum(m.receipts_l for m in members),
			sales_l=sum(m.sales_l for m in members),
			own_use_l=sum(m.own_use_l for m in members),
			transfers_l=sum(m.transfers_l for m in members),
			dip_l=None if any(d is None for d in dips) else sum(dips),
		)
		results[total.tank] = reconcile(total, tol)
	return results


@dataclass(frozen=True)
class DeliveryDip:
	volume_before_l: float
	volume_after_l: float
	sales_during_drop_l: float
	invoiced_l: float


@dataclass
class DeliveryResult:
	received_l: float
	variance_l: float
	variance_pct: float
	needs_reason: bool


def delivery_variance(d: DeliveryDip, tolerance_pct: float = 0.3) -> DeliveryResult:
	"""received = after - before + sold during the drop; variance = received - invoiced.

	Only shortages beyond the tolerance need a reason; gains are reported, not blocked.
	"""
	if d.invoiced_l <= 0:
		raise CalcError("FMS-T206", "Invoiced quantity must be greater than zero")
	received = litres(d.volume_after_l - d.volume_before_l + d.sales_during_drop_l)
	variance = litres(received - d.invoiced_l)
	pct = round(variance / d.invoiced_l * 100, 3)
	return DeliveryResult(received, variance, pct, needs_reason=pct < -tolerance_pct)
```

### 1.7 `forecourt/calc/cashier.py`

**Tasks:** FMS-D06, FMS-F10, FMS-F11 · 62 lines

The cashier balance: expected, accounted, difference, and whether resolution lines clear it.

```python
# forecourt/calc/cashier.py
"""Cashier balance (design guide 7.2).

Used by: Shift Cashier rows (FMS-F10), resolutions (FMS-F11), Cashier Ledger (FMS-F15).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .numbers import money


@dataclass(frozen=True)
class CashCount:
	currency: str
	amount: float  # in that currency
	exchange_rate: float = 1.0  # to company currency


@dataclass(frozen=True)
class CashierInput:
	fuel_amount: float
	item_amount: float = 0.0
	debt_receipts: float = 0.0
	float_amount: float = 0.0
	cash_counts: tuple[CashCount, ...] = ()
	mobile: float = 0.0
	card: float = 0.0
	credit: float = 0.0
	voucher: float = 0.0
	expenses: float = 0.0
	drops: float = 0.0
	resolutions: float = 0.0  # signed: + clears a shortage, - clears an excess


@dataclass
class CashierResult:
	expected: float
	cash_counted: float  # company currency, float already subtracted
	accounted: float
	difference: float  # accounted - expected; < 0 shortage
	unresolved: float  # difference after resolution lines
	resolved: bool


def cash_in_company_currency(counts: Iterable[CashCount]) -> float:
	return money(sum(c.amount * c.exchange_rate for c in counts))


def balance(c: CashierInput, precision: int = 2) -> CashierResult:
	"""EXPECTED = fuel + items + debt receipts
	ACCOUNTED = (cash counted - float) + mobile + card + credit + voucher + expenses + drops
	DIFFERENCE = ACCOUNTED - EXPECTED
	A shift may close only when DIFFERENCE + resolutions == 0 (FMS-S105).
	"""
	expected = money(c.fuel_amount + c.item_amount + c.debt_receipts, precision)
	cash = money(cash_in_company_currency(c.cash_counts) - c.float_amount, precision)
	accounted = money(cash + c.mobile + c.card + c.credit + c.voucher + c.expenses + c.drops, precision)
	difference = money(accounted - expected, precision)
	unresolved = money(difference + c.resolutions, precision)
	return CashierResult(expected, cash, accounted, difference, unresolved, unresolved == 0)
```

### 1.8 `forecourt/calc/attribution.py`

**Tasks:** FMS-D07, FMS-F15, FMS-H02, FMS-H03 · 119 lines

Spreads a cashier's payments over their sales lines so the Sales Ledger can answer "how was this nozzle paid for". Exact payments (credit, POS) are kept; the rest is proportional, rounded so every row and column matches to the cent.

```python
# forecourt/calc/attribution.py
"""Payment attribution for the Sales Ledger (design guide 10.4).

Answers "how was each product, nozzle and tank paid for" when the real link only
exists per cashier. Exact rows (credit slips, POS invoices, handheld sales) are kept
as they are. The cashier's remaining payments are spread over the remaining sales in
proportion to value, in integer minor units, so every row total and every payment
total matches to the cent.

Used by: posting/ledgers.py (FMS-F15), reports (FMS-H02, FMS-H03).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .errors import CalcError
from .numbers import from_minor, to_minor

SHORTAGE = "Shortage"  # sales not covered by any payment (cashier short)


@dataclass(frozen=True)
class SalesLine:
	key: str  # e.g. "NOZ:KE-NBO-WSTL-D01-N1" or "ITEM:LUBE-1L"
	amount: float


@dataclass(frozen=True)
class ExactPayment:
	key: str  # the sales line it belongs to
	payment_type: str
	amount: float


@dataclass(frozen=True)
class AttributedRow:
	key: str
	payment_type: str
	amount: float
	basis: str  # "Exact" or "Attributed"


def attribute(
	lines: Sequence[SalesLine],
	exact: Sequence[ExactPayment],
	payments: dict[str, float],
	precision: int = 2,
	residual_type: str = "Cash",
) -> list[AttributedRow]:
	"""Spread `payments` (type -> amount) over what is left of each sales line.

	1. Remaining per line = line amount - its exact payments (never below zero).
	2. If payments are less than the remaining sales, the gap becomes SHORTAGE.
	   If they are more (an excess), the excess is taken off `residual_type` first,
	   then off the other types in order, because an excess is not a sale.
	3. Integer matrix rounding: floor every cell, then hand out the missing minor units
	   by largest fraction while both the row and the column still need them.
	"""
	line_total = {ln.key: to_minor(ln.amount, precision) for ln in lines}
	exact_by_line: dict[str, int] = defaultdict(int)
	rows: list[AttributedRow] = []
	for e in exact:
		if e.key not in line_total:
			raise CalcError("FMS-S118", f"Exact payment for unknown sales line {e.key}")
		exact_by_line[e.key] += to_minor(e.amount, precision)
		rows.append(AttributedRow(e.key, e.payment_type, e.amount, "Exact"))

	remaining = {k: max(0, v - exact_by_line[k]) for k, v in line_total.items()}
	need = sum(remaining.values())
	pay = {t: to_minor(a, precision) for t, a in payments.items() if to_minor(a, precision) > 0}
	have = sum(pay.values())

	if have < need:
		pay[SHORTAGE] = need - have
	elif have > need:
		excess = have - need
		order = [residual_type] + [t for t in pay if t != residual_type]
		for t in order:
			if t in pay and excess:
				cut = min(pay[t], excess)
				pay[t] -= cut
				excess -= cut
		pay = {t: a for t, a in pay.items() if a > 0}

	if need == 0:
		return rows

	keys = [k for k in remaining if remaining[k] > 0]
	types = list(pay)
	cell: dict[tuple[str, str], int] = {}
	frac: list[tuple[float, str, str]] = []
	for t in types:
		for k in keys:
			ideal = pay[t] * remaining[k] / need
			base = int(ideal)
			cell[(k, t)] = base
			frac.append((ideal - base, k, t))

	row_gap = {k: remaining[k] - sum(cell[(k, t)] for t in types) for k in keys}
	col_gap = {t: pay[t] - sum(cell[(k, t)] for k in keys) for t in types}
	for _, k, t in sorted(frac, reverse=True):
		if row_gap[k] > 0 and col_gap[t] > 0:
			cell[(k, t)] += 1
			row_gap[k] -= 1
			col_gap[t] -= 1
	# Fallback: greedy can leave a few units when fractions are tied; any cell will do.
	for k in keys:
		for t in types:
			while row_gap[k] > 0 and col_gap[t] > 0:
				cell[(k, t)] += 1
				row_gap[k] -= 1
				col_gap[t] -= 1

	for (k, t), units in cell.items():
		if units:
			rows.append(AttributedRow(k, t, from_minor(units, precision), "Attributed"))
	return rows
```

### 1.9 `forecourt/tests/test_calc.py`

**Tasks:** FMS-D08 · 243 lines

The unit tests, including the design guide's worked examples. Run without a bench: `python -m unittest forecourt.tests.test_calc`.

```python
# forecourt/tests/test_calc.py
"""Unit tests for forecourt.calc (FMS-D02 … FMS-D08).

No database. Run inside the bench:
    bench --site test_fms run-tests --app forecourt --module forecourt.tests.test_calc
or outside it (plain Python, from the app root):
    python -m unittest forecourt.tests.test_calc
"""

from __future__ import annotations

import random
import unittest
from datetime import datetime

try:  # inside a bench (v15+)
	from frappe.tests.classes import UnitTestCase as TestCase
except ImportError:  # plain Python
	TestCase = unittest.TestCase

from forecourt.calc.attribution import SHORTAGE, ExactPayment, SalesLine, attribute
from forecourt.calc.calibration import ChartRow, product_volume, validate_chart, volume_at
from forecourt.calc.cashier import CashCount, CashierInput, balance
from forecourt.calc.errors import CalcError
from forecourt.calc.meters import MeterPair, SegmentInput, compute_segment, meter_delta
from forecourt.calc.numbers import rnd
from forecourt.calc.segments import PriceChange, build_segments, price_at
from forecourt.calc.wetstock import (
	DeliveryDip,
	TankMovement,
	Tolerance,
	delivery_variance,
	reconcile,
	reconcile_manifolds,
)

CHART = [ChartRow(0, 0), ChartRow(100, 500), ChartRow(200, 1200), ChartRow(300, 2100)]


class TestRounding(TestCase):
	def test_half_up(self):
		self.assertEqual(rnd(2.675, 2), 2.68)  # float repr would give 2.67 with round()
		self.assertEqual(rnd(-0.005, 2), -0.01)


class TestCalibration(TestCase):
	def test_exact_row(self):
		self.assertEqual(volume_at(200, CHART), 1200)

	def test_interpolates(self):
		self.assertEqual(volume_at(150, CHART), 850)

	def test_out_of_range(self):
		with self.assertRaises(CalcError) as e:
			volume_at(301, CHART)
		self.assertEqual(e.exception.code, "FMS-T202")

	def test_water_deducted(self):
		self.assertEqual(product_volume(150, 50, CHART), (600.0, 250.0))

	def test_invalid_chart(self):
		with self.assertRaises(CalcError):
			validate_chart([ChartRow(0, 0), ChartRow(10, 0)])

	def test_capacity_warning(self):
		self.assertTrue(validate_chart(CHART, capacity_l=3000))
		self.assertFalse(validate_chart(CHART, capacity_l=2100))


class TestMeters(TestCase):
	def test_plain_delta(self):
		self.assertEqual(meter_delta(MeterPair(100, 250)), 150)

	def test_closing_below_opening(self):
		with self.assertRaises(CalcError) as e:
			meter_delta(MeterPair(250, 100))
		self.assertEqual(e.exception.code, "FMS-S101")

	def test_rollover(self):
		self.assertEqual(meter_delta(MeterPair(999_900, 50, rollover=True, modulus=1_000_000)), 150)

	def test_rollover_needs_modulus(self):
		with self.assertRaises(CalcError) as e:
			meter_delta(MeterPair(999_900, 50, rollover=True))
		self.assertEqual(e.exception.code, "FMS-W102")

	def test_ecash_basis(self):
		r = compute_segment(SegmentInput(price=180, meters={"ecash": MeterPair(0, 216_900)}, test_l=5))
		self.assertEqual(r.basis_volume_l, 1205)
		self.assertEqual(r.net_volume_l, 1200)
		self.assertEqual(r.amount, 216_000)

	def test_highest_picks_largest(self):
		r = compute_segment(
			SegmentInput(
				price=100,
				basis="highest",
				meters={"ecash": MeterPair(0, 100_000), "evol": MeterPair(0, 1001), "mvol": MeterPair(0, 999)},
			)
		)
		self.assertEqual(r.basis_meter, "evol")
		self.assertEqual(r.amount, 100_100)

	def test_drift_breach(self):
		r = compute_segment(
			SegmentInput(price=100, basis="evol", meters={"evol": MeterPair(0, 1000), "mvol": MeterPair(0, 980)})
		)
		self.assertEqual(r.drift, {"evol_mvol": 20})
		self.assertEqual(r.drift_breaches, ["evol_mvol"])  # limit = max(2, 5) = 5

	def test_basis_not_recorded(self):
		with self.assertRaises(CalcError):
			compute_segment(SegmentInput(price=100, basis="mvol", meters={"evol": MeterPair(0, 10)}))

	def test_tests_exceed_sales(self):
		with self.assertRaises(CalcError):
			compute_segment(SegmentInput(price=100, basis="evol", meters={"evol": MeterPair(0, 3)}, test_l=5))


class TestSegments(TestCase):
	start, end = datetime(2026, 10, 20, 6), datetime(2026, 10, 20, 18)

	def test_single_segment(self):
		segs = build_segments(180, self.start, self.end)
		self.assertEqual(len(segs), 1)

	def test_mid_shift_change(self):
		segs = build_segments(180, self.start, self.end, [PriceChange(datetime(2026, 10, 20, 14), 182, "FPC-1")])
		self.assertEqual([(s.segment_no, s.price) for s in segs], [(1, 180), (2, 182)])
		self.assertEqual(price_at(datetime(2026, 10, 20, 13, 59), segs).price, 180)
		self.assertEqual(price_at(datetime(2026, 10, 20, 14), segs).price, 182)
		self.assertEqual(price_at(self.end, segs).price, 182)

	def test_same_price_ignored_and_outside_ignored(self):
		segs = build_segments(
			180,
			self.start,
			self.end,
			[PriceChange(datetime(2026, 10, 20, 9), 180), PriceChange(datetime(2026, 10, 21, 9), 190)],
		)
		self.assertEqual(len(segs), 1)


class TestWetstock(TestCase):
	def test_guide_example(self):
		r = reconcile(TankMovement("T1", opening_l=18_400, sales_l=2_200, dip_l=16_192), Tolerance())
		self.assertEqual(r.expected_l, 16_200)
		self.assertEqual(r.variance_l, -8)
		self.assertEqual(r.variance_pct, -0.364)
		self.assertTrue(r.within_tolerance)  # limit = max(20, 11) = 20

	def test_needs_approval(self):
		r = reconcile(TankMovement("T1", opening_l=10_000, sales_l=1_000, dip_l=8_950), Tolerance())
		self.assertTrue(r.needs_reason)
		self.assertTrue(r.needs_approval)  # 50 > 20 x 2

	def test_manifold(self):
		res = reconcile_manifolds(
			[
				TankMovement("T2", 5000, sales_l=500, dip_l=4600, manifold_group="AGO"),
				TankMovement("T3", 5000, sales_l=500, dip_l=4400, manifold_group="AGO"),
			],
			Tolerance(),
		)
		self.assertEqual(res["manifold:AGO"].variance_l, 0)

	def test_delivery(self):
		d = delivery_variance(DeliveryDip(4_000, 13_900, 80, 10_000))
		self.assertEqual(d.received_l, 9_980)
		self.assertEqual(d.variance_pct, -0.2)
		self.assertFalse(d.needs_reason)


class TestCashier(TestCase):
	def test_guide_example(self):
		r = balance(
			CashierInput(
				fuel_amount=369_000,
				item_amount=3_500,
				float_amount=5_000,
				cash_counts=(CashCount("KES", 121_500),),
				mobile=180_000,
				card=40_000,
				credit=34_000,
				expenses=1_500,
			)
		)
		self.assertEqual((r.expected, r.accounted, r.difference), (372_500, 372_000, -500))
		self.assertFalse(r.resolved)

	def test_resolution_clears(self):
		r = balance(CashierInput(fuel_amount=1000, cash_counts=(CashCount("KES", 990),), resolutions=10))
		self.assertTrue(r.resolved)

	def test_multi_currency(self):
		r = balance(CashierInput(fuel_amount=13_000, cash_counts=(CashCount("USD", 100, 130),)))
		self.assertEqual(r.difference, 0)


class TestAttribution(TestCase):
	def _sums(self, rows):
		by_key, by_type = {}, {}
		for r in rows:
			by_key[r.key] = rnd(by_key.get(r.key, 0) + r.amount, 2)
			by_type[r.payment_type] = rnd(by_type.get(r.payment_type, 0) + r.amount, 2)
		return by_key, by_type

	def test_guide_example(self):
		rows = attribute(
			[SalesLine("PMS", 108_000), SalesLine("AGO", 72_000)], [], {"Mobile Money": 180_000}
		)
		self.assertEqual({(r.key, r.amount) for r in rows}, {("PMS", 108_000), ("AGO", 72_000)})

	def test_exact_kept_and_shortage(self):
		rows = attribute(
			[SalesLine("AGO", 153_000), SalesLine("PMS", 216_000)],
			[ExactPayment("AGO", "Credit", 34_000)],
			{"Cash": 300_000, "Mobile Money": 34_500},
		)
		by_key, by_type = self._sums(rows)
		self.assertEqual(by_key, {"AGO": 153_000, "PMS": 216_000})
		self.assertEqual(by_type[SHORTAGE], 500)

	def test_excess_removed_from_cash(self):
		rows = attribute([SalesLine("PMS", 100)], [], {"Cash": 60, "Card": 50})
		_, by_type = self._sums(rows)
		self.assertEqual(by_type, {"Cash": 50, "Card": 50})

	def test_random_totals_balance(self):
		rng = random.Random(42)
		for _ in range(300):
			lines = [SalesLine(f"L{i}", rnd(rng.uniform(0, 5000), 2)) for i in range(rng.randint(1, 8))]
			total = sum(ln.amount for ln in lines)
			split = [rng.random() for _ in range(3)]
			pays = {t: rnd(total * s / sum(split) * rng.uniform(0.95, 1.05), 2) for t, s in zip(("Cash", "Mobile Money", "Card"), split)}
			rows = attribute(lines, [], pays)
			by_key, _ = self._sums(rows)
			for ln in lines:
				self.assertAlmostEqual(by_key.get(ln.key, 0), ln.amount, places=2)
			self.assertTrue(all(r.amount >= 0 for r in rows))


if __name__ == "__main__":
	unittest.main()
```

---

## 2. Errors and gates (`forecourt/errors.py`)

All user-facing validation goes through one catalogue, so every message carries a code, the specifics and the fix (design guide 15.3). `GateCollector` collects problems and raises once, so a manager sees every reason a shift cannot close in one message, not one per save.

### 2.1 `forecourt/errors.py`

**Tasks:** FMS-F12, FMS-K04 · 105 lines

Codes: S1xx shift, T2xx tank, W1xx warnings, P3xx posting setup, I4xx import, C5xx corrections.

```python
# forecourt/errors.py
"""FMS error catalogue and the gate collector (design guide 15.3).

Every user-facing validation goes through here so messages carry a code, a cause and
a fix, and so a shift shows all of its problems at once instead of one per save.
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _


class FMSValidationError(frappe.ValidationError):
	pass


# code -> (title, fix). Messages are built at the call site with the specifics.
CATALOGUE: dict[str, tuple[str, str]] = {
	"FMS-S101": ("Meter reading", "Correct the reading, or tick Rollover if the meter passed its maximum."),
	"FMS-S102": ("Opening mismatch", "Use Re-fetch openings, or check the previous shift and its corrections."),
	"FMS-S103": ("Missing dip", "Enter the closing dip for every tank that requires one."),
	"FMS-S104": ("Unassigned reading", "Assign every reading row to a cashier."),
	"FMS-S105": ("Unresolved cash difference", "Add a resolution line (charge to cashier, write off, or excess)."),
	"FMS-S106": ("Tank variance", "Choose a reason; above the approval limit, send the shift for approval."),
	"FMS-S107": ("Credit limit", "Ask the area manager to approve, or collect payment first."),
	"FMS-S108": ("Credit exceeds meters", "Check the slip's product and quantity, and the meter readings."),
	"FMS-S109": ("Expense", "Choose an expense type and keep the amount within its limit; attach the receipt."),
	"FMS-S110": ("Shift window", "Fix the shift date or template; windows may not overlap."),
	"FMS-S111": ("Unmatched payments", "Assign every payment received on the station's tills to a cashier."),
	"FMS-S112": ("Price segment readings", "Enter the meter readings taken when the price changed."),
	"FMS-S113": ("Draft own use", "Submit or delete the draft Fuel Own Use entry."),
	"FMS-S114": ("Duplicate reference", "Remove the duplicate payment row."),
	"FMS-S115": ("Sales basis", "Record the meter used as sales basis, or change the basis."),
	"FMS-S116": ("Test and own use", "Test and own-use litres cannot exceed the metered litres."),
	"FMS-S117": ("Outside shift", "The time must be inside the shift window."),
	"FMS-S118": ("Attribution", "Internal error: report it with the shift name."),
	"FMS-T201": ("Calibration chart", "Add or re-date the chart, or switch the tank to litres entry."),
	"FMS-T202": ("Dip out of range", "Re-check the dip and the tank."),
	"FMS-T203": ("Unexplained tank rise", "Post the GRN for the delivery (or fix its time or tank), then re-check."),
	"FMS-T204": ("Draft GRN", "Complete the delivery dips and submit the GRN."),
	"FMS-T205": ("Invalid chart", "Depths and volumes must both increase on every row."),
	"FMS-T206": ("Delivery", "Check the GRN quantities."),
	"FMS-W103": ("Meter drift", "Check the pump's price and meters, then record the reason."),
	"FMS-P301": ("Posting setup", "Complete the accounts in Station, Mode of Payment or Forecourt Company Settings."),
	"FMS-I401": ("Import file", "Check the provider's import mapping against the file's columns."),
	"FMS-I402": ("Import row", "Fix the row in the file, or enter the payment by hand."),
	"FMS-C501": ("Correction", "Send the correction for director approval."),
	"FMS-C502": ("Locked document", "This document belongs to a closed shift. Use a Shift Correction."),
}


def fms_throw(code: str, message: str) -> None:
	"""Raise one coded error immediately."""
	title, fix = CATALOGUE.get(code, (code, ""))
	frappe.throw(f"<b>{code}</b> {message}<br><small>{_(fix)}</small>", FMSValidationError, title=_(title))


@dataclass
class Problem:
	code: str
	message: str


class GateCollector:
	"""Collect every failing gate, then raise once with the full list.

	with GateCollector() as gates:
	    gates.check(cond, "FMS-S103", _("Tank {0} has no closing dip").format(tank))
	"""

	def __init__(self) -> None:
		self.problems: list[Problem] = []

	def add(self, code: str, message: str) -> None:
		self.problems.append(Problem(code, message))

	def check(self, ok: bool, code: str, message: str) -> None:
		if not ok:
			self.add(code, message)

	def __enter__(self) -> GateCollector:
		return self

	def __exit__(self, exc_type, exc, tb) -> bool:
		if exc_type is None and self.problems:
			self.raise_all()
		return False

	def raise_all(self) -> None:
		items = "".join(
			f"<li><b>{p.code}</b> {p.message}<br><small>{_(CATALOGUE.get(p.code, ('', ''))[1])}</small></li>"
			for p in self.problems
		)
		frappe.throw(
			f"<p>{_('This shift cannot be closed yet:')}</p><ul>{items}</ul>",
			FMSValidationError,
			title=_("{0} problem(s) to fix").format(len(self.problems)),
		)


def from_calc_error(err) -> None:
	"""Turn a forecourt.calc CalcError into a user message."""
	fms_throw(err.code, err.message)
```

---

## 3. Global helpers (`forecourt/utils`)

The functions most other code calls. Nothing outside this package reads settings fields, computes shift windows or queries previous shifts directly; that keeps the rules in one place.

### 3.1 `forecourt/utils/settings.py`

**Tasks:** FMS-C02, FMS-C03 · 101 lines

Effective settings with the precedence site → company → station → tank or dispenser, memoised per request.

```python
# forecourt/utils/settings.py
"""Effective settings: site defaults -> company -> station -> tank or dispenser.

One function answers "which rule applies here", so no controller reads settings
fields directly. Used by almost every task from FMS-C02 on.
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe

METERS = ("ecash", "evol", "mvol")


@dataclass(frozen=True)
class EffectiveSettings:
	company: str
	station: str
	dip_entry_mode: str  # "Depth via calibration chart" | "Litres entered directly"
	meters: tuple[str, ...]  # recorded meters, e.g. ("ecash",)
	sales_basis: str  # "ecash" | "evol" | "mvol" | "highest"
	drift_tolerance_l: float
	drift_tolerance_pct: float
	drift_requires_reason: bool
	price_change_mode: str  # "Latest price with segments" | "Between shifts only"
	allow_time_estimated_segments: bool
	tank_tolerance_pct: float
	tank_tolerance_l: float
	approval_multiplier: float
	delivery_tolerance_pct: float
	small_difference_pct: float
	small_difference_amount: float
	delivery_dips_required: bool
	background_close_threshold: int
	post_tank_variance: str
	sales_posting_mode: str


_BASIS = {"E-cash": "ecash", "E-vol": "evol", "M-vol": "mvol", "Highest": "highest"}


def _cache() -> dict:
	"""Per-request memo. Settings rarely change, and a shift reads them dozens of times."""
	if not hasattr(frappe.local, "fms_settings_cache"):
		frappe.local.fms_settings_cache = {}
	return frappe.local.fms_settings_cache


def get_settings(station: str, tank: str | None = None, dispenser: str | None = None) -> EffectiveSettings:
	key = (station, tank, dispenser)
	cache = _cache()
	if key in cache:
		return cache[key]

	site = frappe.get_cached_doc("Forecourt Settings")
	st = frappe.get_cached_doc("Station", station)
	co = frappe.get_cached_doc("Forecourt Company Settings", st.company)
	tk = frappe.get_cached_doc("Fuel Tank", tank) if tank else None
	dp = frappe.get_cached_doc("Dispenser", dispenser) if dispenser else None

	meters = tuple(m for m in METERS if site.get(f"record_{m}"))
	if not st.use_settings_meters:
		meters = tuple(m for m in METERS if st.get(f"record_{m}"))
	if dp and dp.meters_override:
		meters = tuple(m for m in METERS if dp.get(f"record_{m}"))

	result = EffectiveSettings(
		company=st.company,
		station=station,
		dip_entry_mode=(tk and tk.dip_entry_mode) or st.dip_entry_mode or site.dip_entry_mode,
		meters=meters,
		sales_basis=_BASIS[st.sales_basis or site.sales_basis],
		drift_tolerance_l=site.drift_tolerance_l,
		drift_tolerance_pct=site.drift_tolerance_pct,
		drift_requires_reason=bool(site.drift_requires_reason),
		price_change_mode=st.price_change_mode or site.price_change_mode,
		allow_time_estimated_segments=bool(site.allow_time_estimated_segments),
		tank_tolerance_pct=(tk and tk.tolerance_pct) or co.tank_tolerance_pct,
		tank_tolerance_l=(tk and tk.tolerance_l) or co.tank_tolerance_l,
		approval_multiplier=co.approval_multiplier,
		delivery_tolerance_pct=co.delivery_tolerance_pct,
		small_difference_pct=co.small_difference_pct,
		small_difference_amount=co.small_difference_amount or 0,
		delivery_dips_required=bool(st.delivery_dips_required),
		background_close_threshold=site.background_close_threshold or 200,
		post_tank_variance=co.post_tank_variance,
		sales_posting_mode=co.sales_posting_mode,
	)
	cache[key] = result
	return result


def company_accounts(company: str) -> frappe._dict:
	"""The FMS account mapping for a company (Forecourt Company Settings)."""
	return frappe.get_cached_doc("Forecourt Company Settings", company)


def clear_settings_cache(doc=None, method=None) -> None:
	"""doc_events on_update for the settings DocTypes: drop the per-request memo."""
	frappe.local.fms_settings_cache = {}
```

### 3.2 `forecourt/utils/time.py`

**Tasks:** FMS-E02, FMS-F02 · 84 lines

Station time zones and shift windows. Overnight templates (end before start) end on the next day. The database stores system time; conversion happens only here.

```python
# forecourt/utils/time.py
"""Station time zones and shift windows.

Frappe stores Datetime fields as naive values in the *system* time zone. Shift
templates are written in the *station's* local clock (06:00 means 06:00 at the
station). These helpers convert between the two so windows are right for stations
in other countries than the server.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, get_system_timezone, getdate, now_datetime


def station_tz(station: str) -> ZoneInfo:
	tz = frappe.get_cached_value("Station", station, "timezone") or get_system_timezone()
	return ZoneInfo(tz)


def to_system(local: datetime, station: str) -> datetime:
	"""Station-local naive datetime -> system-time-zone naive datetime (what Frappe stores)."""
	aware = local.replace(tzinfo=station_tz(station))
	return aware.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def to_station(system_dt: datetime, station: str) -> datetime:
	"""System naive datetime -> station-local naive datetime (for display and day boundaries)."""
	aware = get_datetime(system_dt).replace(tzinfo=ZoneInfo(get_system_timezone()))
	return aware.astimezone(station_tz(station)).replace(tzinfo=None)


def station_now(station: str) -> datetime:
	return to_station(now_datetime(), station)


def station_today(station: str) -> date:
	return station_now(station).date()


def _as_time(value) -> time:
	"""Time fields come back as timedelta from the database and as str from forms."""
	if isinstance(value, time):
		return value
	if isinstance(value, timedelta):
		return (datetime.min + value).time()
	return datetime.strptime(str(value), "%H:%M:%S").time()


def shift_window(template: str, shift_date: date | str) -> tuple[datetime, datetime]:
	"""(start, end) in system time for `template` worked on `shift_date` (station-local date).

	An end time at or before the start time means the shift runs past midnight:
	Night 18:00–06:00 on the 20th ends at 06:00 on the 21st.
	"""
	t = frappe.get_cached_doc("Forecourt Shift Template", template)
	d = getdate(shift_date)
	start_local = datetime.combine(d, _as_time(t.start_time))
	end_local = datetime.combine(d, _as_time(t.end_time))
	if end_local <= start_local:
		end_local += timedelta(days=1)
	return to_system(start_local, t.station), to_system(end_local, t.station)


def guess_template(station: str, at: datetime | None = None) -> tuple[str | None, date]:
	"""The template whose window contains `at` (station now by default), and its shift date.

	Used to default a new shift. Checks yesterday's overnight templates first.
	"""
	local = to_station(at, station) if at else station_now(station)
	templates = frappe.get_all(
		"Forecourt Shift Template",
		filters={"station": station, "active": 1},
		pluck="name",
		order_by="sequence asc",
	)
	for day in (local.date() - timedelta(days=1), local.date()):
		for name in templates:
			start, end = shift_window(name, day)
			if to_station(start, station) <= local < to_station(end, station):
				return name, day
	return (templates[0] if templates else None), local.date()
```

### 3.3 `forecourt/utils/shifts.py`

**Tasks:** FMS-F02, FMS-E05, FMS-F07, FMS-G03, FMS-J04 · 140 lines

Current, open, previous, next and latest closed shift; the shift covering a moment; overlap checks. Everything orders by `shift_start`, never by `creation` or `name` (the v16 default list sort is `creation`).

```python
# forecourt/utils/shifts.py
"""Shift lookups: current, open, previous, next, at a moment, latest closed.

These are the "global" helpers most of the app needs. All return document names
(strings) or None, never documents, so callers decide whether to load the full doc.
Ordering is always by shift_start, never by creation (v16 lists sort by creation by
default, which is wrong for back-dated shifts).

Used by: shift pre-fill (FMS-F02), Fuel Own Use default shift (FMS-E05), price change
segments (FMS-F07), payment matching (FMS-J04), corrections (FMS-G03).
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe.utils import get_datetime, now_datetime

SHIFT = "Forecourt Shift"
OPEN_STATUSES = ("Open", "Counting", "Reconciled", "Pending Approval", "Closing")


def get_open_shift(station: str) -> str | None:
	"""The draft (not yet closed) shift at the station, if any.

	There is at most one, enforced by `assert_single_open_shift` on insert.
	"""
	return frappe.db.get_value(
		SHIFT,
		{"station": station, "docstatus": 0, "status": ("in", OPEN_STATUSES)},
		"name",
		order_by="shift_start desc",
	)


def get_shift_at(station: str, moment: datetime | str, include_drafts: bool = True) -> str | None:
	"""The shift whose window contains `moment` (start inclusive, end exclusive)."""
	moment = get_datetime(moment)
	docstatus = ("<", 2) if include_drafts else 1
	return frappe.db.get_value(
		SHIFT,
		{
			"station": station,
			"docstatus": docstatus,
			"shift_start": ("<=", moment),
			"shift_end": (">", moment),
		},
		"name",
		order_by="shift_start desc",
	)


def get_current_shift(station: str) -> str | None:
	"""The open shift, else the closed shift covering now (a shift closed early)."""
	return get_open_shift(station) or get_shift_at(station, now_datetime())


def get_previous_shift(station: str, before: datetime | str, submitted_only: bool = True) -> str | None:
	"""The latest shift at the station that started before `before`.

	Pre-fill uses submitted_only=True: openings must come from a closed shift.
	"""
	return frappe.db.get_value(
		SHIFT,
		{
			"station": station,
			"docstatus": 1 if submitted_only else ("<", 2),
			"shift_start": ("<", get_datetime(before)),
		},
		"name",
		order_by="shift_start desc",
	)


def get_next_shift(shift: str) -> str | None:
	"""The first shift (draft or closed) after `shift` at the same station."""
	station, start = frappe.db.get_value(SHIFT, shift, ["station", "shift_start"])
	return frappe.db.get_value(
		SHIFT,
		{"station": station, "docstatus": ("<", 2), "shift_start": (">", start), "name": ("!=", shift)},
		"name",
		order_by="shift_start asc",
	)


def get_latest_closed_shift(station: str) -> str | None:
	return frappe.db.get_value(SHIFT, {"station": station, "docstatus": 1}, "name", order_by="shift_start desc")


def is_latest_closed_shift(shift: str) -> bool:
	station = frappe.db.get_value(SHIFT, shift, "station")
	return get_latest_closed_shift(station) == shift


def shifts_between(station: str, start: datetime, end: datetime, submitted_only: bool = True) -> list[str]:
	"""Shifts that overlap [start, end), oldest first. Used by reports and the day close."""
	return frappe.get_all(
		SHIFT,
		filters={
			"station": station,
			"docstatus": 1 if submitted_only else ("<", 2),
			"shift_start": ("<", end),
			"shift_end": (">", start),
		},
		pluck="name",
		order_by="shift_start asc",
	)


def assert_single_open_shift(station: str, exclude: str | None = None) -> None:
	from forecourt.errors import fms_throw

	other = get_open_shift(station)
	if other and other != exclude:
		fms_throw("FMS-S110", frappe._("Shift {0} is still open at this station. Close it first.").format(other))


def assert_no_overlap(station: str, start: datetime, end: datetime, exclude: str | None = None) -> None:
	from forecourt.errors import fms_throw

	clash = frappe.db.get_value(
		SHIFT,
		{
			"station": station,
			"docstatus": ("<", 2),
			"shift_start": ("<", end),
			"shift_end": (">", start),
			"name": ("!=", exclude or ""),
		},
		"name",
	)
	if clash:
		fms_throw("FMS-S110", frappe._("This window overlaps shift {0}").format(clash))


@frappe.whitelist()
def current_shift(station: str) -> str | None:
	"""Client helper: frappe.call('forecourt.utils.shifts.current_shift', {station})."""
	frappe.has_permission("Station", "read", station, throw=True)
	return get_current_shift(station)
```

### 3.4 `forecourt/utils/pricing.py`

**Tasks:** FMS-E09, FMS-F07 · 64 lines

The price of an item at a station at a moment, and the price changes inside a window.

```python
# forecourt/utils/pricing.py
"""Fuel prices at a moment, and price changes inside a window.

Item Price only has a valid-from *date*. Mid-day changes are therefore read from
submitted Fuel Price Change documents (effective_at is a Datetime), with Item Price as
the fallback for the very first price at a new station.
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe.query_builder import DocType
from frappe.utils import flt, get_datetime

from forecourt.calc.segments import PriceChange


def _changes_query(station: str, item: str):
	fpc = DocType("Fuel Price Change")
	fpci = DocType("Fuel Price Change Item")
	return (
		frappe.qb.from_(fpci)
		.join(fpc)
		.on(fpc.name == fpci.parent)
		.select(fpc.name, fpc.effective_at, fpci.new_price)
		.where((fpc.docstatus == 1) & (fpc.station == station) & (fpci.item == item))
	)


def get_price(station: str, item: str, at: datetime | str) -> float:
	"""Price in force at `at`: latest Fuel Price Change on or before it, else Item Price."""
	fpc = DocType("Fuel Price Change")
	rows = (
		_changes_query(station, item)
		.where(fpc.effective_at <= get_datetime(at))
		.orderby(fpc.effective_at, order=frappe.qb.desc)
		.limit(1)
		.run(as_dict=True)
	)
	if rows:
		return flt(rows[0].new_price)
	price_list = frappe.get_cached_value("Station", station, "price_list")
	rate = frappe.db.get_value(
		"Item Price",
		{"price_list": price_list, "item_code": item, "valid_from": ("<=", get_datetime(at).date())},
		"price_list_rate",
		order_by="valid_from desc",
	)
	if rate is None:
		frappe.throw(frappe._("No price for {0} at station {1}").format(item, station))
	return flt(rate)


def get_price_changes(station: str, item: str, start: datetime, end: datetime) -> list[PriceChange]:
	"""Submitted changes strictly inside (start, end), oldest first, for build_segments()."""
	fpc = DocType("Fuel Price Change")
	rows = (
		_changes_query(station, item)
		.where((fpc.effective_at > start) & (fpc.effective_at < end))
		.orderby(fpc.effective_at)
		.run(as_dict=True)
	)
	return [PriceChange(get_datetime(r.effective_at), flt(r.new_price), r.name) for r in rows]
```

### 3.5 `forecourt/utils/stock.py`

**Tasks:** FMS-C10, FMS-C12, FMS-C13, FMS-F14 · 69 lines

Tank book stock and valuation from ERPNext's stock ledger, the calibration chart valid on a date, and nozzle last readings.

```python
# forecourt/utils/stock.py
"""Tank stock and nozzle readings."""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe.utils import flt, get_datetime

from forecourt.calc.calibration import ChartRow


def tank_book_stock(tank: str, at: datetime | str) -> float:
	"""ERPNext book stock of the tank's warehouse at a moment (litres)."""
	from erpnext.stock.utils import get_stock_balance

	at = get_datetime(at)
	item, warehouse = frappe.get_cached_value("Fuel Tank", tank, ["item", "warehouse"])
	return flt(get_stock_balance(item, warehouse, at.date(), at.time()))


def tank_valuation_rate(tank: str, at: datetime | str) -> float:
	from erpnext.stock.utils import get_stock_balance

	at = get_datetime(at)
	item, warehouse = frappe.get_cached_value("Fuel Tank", tank, ["item", "warehouse"])
	_qty, rate = get_stock_balance(item, warehouse, at.date(), at.time(), with_valuation_rate=True)
	return flt(rate)


def calibration_rows(tank: str, on: datetime | str) -> tuple[list[ChartRow], list[ChartRow]]:
	"""(product rows, water rows) of the chart valid on the date. FMS-T201 when none."""
	from forecourt.errors import fms_throw

	name = frappe.db.get_value(
		"Tank Calibration Chart",
		{"tank": tank, "valid_from": ("<=", get_datetime(on).date())},
		"name",
		order_by="valid_from desc",
	)
	if not name:
		fms_throw("FMS-T201", frappe._("No calibration chart valid on {0} for tank {1}").format(on, tank))
	chart = frappe.get_cached_doc("Tank Calibration Chart", name)
	rows = [ChartRow(r.depth_mm, r.volume_l) for r in chart.rows]
	water = [ChartRow(r.depth_mm, r.volume_l) for r in chart.water_rows]
	return rows, water


def nozzle_last_readings(nozzle: str) -> dict[str, float]:
	"""Last closing value per meter, as stored on the Nozzle by shift close and Meter Change."""
	n = frappe.db.get_value("Nozzle", nozzle, ["last_ecash", "last_evol", "last_mvol"], as_dict=True)
	return {"ecash": flt(n.last_ecash), "evol": flt(n.last_evol), "mvol": flt(n.last_mvol)}


def nozzle_modulus(nozzle: str) -> dict[str, float]:
	n = frappe.get_cached_value("Nozzle", nozzle, ["ecash_max", "evol_max", "mvol_max"], as_dict=True)
	return {"ecash": flt(n.ecash_max), "evol": flt(n.evol_max), "mvol": flt(n.mvol_max)}


def set_nozzle_last_readings(nozzle: str, readings: dict[str, float], shift: str | None) -> None:
	"""Only shift close, corrections and Meter Change call this (flags.from_fms lets the write through)."""
	doc = frappe.get_doc("Nozzle", nozzle)
	for meter, value in readings.items():
		if value is not None:
			doc.set(f"last_{meter}", value)
	doc.last_reading_shift = shift
	doc.flags.from_fms = True
	doc.flags.ignore_permissions = True
	doc.save()
```

---

## 4. Shift: pre-fill, sources, recompute, gates

The shift is the centre of the system. Its controller stays thin; each concern lives in its own module under `forecourt/forecourt_shift/shift/`:

| Module | Runs | Job |
|---|---|---|
| `prefill.py` | `before_insert` | Everything the system already knows: window, previous shift, roster, reading rows with locked openings, tank rows with opening dips, price segments, settings snapshot |
| `sources.py` | inside `recompute` | Pulls GRN receipts, own use, transfers and POS sales from submitted documents in the window |
| `compute.py` | `validate` and the live `preview` | Derives every calculated field through `forecourt.calc` |
| `gates.py` | `before_submit` and the status | Lists every reason the shift cannot close |

### 4.1 `forecourt/forecourt_shift/shift/prefill.py`

**Tasks:** FMS-F02, FMS-F07 · 147 lines

```python
# forecourt/forecourt_shift/shift/prefill.py
"""Shift creation pre-fill (FMS-F02, design guide 6.3).

Everything here is "data the system already has": the manager should open a new
shift and only type closing values.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.calc.segments import build_segments
from forecourt.utils.pricing import get_price, get_price_changes
from forecourt.utils.settings import get_settings
from forecourt.utils.shifts import assert_no_overlap, assert_single_open_shift, get_previous_shift
from forecourt.utils.stock import nozzle_last_readings, tank_book_stock
from forecourt.utils.time import guess_template, shift_window

BASIS_LABEL = {"ecash": "E-cash", "evol": "E-vol", "mvol": "M-vol", "highest": "Highest"}


def prefill(doc) -> None:
	station = frappe.get_cached_doc("Station", doc.station)
	doc.company = station.company
	if not doc.shift_template:
		doc.shift_template, doc.shift_date = guess_template(doc.station)
	if not doc.shift_template:
		frappe.throw(_("Station {0} has no active shift template").format(doc.station))

	doc.shift_start, doc.shift_end = shift_window(doc.shift_template, doc.shift_date)
	assert_single_open_shift(doc.station)
	assert_no_overlap(doc.station, doc.shift_start, doc.shift_end)
	doc.previous_shift = get_previous_shift(doc.station, doc.shift_start)
	doc.status = "Open"
	template_name = frappe.get_cached_value("Forecourt Shift Template", doc.shift_template, "template_name")
	doc.shift_title = f"{station.station_name} · {template_name} · {doc.shift_date}"

	s = get_settings(doc.station)
	doc.dip_entry_mode = s.dip_entry_mode
	doc.sales_basis = BASIS_LABEL[s.sales_basis]
	doc.price_change_mode = s.price_change_mode
	for m in ("ecash", "evol", "mvol"):
		doc.set(f"record_{m}", int(m in s.meters))

	template = frappe.get_cached_doc("Forecourt Shift Template", doc.shift_template)
	add_cashiers(doc, template)
	nozzles = active_nozzles(doc.station)
	add_prices(doc, {n.item for n in nozzles})
	add_readings(doc, template, nozzles)
	add_tanks(doc)


def active_nozzles(station: str) -> list[frappe._dict]:
	return frappe.get_all(
		"Nozzle",
		filters={"station": station, "status": "Active"},
		fields=["name", "dispenser", "tank", "item", "nozzle_no"],
		order_by="dispenser asc, nozzle_no asc",
	)


def add_cashiers(doc, template) -> None:
	doc.set("cashiers", [])
	for row in template.cashiers:
		doc.append("cashiers", {"cashier": row.cashier, "float_amount": row.float_amount})


def add_prices(doc, items: set[str]) -> None:
	doc.set("prices", [])
	if doc.price_change_mode == "Between shifts only":
		changes_for = lambda item: []  # noqa: E731
	else:
		changes_for = lambda item: get_price_changes(doc.station, item, doc.shift_start, doc.shift_end)  # noqa: E731
	for item in sorted(items):
		opening = get_price(doc.station, item, doc.shift_start)
		for seg in build_segments(opening, doc.shift_start, doc.shift_end, changes_for(item)):
			doc.append(
				"prices",
				{
					"item": item,
					"segment_no": seg.segment_no,
					"price": seg.price,
					"effective_from": seg.start,
					"effective_to": seg.end,
					"fuel_price_change": seg.source,
				},
			)


def segments_by_item(doc) -> dict[str, list]:
	out: dict[str, list] = defaultdict(list)
	for p in sorted(doc.prices, key=lambda p: (p.item, p.segment_no)):
		out[p.item].append(p)
	return out


def add_readings(doc, template, nozzles) -> None:
	"""One row per nozzle per price segment. Only the first row's openings are set here;
	later rows inherit the previous row's closing during validate (chain_openings)."""
	doc.set("meter_readings", [])
	assigned = {r.nozzle: (r.cashier, r.attendant) for r in template.nozzle_assignments}
	segs = segments_by_item(doc)
	for n in nozzles:
		cashier, attendant = assigned.get(n.name, (None, None))
		last = nozzle_last_readings(n.name)
		for i, seg in enumerate(segs[n.item]):
			row = {
				"nozzle": n.name,
				"tank": n.tank,
				"item": n.item,
				"cashier": cashier,
				"attendant": attendant,
				"segment_no": seg.segment_no,
				"price": seg.price,
				"source": "Manual",
			}
			if i == 0:
				for m in ("ecash", "evol", "mvol"):
					if doc.get(f"record_{m}"):
						row[f"opening_{m}"] = last[m]
			doc.append("meter_readings", row)


def add_tanks(doc) -> None:
	doc.set("tank_dips", [])
	previous = previous_dips(doc.previous_shift)
	for t in frappe.get_all(
		"Fuel Tank", filters={"station": doc.station, "status": "Active"}, fields=["name", "item"], order_by="tank_code"
	):
		opening = previous.get(t.name)
		if opening is None:
			opening = tank_book_stock(t.name, doc.shift_start)
		doc.append("tank_dips", {"tank": t.name, "item": t.item, "opening_l": flt(opening), "source": "Manual"})


def previous_dips(previous_shift: str | None) -> dict[str, float]:
	if not previous_shift:
		return {}
	rows = frappe.get_all(
		"Shift Tank Dip",
		filters={"parent": previous_shift, "parenttype": "Forecourt Shift", "dip_l": ("is", "set")},
		fields=["tank", "dip_l"],
	)
	return {r.tank: flt(r.dip_l) for r in rows}
```

### 4.2 `forecourt/forecourt_shift/shift/sources.py`

**Tasks:** FMS-F05, FMS-F06, FMS-F09, FMS-E07 · 143 lines

`TIMESTAMP(date, time)` is built with pypika's `CustomFunction`; `frappe.qb.functions` has no such helper. The Stock Ledger Entry query uses `posting_datetime`, which v15+ stores.

```python
# forecourt/forecourt_shift/shift/sources.py
"""Data the shift pulls from other documents inside its window (enter once).

GRN receipts (FMS-F05), Fuel Own Use (FMS-F06), POS sales (FMS-F09), transfers
(FMS-E07). Every query uses the Stock Ledger or submitted documents only, so
drafts never leak into a shift; drafts are reported separately by the gates.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Sum
from frappe.utils import flt
from pypika import CustomFunction

# TIMESTAMP(date, time): Stock Entry and POS Invoice keep date and time in two columns.
Timestamp = CustomFunction("TIMESTAMP", ["date", "time"])


def _tank_warehouses(doc) -> dict[str, str]:
	return {r.tank: frappe.get_cached_value("Fuel Tank", r.tank, "warehouse") for r in doc.tank_dips}


def stock_moves_by_tank(doc) -> dict[str, dict[str, float]]:
	"""Litres in and out of each tank warehouse during the window, by kind.

	receipts  = Purchase Receipts (GRNs) + delivery shortage Stock Entries (negative)
	transfers = Tank Transfer Stock Entries (in minus out)
	own_use   = Fuel Own Use Stock Entries (positive number of litres used)
	Sales are not read here; they come from the meters.
	"""
	wh_to_tank = {wh: tank for tank, wh in _tank_warehouses(doc).items()}
	if not wh_to_tank:
		return {}
	sle = DocType("Stock Ledger Entry")
	se = DocType("Stock Entry")
	rows = (
		frappe.qb.from_(sle)
		.left_join(se)
		.on((sle.voucher_type == "Stock Entry") & (se.name == sle.voucher_no))
		.select(
			sle.warehouse,
			sle.voucher_type,
			se.stock_entry_type,
			se.fms_purchase_receipt,
			Sum(sle.actual_qty).as_("qty"),
		)
		.where(
			(sle.is_cancelled == 0)
			& (sle.warehouse.isin(list(wh_to_tank)))
			& (sle.posting_datetime >= doc.shift_start)
			& (sle.posting_datetime < doc.shift_end)
			& (sle.voucher_type.isin(["Purchase Receipt", "Stock Entry"]))
		)
		.groupby(sle.warehouse, sle.voucher_type, se.stock_entry_type, se.fms_purchase_receipt)
		.run(as_dict=True)
	)
	out: dict[str, dict[str, float]] = defaultdict(lambda: {"receipts": 0.0, "transfers": 0.0, "own_use": 0.0})
	for r in rows:
		tank = wh_to_tank[r.warehouse]
		qty = flt(r.qty)
		if r.voucher_type == "Purchase Receipt" or r.fms_purchase_receipt:
			out[tank]["receipts"] += qty
		elif r.stock_entry_type == "Fuel Own Use":
			out[tank]["own_use"] += -qty
		elif r.stock_entry_type == "Material Transfer":
			out[tank]["transfers"] += qty
	return out


def own_use_by_nozzle(doc) -> dict[str, list[frappe._dict]]:
	"""Submitted Fuel Own Use entries in the window, per nozzle, with time and attendant."""
	se = DocType("Stock Entry")
	sed = DocType("Stock Entry Detail")
	rows = (
		frappe.qb.from_(se)
		.join(sed)
		.on(sed.parent == se.name)
		.select(se.name, se.fms_nozzle, se.fms_attendant, se.posting_date, se.posting_time, Sum(sed.transfer_qty).as_("qty"))
		.where(
			(se.docstatus == 1)
			& (se.stock_entry_type == "Fuel Own Use")
			& (se.station == doc.station)
			& (Timestamp(se.posting_date, se.posting_time) >= doc.shift_start)
			& (Timestamp(se.posting_date, se.posting_time) < doc.shift_end)
		)
		.groupby(se.name)
		.run(as_dict=True)
	)
	out: dict[str, list] = defaultdict(list)
	for r in rows:
		out[r.fms_nozzle].append(r)
	return out


def draft_documents_in_window(doc) -> dict[str, list[str]]:
	"""Drafts that would be missed by the close: GRNs into the tanks and Fuel Own Use.

	`station` is the Station accounting dimension field ERPNext adds to these DocTypes.
	"""
	warehouses = list(_tank_warehouses(doc).values())
	grns = frappe.get_all(
		"Purchase Receipt",
		filters={
			"docstatus": 0,
			"station": doc.station,
			"posting_date": ("between", [doc.shift_start.date(), doc.shift_end.date()]),
		},
		pluck="name",
	)
	own_use = frappe.get_all(
		"Stock Entry",
		filters={
			"docstatus": 0,
			"stock_entry_type": "Fuel Own Use",
			"station": doc.station,
			"posting_date": ("between", [doc.shift_start.date(), doc.shift_end.date()]),
		},
		pluck="name",
	)
	return {"grn": grns if warehouses else [], "own_use": own_use}


def pos_sales(doc) -> list[frappe._dict]:
	"""Submitted POS Invoice lines by FMS cashier in the window (shown, not posted again)."""
	pi = DocType("POS Invoice")
	pii = DocType("POS Invoice Item")
	return (
		frappe.qb.from_(pi)
		.join(pii)
		.on(pii.parent == pi.name)
		.select(pi.name.as_("pos_invoice"), pi.fms_cashier.as_("cashier"), pii.item_code.as_("item"), pii.qty, pii.rate, pii.amount, pii.warehouse)
		.where(
			(pi.docstatus == 1)
			& (pi.station == doc.station)
			& (pi.fms_cashier.isnotnull())
			& (Timestamp(pi.posting_date, pi.posting_time) >= doc.shift_start)
			& (Timestamp(pi.posting_date, pi.posting_time) < doc.shift_end)
		)
		.run(as_dict=True)
	)
```

### 4.3 `forecourt/forecourt_shift/shift/compute.py`

**Tasks:** FMS-F03 … FMS-F11 · 316 lines

A non-fuel item sold on credit adds to the cashier's item amount, because it appears nowhere else; fuel on credit is already inside the metered litres.

```python
# forecourt/forecourt_shift/shift/compute.py
"""Recalculate a draft shift from its inputs (FMS-F03 … FMS-F11).

Called from validate() on every save and from the `preview` whitelisted method the
form calls while the manager types. It only *derives* values; gates decide whether
the shift may close. All arithmetic is delegated to forecourt.calc.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from erpnext.setup.utils import get_exchange_rate
from frappe.utils import flt, get_datetime

from forecourt.calc.calibration import product_volume
from forecourt.calc.cashier import CashCount, CashierInput, balance
from forecourt.calc.errors import CalcError
from forecourt.calc.meters import MeterPair, SegmentInput, compute_segment
from forecourt.calc.wetstock import TankMovement, Tolerance, reconcile
from forecourt.errors import from_calc_error
from forecourt.utils.settings import get_settings
from forecourt.utils.stock import calibration_rows, nozzle_modulus

from .sources import own_use_by_nozzle, stock_moves_by_tank

METERS = ("ecash", "evol", "mvol")
RESOLUTION_SIGN = {"Charge to cashier": 1, "Write off": 1, "Record excess": -1}


def recorded_meters(doc) -> list[str]:
	return [m for m in METERS if doc.get(f"record_{m}")]


def has_closing(row, meters) -> bool:
	return all(row.get(f"closing_{m}") not in (None, "") for m in meters)


def recompute(doc, strict: bool = False) -> None:
	"""strict=True (before_submit) raises calculation errors; otherwise rows that cannot be
	computed yet are left blank so a half-filled draft can still be saved."""
	chain_openings(doc)
	apply_own_use(doc)
	compute_readings(doc, strict)
	compute_tanks(doc, strict)
	compute_credit_sales(doc)
	compute_resolutions(doc)
	compute_cashiers(doc)
	compute_totals(doc)
	doc.status = derive_status(doc)


def reading_groups(doc) -> dict[str, list]:
	"""Rows per nozzle in time order: price segment first, then row order (handovers)."""
	groups: dict[str, list] = defaultdict(list)
	for row in doc.meter_readings:
		groups[row.nozzle].append(row)
	for rows in groups.values():
		rows.sort(key=lambda r: (r.segment_no or 1, r.idx))
	return groups


def chain_openings(doc) -> None:
	"""Each row after the first for a nozzle opens at the previous row's closing.

	The manager types a change-time or handover reading once (as the closing of the
	earlier row); it becomes the opening of the next row automatically.
	"""
	meters = recorded_meters(doc)
	for rows in reading_groups(doc).values():
		for prev, cur in zip(rows, rows[1:]):
			for m in meters:
				cur.set(f"opening_{m}", prev.get(f"closing_{m}"))


def apply_own_use(doc) -> None:
	"""Put each submitted Fuel Own Use entry on the reading row of its nozzle, segment and
	attendant (falling back to the nozzle's last row)."""
	by_nozzle = own_use_by_nozzle(doc)
	seg_window = {(p.item, p.segment_no): (get_datetime(p.effective_from), get_datetime(p.effective_to)) for p in doc.prices}
	groups = reading_groups(doc)
	for row in doc.meter_readings:
		row.own_use_l = 0
	for nozzle, entries in by_nozzle.items():
		rows = groups.get(nozzle) or []
		if not rows:
			continue
		for e in entries:
			at = get_datetime(f"{e.posting_date} {e.posting_time}")
			candidates = [r for r in rows if in_segment(seg_window.get((r.item, r.segment_no)), at)] or rows
			target = next((r for r in candidates if r.cashier == e.fms_attendant), candidates[-1])
			target.own_use_l = flt(target.own_use_l) + flt(e.qty)


def in_segment(window, at) -> bool:
	return bool(window) and window[0] <= at < window[1]


def compute_readings(doc, strict: bool) -> None:
	meters = recorded_meters(doc)
	for row in doc.meter_readings:
		s = get_settings(doc.station, dispenser=frappe.get_cached_value("Nozzle", row.nozzle, "dispenser"))
		if not has_closing(row, meters):
			clear_row(row)
			continue
		modulus = nozzle_modulus(row.nozzle)
		seg = SegmentInput(
			price=flt(row.price),
			meters={
				m: MeterPair(
					opening=flt(row.get(f"opening_{m}")),
					closing=flt(row.get(f"closing_{m}")),
					rollover=bool(row.get(f"rollover_{m}")),
					modulus=modulus[m] or None,
				)
				for m in meters
			},
			basis=s.sales_basis,
			test_l=flt(row.test_volume_l),
			own_use_l=flt(row.own_use_l),
			drift_tolerance_l=s.drift_tolerance_l,
			drift_tolerance_pct=s.drift_tolerance_pct,
		)
		try:
			r = compute_segment(seg, label=f"Row {row.idx} ({row.nozzle})")
		except CalcError as e:
			if strict:
				from_calc_error(e)
			clear_row(row)
			continue
		row.basis_meter = r.basis_meter
		row.basis_volume_l = r.basis_volume_l
		row.net_volume_l = r.net_volume_l
		row.amount = r.amount
		row.drift_evol_mvol_l = r.drift.get("evol_mvol")
		row.drift_ecash_evol_l = r.drift.get("ecash_evol")
		row.drift_ecash_mvol_l = r.drift.get("ecash_mvol")
		row.drift_breach = int(bool(r.drift_breaches))


def clear_row(row) -> None:
	for f in ("basis_meter", "basis_volume_l", "net_volume_l", "amount"):
		row.set(f, None)
	row.drift_breach = 0


def compute_tanks(doc, strict: bool) -> None:
	moves = stock_moves_by_tank(doc)
	sales: dict[str, float] = defaultdict(float)
	for row in doc.meter_readings:
		sales[row.tank] += flt(row.net_volume_l)
	for t in doc.tank_dips:
		s = get_settings(doc.station, tank=t.tank)
		mv = moves.get(t.tank, {})
		t.receipts_l = flt(mv.get("receipts"))
		t.transfers_l = flt(mv.get("transfers"))
		t.own_use_l = flt(mv.get("own_use"))
		t.sales_l = sales[t.tank]
		dip = dip_litres(doc, t, s.dip_entry_mode, strict)
		r = reconcile(
			TankMovement(
				tank=t.tank,
				opening_l=flt(t.opening_l),
				receipts_l=t.receipts_l,
				sales_l=t.sales_l,
				own_use_l=t.own_use_l,
				transfers_l=t.transfers_l,
				dip_l=dip,
			),
			Tolerance(s.tank_tolerance_pct, s.tank_tolerance_l, s.approval_multiplier),
		)
		t.expected_l = r.expected_l
		t.variance_l = r.variance_l
		t.variance_pct = r.variance_pct
		t.within_tolerance = int(r.within_tolerance)
		t.needs_approval = int(r.needs_approval)


def dip_litres(doc, t, mode: str, strict: bool) -> float | None:
	"""Chart mode converts mm; litres mode trusts the entered litres."""
	if mode == "Litres entered directly":
		return None if t.dip_l in (None, "") else flt(t.dip_l)
	if t.dip_mm in (None, ""):
		t.dip_l = t.water_l = None
		return None
	rows, water_rows = calibration_rows(t.tank, doc.shift_end)
	try:
		t.dip_l, t.water_l = product_volume(flt(t.dip_mm), flt(t.water_mm), rows, water_rows)
	except CalcError as e:
		if strict:
			from_calc_error(e)
		return None
	return t.dip_l


def compute_credit_sales(doc) -> None:
	"""Price each slip from the segment in force when it was sold, and flag credit-limit breaches.

	The limit check adds this shift's slips for the customer to their current outstanding,
	the same way ERPNext checks a Sales Invoice, so the problem shows before close.
	"""
	from erpnext.selling.doctype.customer.customer import get_credit_limit, get_customer_outstanding

	from forecourt.calc.segments import Segment, price_at

	segs: dict[str, list[Segment]] = defaultdict(list)
	for p in sorted(doc.prices, key=lambda p: (p.item, p.segment_no)):
		segs[p.item].append(Segment(p.segment_no, flt(p.price), get_datetime(p.effective_from), get_datetime(p.effective_to)))
	shift_total: dict[str, float] = defaultdict(float)
	for cs in doc.credit_sales:
		if cs.item in segs:  # fuel: price from the segment
			at = get_datetime(cs.sold_at) if cs.sold_at else get_datetime(doc.shift_end)
			cs.rate = price_at(min(max(at, get_datetime(doc.shift_start)), get_datetime(doc.shift_end)), segs[cs.item]).price
		cs.amount = flt(cs.qty) * flt(cs.rate)
		shift_total[cs.customer] += cs.amount
	for cs in doc.credit_sales:
		limit = flt(get_credit_limit(cs.customer, doc.company))
		outstanding = flt(get_customer_outstanding(cs.customer, doc.company))
		cs.over_limit = int(bool(limit) and outstanding + shift_total[cs.customer] > limit)


def compute_resolutions(doc) -> None:
	"""Write-offs above the small-difference limit, and reasons flagged 'requires approval',
	need an approver who is not the person closing the shift."""
	s = get_settings(doc.station)
	approval_reasons = set(frappe.get_all("Variance Reason", {"requires_approval": 1}, pluck="name"))
	expected = {c.cashier: flt(c.expected) for c in doc.cashiers}
	for r in doc.resolutions:
		limit = max(flt(s.small_difference_amount), expected.get(r.cashier, 0) * flt(s.small_difference_pct) / 100)
		r.needs_approval = int(
			r.reason in approval_reasons or (r.action == "Write off" and flt(r.amount) > limit)
		)


def compute_cashiers(doc) -> None:
	fuel = defaultdict(float)
	for r in doc.meter_readings:
		fuel[r.cashier] += flt(r.amount)
	items = defaultdict(float)
	for r in doc.item_sales:
		if not r.pos_invoice:  # POS invoices are paid and reconciled by POS closing
			items[r.cashier] += flt(r.amount)
	for r in doc.credit_sales:
		# Fuel on credit is already inside the metered litres; a non-fuel item on credit
		# is a sale that appears nowhere else, so it adds to what the cashier must explain.
		if not frappe.get_cached_value("Item", r.item, "fms_is_fuel"):
			items[r.cashier] += flt(r.amount)
	credit = defaultdict(float)
	for r in doc.credit_sales:
		credit[r.cashier] += flt(r.amount)
	coll: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
	for c in doc.collections:
		coll[c.cashier][c.collection_type] += flt(c.amount)
	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	counts: dict[str, list[CashCount]] = defaultdict(list)
	for c in doc.cash_counts:
		if c.currency == company_currency:
			c.exchange_rate = 1
		elif not flt(c.exchange_rate):
			c.exchange_rate = get_exchange_rate(c.currency, company_currency, doc.shift_date)
		c.base_amount = flt(c.amount) * flt(c.exchange_rate)
		counts[c.cashier].append(CashCount(c.currency, flt(c.amount), flt(c.exchange_rate) or 1.0))
	resolved = defaultdict(float)
	for r in doc.resolutions:
		if r.resolution_for == "Cashier":
			resolved[r.cashier] += RESOLUTION_SIGN.get(r.action, 0) * flt(r.amount)

	for row in doc.cashiers:
		k = row.cashier
		res = balance(
			CashierInput(
				fuel_amount=fuel[k],
				item_amount=items[k],
				debt_receipts=coll[k]["Debt Receipt"],
				float_amount=flt(row.float_amount),
				cash_counts=tuple(counts[k]),
				mobile=coll[k]["Mobile Money"],
				card=coll[k]["Card"],
				credit=credit[k],
				voucher=coll[k]["Voucher"],
				expenses=coll[k]["Expense"],
				drops=coll[k]["Drop"],
				resolutions=resolved[k],
			)
		)
		row.fuel_amount, row.item_amount = fuel[k], items[k]
		row.debt_receipts = coll[k]["Debt Receipt"]
		row.expected, row.cash_counted, row.accounted = res.expected, res.cash_counted, res.accounted
		row.mobile, row.card, row.credit = coll[k]["Mobile Money"], coll[k]["Card"], credit[k]
		row.voucher, row.expenses, row.drops = coll[k]["Voucher"], coll[k]["Expense"], coll[k]["Drop"]
		row.difference = res.difference
		row.resolved = int(res.resolved)


def compute_totals(doc) -> None:
	doc.total_fuel_volume = sum(flt(r.net_volume_l) for r in doc.meter_readings)
	doc.total_fuel_amount = sum(flt(r.amount) for r in doc.meter_readings)
	doc.total_item_amount = sum(flt(r.item_amount) for r in doc.cashiers)
	doc.total_credit = sum(flt(r.credit) for r in doc.cashiers)
	doc.total_mobile = sum(flt(r.mobile) for r in doc.cashiers)
	doc.total_card = sum(flt(r.card) for r in doc.cashiers)
	doc.total_cash = sum(flt(r.cash_counted) for r in doc.cashiers)
	doc.total_expenses = sum(flt(r.expenses) for r in doc.cashiers)
	doc.total_difference = sum(flt(r.difference) for r in doc.cashiers)
	doc.total_tank_variance_l = sum(flt(t.variance_l) for t in doc.tank_dips)


def derive_status(doc) -> str:
	if doc.status in ("Closing", "Pending Approval"):
		return doc.status
	meters = recorded_meters(doc)
	if not any(has_closing(r, meters) for r in doc.meter_readings):
		return "Open"
	from .gates import collect_problems

	return "Reconciled" if not collect_problems(doc) else "Counting"
```

### 4.4 `forecourt/forecourt_shift/shift/gates.py`

**Tasks:** FMS-F12 · 142 lines

```python
# forecourt/forecourt_shift/shift/gates.py
"""Close gates (FMS-F12, design guide 6.6).

`collect_problems` is side-effect free so it can also drive the status shown while
the manager types. `run_gates` raises once with every problem listed.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.errors import GateCollector, Problem
from forecourt.utils.settings import get_settings
from forecourt.utils.stock import nozzle_last_readings

from .sources import draft_documents_in_window


def run_gates(doc) -> None:
	problems = collect_problems(doc)
	if problems:
		g = GateCollector()
		g.problems = problems
		g.raise_all()


def collect_problems(doc) -> list[Problem]:
	g = GateCollector()
	s = get_settings(doc.station)
	meters = [m for m in ("ecash", "evol", "mvol") if doc.get(f"record_{m}")]

	# Meters ------------------------------------------------------------------
	first_rows: dict[str, object] = {}
	for row in sorted(doc.meter_readings, key=lambda r: (r.nozzle, r.segment_no or 1, r.idx)):
		first_rows.setdefault(row.nozzle, row)
		missing = [m for m in meters if row.get(f"closing_{m}") in (None, "")]
		if missing:
			code = "FMS-S112" if (row.segment_no or 1) < max_segment(doc, row.item) else "FMS-S101"
			g.add(code, _("Row {0} ({1}) has no closing {2} reading").format(row.idx, row.nozzle, ", ".join(missing)))
		elif row.net_volume_l is None:
			g.add("FMS-S101", _("Row {0} ({1}) could not be calculated; check the readings").format(row.idx, row.nozzle))
		g.check(bool(row.cashier), "FMS-S104", _("Row {0} ({1}) has no cashier").format(row.idx, row.nozzle))
		if row.drift_breach and s.drift_requires_reason:
			g.check(bool(row.drift_reason), "FMS-W103", _("Row {0} ({1}) drift is beyond tolerance").format(row.idx, row.nozzle))

	for nozzle, row in first_rows.items():
		last = nozzle_last_readings(nozzle)
		for m in meters:
			if flt(row.get(f"opening_{m}")) != flt(last[m]):
				g.add("FMS-S102", _("{0} opening {1} is {2}, last closing was {3}").format(nozzle, m, row.get(f"opening_{m}"), last[m]))

	# Tanks -------------------------------------------------------------------
	template_needs_dips = frappe.get_cached_value("Forecourt Shift Template", doc.shift_template, "dips_required")
	reasons_needing_approval = set(frappe.get_all("Variance Reason", {"requires_approval": 1}, pluck="name"))
	for t in doc.tank_dips:
		if template_needs_dips:
			g.check(t.dip_l not in (None, ""), "FMS-S103", _("Tank {0} has no closing dip").format(t.tank))
		if t.variance_l is not None and not t.within_tolerance:
			g.check(bool(t.reason), "FMS-S106", _("Tank {0} variance {1} L needs a reason").format(t.tank, t.variance_l))
			if (t.needs_approval or t.reason in reasons_needing_approval) and not t.approved_by:
				g.add("FMS-S106", _("Tank {0} variance {1} L needs area manager approval").format(t.tank, t.variance_l))
		if t.variance_l is not None and t.variance_l > 0 and not t.within_tolerance and not t.receipts_l:
			g.add("FMS-T203", _("Tank {0} rose by {1} L with no GRN in the shift window").format(t.tank, t.variance_l))

	drafts = draft_documents_in_window(doc)
	for name in drafts["grn"]:
		g.add("FMS-T204", _("Draft GRN {0} is inside the shift window").format(name))
	for name in drafts["own_use"]:
		g.add("FMS-S113", _("Draft Fuel Own Use {0} is inside the shift window").format(name))

	# Cashiers ----------------------------------------------------------------
	for c in doc.cashiers:
		if not c.resolved:
			g.add("FMS-S105", _("{0} has an unresolved difference of {1}").format(c.cashier, c.difference))
	for r in doc.resolutions:
		if r.needs_approval and not r.approved_by:
			g.add("FMS-S105", _("Resolution for {0} needs approval").format(r.cashier or r.tank))

	# Credit ------------------------------------------------------------------
	metered = defaultdict(float)
	for row in doc.meter_readings:
		metered[row.item] += flt(row.net_volume_l)
	credited = defaultdict(float)
	for cs in doc.credit_sales:
		credited[cs.item] += flt(cs.qty)
		if cs.get("over_limit") and not cs.over_limit_approved_by:
			g.add("FMS-S107", _("Credit slip {0} for {1} is over the credit limit").format(cs.slip_no, cs.customer))
	for item, qty in credited.items():
		if item in metered and qty > metered[item] + 0.001:
			g.add("FMS-S108", _("Credit {0} L of {1} exceeds metered {2} L").format(qty, item, metered[item]))

	# Collections -------------------------------------------------------------
	seen = set()
	for c in doc.collections:
		g.check(bool(c.cashier), "FMS-S111", _("Row {0}: {1} {2} has no cashier").format(c.idx, c.collection_type, c.reference or ""))
		if c.collection_type in ("Mobile Money", "Card"):
			key = (c.provider, (c.reference or "").strip().upper())
			g.check(bool(key[1]), "FMS-S114", _("Row {0}: {1} payment needs a reference").format(c.idx, c.collection_type))
			if key[1] and key in seen:
				g.add("FMS-S114", _("Duplicate reference {0}").format(c.reference))
			seen.add(key)
		if c.collection_type == "Expense":
			check_expense(g, c)
	for ref in already_used_references(doc):
		g.add("FMS-S114", _("Reference {0} was already used in shift {1}").format(ref.reference, ref.parent))

	unmatched = frappe.db.count(
		"Payment Feed Entry",
		{"station": doc.station, "status": "Unmatched", "transaction_time": ("between", [doc.shift_start, doc.shift_end])},
	)
	g.check(not unmatched, "FMS-S111", _("{0} payment(s) received on this station's tills are not assigned").format(unmatched))
	return g.problems


def max_segment(doc, item: str) -> int:
	return max((p.segment_no for p in doc.prices if p.item == item), default=1)


def check_expense(g: GateCollector, c) -> None:
	if not c.expense_type:
		g.add("FMS-S109", _("Row {0}: expense has no type").format(c.idx))
		return
	limit, receipt = frappe.get_cached_value("Expense Type", c.expense_type, ["max_per_line", "receipt_required"])
	if flt(limit) and flt(c.amount) > flt(limit):
		g.add("FMS-S109", _("Row {0}: {1} is above the {2} limit").format(c.idx, c.amount, c.expense_type))
	if receipt and not c.attachment:
		g.add("FMS-S109", _("Row {0}: attach the receipt").format(c.idx))


def already_used_references(doc) -> list:
	"""Mobile and card references must be unique across the site, not only in this shift."""
	refs = [c.reference for c in doc.collections if c.collection_type in ("Mobile Money", "Card") and c.reference]
	if not refs:
		return []
	return frappe.get_all(
		"Shift Collection",
		filters={"reference": ("in", refs), "parent": ("!=", doc.name), "docstatus": 1},
		fields=["reference", "parent"],
	)
```

---

## 5. Shift controller and form

The controller wires the modules together and exposes the form's server methods: `preview` (live totals and the problem list), `refetch_openings`, `approve` and `close_shift` (background close above `background_close_threshold` collection rows). Posting sets `frappe.flags.fms_posting` so the cancel guards know the shift itself is acting. Hooks never call `frappe.db.commit()`; only the background job does, because a job is not a document hook.

### 5.1 `forecourt/forecourt_shift/doctype/forecourt_shift/forecourt_shift.py`

**Tasks:** FMS-F01, FMS-F03, FMS-F16, FMS-I03 · 177 lines

```python
# forecourt/forecourt_shift/doctype/forecourt_shift/forecourt_shift.py
# Copyright (c) 2026, the FMS authors. MIT licence.
"""Forecourt Shift controller (FMS-F01 … FMS-F18).

The controller is thin on purpose: pre-fill, recompute, gates and posting each live
in their own module so they can be read, tested and changed separately.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from forecourt.errors import fms_throw
from forecourt.forecourt_shift.shift.compute import recompute
from forecourt.forecourt_shift.shift.gates import run_gates
from forecourt.forecourt_shift.shift.prefill import prefill
from forecourt.posting import post_shift
from forecourt.utils.settings import get_settings
from forecourt.utils.shifts import is_latest_closed_shift


class ForecourtShift(Document):
	def before_insert(self) -> None:
		prefill(self)

	def validate(self) -> None:
		recompute(self)

	def before_submit(self) -> None:
		recompute(self, strict=True)
		run_gates(self)

	def on_submit(self) -> None:
		frappe.flags.fms_posting = True
		try:
			post_shift(self)
		finally:
			frappe.flags.fms_posting = False
		self.db_set("status", "Closed")

	def before_cancel(self) -> None:
		# Normal fixes go through Shift Correction (design guide 6.8). Whole-shift
		# cancellation is the exception: latest shift, System Manager, director approval.
		if not frappe.flags.fms_correction:
			fms_throw("FMS-C502", _("Closed shifts are corrected with a Shift Correction, not cancelled."))
		if not is_latest_closed_shift(self.name):
			fms_throw("FMS-C502", _("Only the latest closed shift at a station can be cancelled."))

	def on_cancel(self) -> None:
		from forecourt.posting import cancel_shift_postings

		frappe.flags.fms_posting = True
		try:
			cancel_shift_postings(self)
		finally:
			frappe.flags.fms_posting = False

	def on_update_after_submit(self) -> None:
		# Only Shift Correction may change a closed shift, and only its status.
		if not frappe.flags.fms_correction:
			fms_throw("FMS-C502", _("Closed shifts cannot be edited."))


def on_doctype_update() -> None:
	"""Composite indexes (called by `bench migrate`)."""
	frappe.db.add_index("Forecourt Shift", ["station", "shift_start"])
	frappe.db.add_index("Forecourt Shift", ["company", "shift_date"])
	frappe.db.add_index("Shift Collection", ["provider", "reference"])


# ---------------------------------------------------------------- client API


@frappe.whitelist()
def preview(doc: str | dict) -> dict:
	"""Recompute an unsaved form and return it, for live totals while typing (FMS-F03).

	Nothing is written. The client sends the whole doc, debounced.
	"""
	from forecourt.forecourt_shift.shift.gates import collect_problems

	shift = frappe.get_doc(frappe.parse_json(doc) if isinstance(doc, str) else doc)
	shift.check_permission("write")
	recompute(shift)
	problems = collect_problems(shift) if shift.status != "Open" else []
	return {"doc": shift.as_dict(), "problems": [{"code": p.code, "message": p.message} for p in problems]}


@frappe.whitelist()
def refetch_openings(name: str) -> None:
	"""Reset first-row openings to the nozzles' current last readings (fix for FMS-S102)."""
	from forecourt.utils.stock import nozzle_last_readings

	shift = frappe.get_doc("Forecourt Shift", name)
	shift.check_permission("write")
	if shift.docstatus != 0:
		frappe.throw(_("Only open shifts can be changed"))
	done = set()
	for row in sorted(shift.meter_readings, key=lambda r: (r.nozzle, r.segment_no or 1, r.idx)):
		if row.nozzle in done:
			continue
		done.add(row.nozzle)
		last = nozzle_last_readings(row.nozzle)
		for m in ("ecash", "evol", "mvol"):
			if shift.get(f"record_{m}"):
				row.set(f"opening_{m}", last[m])
	shift.save()


@frappe.whitelist()
def approve(name: str, row_doctype: str, row_name: str) -> None:
	"""Area manager approves one tank variance or one resolution line.

	The approver may not be the user who last edited the shift (segregation of duties).
	"""
	if "Area Manager" not in frappe.get_roles():
		frappe.throw(_("Only an Area Manager can approve"), frappe.PermissionError)
	shift = frappe.get_doc("Forecourt Shift", name)
	if shift.modified_by == frappe.session.user:
		frappe.throw(_("You cannot approve a shift you edited"))
	table = {"Shift Tank Dip": "tank_dips", "Shift Resolution": "resolutions"}.get(row_doctype)
	if not table:
		frappe.throw(_("Nothing to approve on {0}").format(row_doctype))
	row = next((r for r in shift.get(table) if r.name == row_name), None)
	if not row:
		frappe.throw(_("Row not found"))
	row.approved_by = frappe.session.user
	shift.flags.ignore_permissions = True
	shift.save()


@frappe.whitelist()
def close_shift(name: str) -> str:
	"""The Close button. Small shifts submit now; large ones submit in a background job (FMS-F16).

	Returns "closed" or "queued".
	"""
	shift = frappe.get_doc("Forecourt Shift", name)
	shift.check_permission("submit")
	threshold = get_settings(shift.station).background_close_threshold
	if len(shift.collections) <= threshold:
		shift.submit()
		return "closed"
	run_gates(shift)  # fail fast, before queuing
	shift.db_set("status", "Closing")
	frappe.enqueue(
		"forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift.run_close",
		queue="long",
		timeout=1800,
		job_id=f"fms-close::{name}",
		deduplicate=True,
		name=name,
		user=frappe.session.user,
	)
	return "queued"


def run_close(name: str, user: str) -> None:
	"""Background job body. One transaction: either everything posts or nothing does."""
	frappe.set_user(user)
	shift = frappe.get_doc("Forecourt Shift", name)
	try:
		shift.status = "Reconciled"
		shift.submit()
		frappe.db.commit()  # jobs commit explicitly; this is not a document hook
		frappe.publish_realtime("fms_shift_closed", {"name": name}, user=user)
	except Exception:
		frappe.db.rollback()
		frappe.db.set_value("Forecourt Shift", name, "status", "Reconciled")
		frappe.get_doc("Forecourt Shift", name).add_comment(
			"Comment", _("Background close failed at {0}. See Error Log.").format(now_datetime())
		)
		frappe.log_error(title=f"FMS close failed: {name}")
		frappe.db.commit()
		frappe.publish_realtime("fms_shift_close_failed", {"name": name}, user=user)
```

### 5.2 `forecourt/forecourt_shift/doctype/forecourt_shift/forecourt_shift.js`

**Tasks:** FMS-F03, FMS-F10, FMS-F11, FMS-F16, FMS-F17, FMS-I03, FMS-J01 · 297 lines

The form never calculates. It sends the unsaved document to `preview` (debounced 600 ms; stale answers are dropped by a sequence number) and copies only the calculated fields back, so typing is never interrupted and what the manager sees is what will be saved. Enter in a reading or dip column jumps to the same column on the next row. The headline lists the open problems with their codes. Buttons: Re-fetch openings and Import statement (Tools), Resolve differences (pre-filled lines), Approve (Area Manager), Close shift (only when Reconciled and saved).

```javascript
// forecourt/forecourt_shift/doctype/forecourt_shift/forecourt_shift.js
// Copyright (c) 2026, the FMS authors. MIT licence.
// Forecourt Shift form (FMS-F03 live totals, FMS-F10 entry speed, FMS-F11 resolve,
// FMS-F16 close, FMS-I03 approve, FMS-J01 import).
//
// The server is the only place that calculates. The form sends the unsaved doc to
// `preview` (debounced) and copies the calculated fields back, so what the manager
// sees while typing is exactly what will be saved.

const METHOD = "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift";
const PREVIEW_DELAY_MS = 600;

// Fields the server calculates, per table. Copied back without marking rows dirty.
const COMPUTED = {
	meter_readings: ["opening_ecash", "opening_evol", "opening_mvol", "basis_meter", "basis_volume_l",
		"own_use_l", "net_volume_l", "amount", "drift_evol_mvol_l", "drift_ecash_evol_l",
		"drift_ecash_mvol_l", "drift_breach"],
	tank_dips: ["receipts_l", "sales_l", "own_use_l", "transfers_l", "expected_l", "dip_l", "water_l",
		"variance_l", "variance_pct", "within_tolerance", "needs_approval"],
	credit_sales: ["rate", "amount", "over_limit"],
	cashiers: ["fuel_amount", "item_amount", "debt_receipts", "expected", "cash_counted", "mobile", "card",
		"credit", "voucher", "expenses", "drops", "accounted", "difference", "resolved"],
	cash_counts: ["exchange_rate", "base_amount"],
	resolutions: ["needs_approval"],
};
const HEADER = ["status", "total_fuel_volume", "total_fuel_amount", "total_item_amount", "total_credit",
	"total_mobile", "total_card", "total_cash", "total_expenses", "total_difference", "total_tank_variance_l"];

// Typing in these fields triggers a preview.
const INPUTS = {
	"Shift Meter Reading": ["closing_ecash", "closing_evol", "closing_mvol", "rollover_ecash", "rollover_evol",
		"rollover_mvol", "test_volume_l", "cashier"],
	"Shift Tank Dip": ["dip_mm", "water_mm", "dip_l"],
	"Shift Credit Sale": ["item", "qty", "sold_at", "customer", "cashier"],
	"Shift Item Sale": ["qty", "rate", "amount", "cashier"],
	"Shift Cashier": ["float_amount"],
	"Shift Cash Count": ["amount", "count", "denomination", "currency", "cashier"],
	"Shift Collection": ["amount", "collection_type", "cashier"],
	"Shift Resolution": ["amount", "action", "reason", "cashier"],
};

frappe.ui.form.on("Forecourt Shift", {
	setup(frm) {
		frm.set_query("shift_template", () => ({ filters: { station: frm.doc.station, active: 1 } }));
		frm.set_query("cashier", "cashiers", () => ({ filters: { fms_is_forecourt_cashier: 1, status: "Active" } }));
		frm.set_query("vehicle", "credit_sales", (doc, cdt, cdn) => ({
			filters: { customer: locals[cdt][cdn].customer, active: 1 },
		}));
		frm.set_query("expense_type", "collections", () => ({ filters: { disabled: 0 } }));
		frm.set_query("reason", "resolutions", () => ({ filters: { disabled: 0, applies_to_cashier: 1 } }));
		frm.set_query("reason", "tank_dips", () => ({ filters: { disabled: 0, applies_to_tank: 1 } }));
	},

	onload(frm) {
		frm.fms_preview = frappe.utils.debounce(() => run_preview(frm), PREVIEW_DELAY_MS);
		frappe.realtime.on("fms_shift_closed", (d) => {
			if (d.name === frm.doc.name) {
				frappe.show_alert({ message: __("Shift closed"), indicator: "green" });
				frm.reload_doc();
			}
		});
		frappe.realtime.on("fms_shift_close_failed", (d) => {
			if (d.name === frm.doc.name) {
				frappe.msgprint({ title: __("Close failed"), message: __("See the comment on the shift and the Error Log."), indicator: "red" });
				frm.reload_doc();
			}
		});
	},

	refresh(frm) {
		set_indicator(frm);
		show_problems(frm, frm.fms_problems || []);
		if (frm.doc.docstatus !== 0) return;
		add_buttons(frm);
		bind_enter_to_next_row(frm, "meter_readings", ["closing_ecash", "closing_evol", "closing_mvol"]);
		bind_enter_to_next_row(frm, "tank_dips", ["dip_mm", "dip_l"]);
	},
});

const TABLE_OF = {
	"Shift Meter Reading": "meter_readings", "Shift Tank Dip": "tank_dips", "Shift Credit Sale": "credit_sales",
	"Shift Item Sale": "item_sales", "Shift Cashier": "cashiers", "Shift Cash Count": "cash_counts",
	"Shift Collection": "collections", "Shift Resolution": "resolutions",
};

// One handler per child DocType and input field: schedule a preview.
for (const [cdt, fields] of Object.entries(INPUTS)) {
	const handlers = {};
	for (const f of fields) handlers[f] = (frm) => frm.fms_preview && frm.fms_preview();
	// Deleting a row also changes totals; the event is named after the parent's table field.
	handlers[`${TABLE_OF[cdt]}_remove`] = (frm) => frm.fms_preview && frm.fms_preview();
	frappe.ui.form.on(cdt, handlers);
}

// Denomination × count fills the amount, so counting notes is one column of typing.
frappe.ui.form.on("Shift Cash Count", {
	count: (frm, cdt, cdn) => fill_denomination(cdt, cdn),
	denomination: (frm, cdt, cdn) => fill_denomination(cdt, cdn),
});

function fill_denomination(cdt, cdn) {
	const r = locals[cdt][cdn];
	if (r.denomination && r.count) frappe.model.set_value(cdt, cdn, "amount", r.denomination * r.count);
}

// ------------------------------------------------------------------ preview

let preview_seq = 0;

async function run_preview(frm) {
	if (frm.doc.docstatus !== 0) return;
	const seq = ++preview_seq;
	const r = await frappe.xcall(`${METHOD}.preview`, { doc: frm.doc });
	if (seq !== preview_seq) return; // a newer preview is on its way; drop this one
	apply_preview(frm, r.doc);
	frm.fms_problems = r.problems;
	show_problems(frm, r.problems);
	set_indicator(frm);
}

function apply_preview(frm, server) {
	for (const f of HEADER) frm.doc[f] = server[f];
	for (const [table, fields] of Object.entries(COMPUTED)) {
		// Rows match by name (saved rows) or by idx (new rows not yet saved).
		const by_key = {};
		for (const row of server[table] || []) by_key[row.name] = by_key[`idx:${row.idx}`] = row;
		for (const row of frm.doc[table] || []) {
			const src = by_key[row.name] || by_key[`idx:${row.idx}`];
			if (!src) continue;
			for (const f of fields) row[f] = src[f];
		}
		frm.refresh_field(table);
	}
	for (const f of HEADER) frm.refresh_field(f);
}

function set_indicator(frm) {
	const colour = { Open: "orange", Counting: "orange", Reconciled: "green", "Pending Approval": "purple",
		Closing: "blue", Closed: "blue", Corrected: "grey" }[frm.doc.status] || "grey";
	frm.page.set_indicator(__(frm.doc.status || "Open"), colour);
}

function show_problems(frm, problems) {
	frm.dashboard.clear_headline();
	if (!problems.length) return;
	const items = problems.slice(0, 8).map((p) => `<li><b>${p.code}</b> ${frappe.utils.escape_html(p.message)}</li>`);
	const more = problems.length > 8 ? `<li>${__("and {0} more", [problems.length - 8])}</li>` : "";
	frm.dashboard.set_headline(`<div>${__("To close this shift:")}</div><ul class="mb-0">${items.join("")}${more}</ul>`, "orange");
}

// ------------------------------------------------------------------ fast entry

// Enter in a reading column moves to the same column on the next row, so a manager can
// type all closing readings top to bottom without the mouse.
function bind_enter_to_next_row(frm, table, fields) {
	const grid = frm.fields_dict[table].grid;
	if (grid.fms_bound) return;
	grid.fms_bound = true;
	grid.wrapper.on("keydown", "input", function (e) {
		if (e.key !== "Enter") return;
		const field = $(this).attr("data-fieldname");
		if (!fields.includes(field)) return;
		e.preventDefault();
		const row_name = $(this).closest(".grid-row").attr("data-name");
		const rows = grid.grid_rows;
		const i = rows.findIndex((r) => r.doc.name === row_name);
		const next = rows[i + 1];
		if (!next) return;
		next.activate();
		setTimeout(() => next.columns[field] && next.columns[field].field && next.columns[field].field.$input.focus().select(), 50);
	});
}

// ------------------------------------------------------------------ buttons

function add_buttons(frm) {
	if (frm.is_new()) return;

	frm.add_custom_button(__("Re-fetch openings"), () =>
		frappe.confirm(__("Reset the first opening of every nozzle to its last closing?"), () =>
			frappe.xcall(`${METHOD}.refetch_openings`, { name: frm.doc.name }).then(() => frm.reload_doc())
		), __("Tools"));

	frm.add_custom_button(__("Import statement"), () => import_statement(frm), __("Tools"));

	const unresolved = (frm.doc.cashiers || []).filter((c) => !c.resolved && c.difference);
	if (unresolved.length) {
		frm.add_custom_button(__("Resolve differences"), () => resolve_dialog(frm, unresolved));
	}

	const awaiting = [
		...(frm.doc.tank_dips || []).filter((t) => t.needs_approval && !t.approved_by).map((t) => ["Shift Tank Dip", t]),
		...(frm.doc.resolutions || []).filter((r) => r.needs_approval && !r.approved_by).map((r) => ["Shift Resolution", r]),
	];
	if (awaiting.length && frappe.user.has_role("Area Manager")) {
		frm.add_custom_button(__("Approve"), () => approve_dialog(frm, awaiting));
	}

	if (frm.doc.status === "Reconciled" && !frm.is_dirty()) {
		frm.add_custom_button(__("Close shift"), () => close_shift(frm)).addClass("btn-primary");
	}
}

function resolve_dialog(frm, cashiers) {
	// One line per unresolved cashier; amount pre-filled with what clears the difference.
	const d = new frappe.ui.Dialog({
		title: __("Resolve differences"),
		size: "large",
		fields: [{
			fieldname: "lines", fieldtype: "Table", cannot_add_rows: true, in_place_edit: true,
			data: cashiers.map((c) => ({
				cashier: c.cashier,
				difference: c.difference,
				action: c.difference < 0 ? "Charge to cashier" : "Record excess",
				amount: Math.abs(c.difference),
			})),
			fields: [
				{ fieldname: "cashier", label: __("Cashier"), fieldtype: "Link", options: "Employee", read_only: 1, in_list_view: 1 },
				{ fieldname: "difference", label: __("Difference"), fieldtype: "Currency", read_only: 1, in_list_view: 1 },
				{ fieldname: "action", label: __("Action"), fieldtype: "Select", in_list_view: 1,
					options: ["Charge to cashier", "Write off", "Record excess"] },
				{ fieldname: "amount", label: __("Amount"), fieldtype: "Currency", in_list_view: 1 },
				{ fieldname: "reason", label: __("Reason"), fieldtype: "Link", options: "Variance Reason", reqd: 1, in_list_view: 1,
					get_query: () => ({ filters: { applies_to_cashier: 1, disabled: 0 } }) },
				{ fieldname: "note", label: __("Note"), fieldtype: "Small Text" },
			],
		}],
		primary_action_label: __("Add lines"),
		primary_action(values) {
			for (const l of values.lines) {
				frm.add_child("resolutions", { resolution_for: "Cashier", cashier: l.cashier, action: l.action,
					amount: l.amount, reason: l.reason, note: l.note });
			}
			frm.refresh_field("resolutions");
			d.hide();
			frm.save();
		},
	});
	d.show();
}

function approve_dialog(frm, rows) {
	const d = new frappe.ui.Dialog({
		title: __("Approve"),
		fields: rows.map(([dt, r], i) => ({
			fieldname: `row_${i}`, fieldtype: "Check", default: 1,
			label: dt === "Shift Tank Dip"
				? __("Tank {0}: {1} L ({2}%), {3}", [r.tank, r.variance_l, r.variance_pct, r.reason || __("no reason")])
				: __("{0}: {1} {2}, {3}", [r.cashier, r.action, format_currency(r.amount), r.reason]),
		})),
		primary_action_label: __("Approve selected"),
		async primary_action(values) {
			for (const [i, [dt, r]] of rows.entries()) {
				if (values[`row_${i}`]) await frappe.xcall(`${METHOD}.approve`, { name: frm.doc.name, row_doctype: dt, row_name: r.name });
			}
			d.hide();
			frm.reload_doc();
		},
	});
	d.show();
}

function import_statement(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Import provider statement"),
		fields: [
			{ fieldname: "provider", fieldtype: "Link", options: "Payment Provider", reqd: 1, label: __("Provider"),
				get_query: () => ({ filters: { disabled: 0, import_format: ["!=", "None"] } }) },
			{ fieldname: "file", fieldtype: "Attach", reqd: 1, label: __("File (CSV or Excel)") },
		],
		primary_action_label: __("Import"),
		async primary_action(v) {
			if (frm.is_dirty()) await frm.save();
			const batch = await frappe.db.insert({ doctype: "Payment Import Batch", station: frm.doc.station,
				forecourt_shift: frm.doc.name, provider: v.provider, file: v.file });
			const r = await frappe.xcall("forecourt.forecourt_integrations.statement_import.run", { batch: batch.name });
			d.hide();
			frappe.msgprint(__("{0} read, {1} added, {2} duplicates skipped, {3} rejected (see {4})",
				[r.read, r.created, r.duplicate, r.rejected, batch.name]));
			frm.reload_doc();
		},
	});
	d.show();
}

async function close_shift(frm) {
	const ok = await new Promise((res) => frappe.confirm(
		__("Close the shift? This posts invoices, payments and stock and cannot be edited afterwards."), () => res(true), () => res(false)));
	if (!ok) return;
	frappe.dom.freeze(__("Closing shift…"));
	try {
		const result = await frappe.xcall(`${METHOD}.close_shift`, { name: frm.doc.name });
		if (result === "queued") frappe.show_alert({ message: __("Closing in the background; you will be notified"), indicator: "blue" });
		frm.reload_doc();
	} finally {
		frappe.dom.unfreeze();
	}
}
```

---

## 6. Posting (`forecourt/posting`)

Runs inside the shift's `on_submit`, in one transaction: if anything fails, nothing posts. The order follows design guide 8.2:

1. credit Sales Invoices, one per customer (Delivery Notes if the company invoices monthly);
2. the walk-in Sales Invoice: metered litres minus credit litres, per tank and price, plus non-POS items;
3. one Payment Entry per mobile money, card or voucher transaction, oldest first, then one cash Payment Entry per cashier for the balance, then debt receipts against the customer's oldest invoices;
4. one Journal Entry for expenses, drops and resolution lines, after which the till equals the count;
5. one Stock Reconciliation setting each dipped tank to its dip (the variance);
6. the four FMS ledgers by bulk insert;
7. each nozzle's last readings.

Every document is dated one second before the shift ends, so it sorts before the next shift's opening, and carries `station` (accounting dimension), `cost_center` and `fms_forecourt_shift`.

### 6.1 `forecourt/posting/__init__.py`

**Tasks:** FMS-F13, FMS-G05 · 54 lines

```python
# forecourt/posting/__init__.py
"""Posting: turn a closed shift into native ERPNext documents and FMS ledger rows.

Order matters (stock and receivables must exist before payments), and everything
runs inside the submit transaction, so a failure anywhere posts nothing.
"""

from __future__ import annotations

import frappe

from .context import GENERATED_DOCTYPES, PostingContext
from .journals import post_journal
from .ledgers import mark_ledgers_cancelled, write_ledgers
from .payments import post_payments
from .sales import post_credit_sales, post_walk_in_sales
from .stock import post_stock_reconciliation


def post_shift(shift) -> PostingContext:
	ctx = PostingContext.from_shift(shift)
	post_credit_sales(ctx)  # 1. credit invoices per customer
	post_walk_in_sales(ctx)  # 2. walk-in invoice
	post_payments(ctx)  # 2a/2b, 4, 5. payment entries, drops, debt receipts
	post_journal(ctx)  # 3. expenses and resolutions
	post_stock_reconciliation(ctx)  # 7. tank book stock = dips
	write_ledgers(ctx)  # 8-10. FMS ledgers
	update_nozzles(ctx)
	return ctx


def update_nozzles(ctx: PostingContext) -> None:
	"""The last row per nozzle (latest segment, last handover) holds the shift closing."""
	from forecourt.utils.stock import set_nozzle_last_readings

	last: dict[str, object] = {}
	for row in sorted(ctx.shift.meter_readings, key=lambda r: (r.nozzle, r.segment_no or 1, r.idx)):
		last[row.nozzle] = row
	for nozzle, row in last.items():
		set_nozzle_last_readings(
			nozzle, {m: row.get(f"closing_{m}") for m in ("ecash", "evol", "mvol") if ctx.shift.get(f"record_{m}")}, ctx.shift.name
		)


def cancel_shift_postings(shift) -> None:
	"""Exceptional whole-shift cancellation: cancel generated documents newest first."""
	docs = []
	for doctype in GENERATED_DOCTYPES:
		for d in frappe.get_all(doctype, {"fms_forecourt_shift": shift.name, "docstatus": 1}, ["name", "creation"]):
			docs.append((d.creation, doctype, d.name))
	for _creation, doctype, name in sorted(docs, reverse=True):
		doc = frappe.get_doc(doctype, name)
		doc.flags.ignore_permissions = True
		doc.cancel()
	mark_ledgers_cancelled(shift.name)
```

### 6.2 `forecourt/posting/context.py`

**Tasks:** FMS-F13 · 94 lines

```python
# forecourt/posting/context.py
"""Shared posting context and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import frappe
from frappe.utils import get_datetime

from forecourt.utils.settings import company_accounts, get_settings

GENERATED_DOCTYPES = (
	"Payment Entry",
	"Journal Entry",
	"Stock Reconciliation",
	"Sales Invoice",
	"Delivery Note",
)


@dataclass
class PostingContext:
	shift: object
	company: str
	station: str
	cost_center: str
	posting_date: object
	posting_time: object
	walk_in_customer: str
	till_account: str
	safe_account: str
	accounts: object
	settings: object
	created: list[tuple[str, str]] = field(default_factory=list)
	walk_in_invoice: str | None = None
	correction: str | None = None  # set when a Shift Correction posts
	cashier_walk_in_share: dict[str, float] = field(default_factory=dict)

	@classmethod
	def from_shift(cls, shift) -> PostingContext:
		st = frappe.get_cached_doc("Station", shift.station)
		currency = frappe.get_cached_value("Company", shift.company, "default_currency")
		till = next((t.account for t in st.till_accounts if t.currency == currency), None)
		if not till:
			frappe.throw(frappe._("Station {0} has no till account in {1}").format(st.name, currency))
		# Post one second before the window ends, so the shift's documents sort before the
		# next shift's opening at exactly shift_end. A night shift therefore posts on the
		# morning it ends; reports by shift date use the FMS ledgers' shift_date.
		at = get_datetime(shift.shift_end) - timedelta(seconds=1)
		return cls(
			shift=shift,
			company=shift.company,
			station=shift.station,
			cost_center=st.cost_center,
			posting_date=at.date(),
			posting_time=at.time(),
			walk_in_customer=st.walk_in_customer,
			till_account=till,
			safe_account=st.safe_account,
			accounts=company_accounts(shift.company),
			settings=get_settings(shift.station),
		)

	def stamp(self, doc) -> None:
		"""Fields every generated document carries."""
		if self.correction and doc.meta.has_field("remarks"):
			doc.remarks = frappe._("Shift Correction {0}").format(self.correction)
		doc.company = self.company
		doc.posting_date = self.posting_date
		if doc.meta.has_field("posting_time"):
			doc.posting_time = self.posting_time
			doc.set_posting_time = 1
		doc.station = self.station  # accounting dimension
		doc.fms_forecourt_shift = self.shift.name
		if doc.meta.has_field("cost_center"):
			doc.cost_center = self.cost_center
		doc.flags.ignore_permissions = True

	def submit(self, doc) -> None:
		doc.insert()
		doc.submit()
		self.created.append((doc.doctype, doc.name))


def mop_account(mode_of_payment: str, company: str) -> str:
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account"
	)
	if not account:
		from forecourt.errors import fms_throw

		fms_throw("FMS-P301", frappe._("Mode of Payment {0} has no account for {1}").format(mode_of_payment, company))
	return account
```

### 6.3 `forecourt/posting/sales.py`

**Tasks:** FMS-F13, FMS-F08, FMS-F09 · 169 lines

Credit litres come off the walk-in invoice at the same tank and price as the slip; if that line has no litres left they spill to another tank of the same item, so the totals always match the meters.

```python
# forecourt/posting/sales.py
"""Sales invoices for a closed shift (FMS-F13; design guide 8.2 steps 1 and 2).

Credit slips become one Sales Invoice per customer (or Delivery Notes when the company
invoices monthly). Everything else sold in the shift becomes one walk-in invoice, with
the credit litres taken off the tank and price they were drawn from.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.calc.numbers import litres, money

from .context import PostingContext

QTY_EPS = 0.0005


def tank_warehouse(tank: str) -> str:
	return frappe.get_cached_value("Fuel Tank", tank, "warehouse")


def credit_tank(shift, cs) -> str:
	"""Which tank a credit slip drew from.

	1. the slip's nozzle, 2. the cashier's reading row for that item with the most litres,
	3. any reading row for that item. Gate FMS-S108 has already checked the litres exist.
	"""
	if cs.nozzle:
		return frappe.get_cached_value("Nozzle", cs.nozzle, "tank")
	rows = [r for r in shift.meter_readings if r.item == cs.item]
	own = [r for r in rows if r.cashier == cs.cashier] or rows
	if not own:
		frappe.throw(_("Credit slip {0}: no meter reading for {1}").format(cs.slip_no, cs.item))
	return max(own, key=lambda r: flt(r.net_volume_l)).tank


def is_fuel(item: str) -> bool:
	return bool(frappe.get_cached_value("Item", item, "fms_is_fuel"))


# ---------------------------------------------------------------- credit


def post_credit_sales(ctx: PostingContext) -> None:
	by_customer: dict[str, list] = defaultdict(list)
	for cs in ctx.shift.credit_sales:
		by_customer[cs.customer].append(cs)
	monthly = ctx.accounts.credit_invoicing == "Monthly"
	for customer, slips in by_customer.items():
		doc = frappe.new_doc("Delivery Note" if monthly else "Sales Invoice")
		ctx.stamp(doc)
		doc.customer = customer
		doc.selling_price_list = frappe.get_cached_value("Station", ctx.station, "price_list")
		if not monthly:
			doc.update_stock = 1
			doc.due_date = None  # payment terms decide; ERPNext fills it
			doc.fms_cashier = slips[0].cashier if len({s.cashier for s in slips}) == 1 else None
		for cs in slips:
			doc.append(
				"items",
				{
					"item_code": cs.item,
					"qty": cs.qty,
					"rate": cs.rate,
					"warehouse": tank_warehouse(credit_tank(ctx.shift, cs)) if is_fuel(cs.item) else shop_warehouse(ctx, cs),
					"description": slip_description(cs),
					"cost_center": ctx.cost_center,
				},
			)
		# Rates are fixed by the shift's price segment; stop the price list overwriting them.
		doc.ignore_pricing_rule = 1
		ctx.submit(doc)
		for cs in slips:
			cs.db_set("sales_invoice" if not monthly else "delivery_note", doc.name, update_modified=False)


def slip_description(cs) -> str:
	parts = [f"Slip {cs.slip_no}"]
	if cs.vehicle:
		parts.append(frappe.get_cached_value("Customer Vehicle", cs.vehicle, "plate_no") or cs.vehicle)
	if cs.driver:
		parts.append(cs.driver)
	if cs.odometer:
		parts.append(f"odo {cs.odometer}")
	return " · ".join(parts)


def shop_warehouse(ctx: PostingContext, row) -> str:
	return row.get("warehouse") or frappe.get_cached_value("Station", ctx.station, "shop_warehouse")


# ---------------------------------------------------------------- walk-in


def walk_in_fuel_lines(shift) -> dict[tuple[str, str, float], float]:
	"""(item, tank, price) -> litres sold for cash, mobile, card and vouchers.

	Metered net litres minus credit litres at the same tank and price. A credit slip
	whose tank or price has no litres left spills to another tank of the same item and
	price, then to any line of the item, so the total always matches.
	"""
	lines: dict[tuple[str, str, float], float] = defaultdict(float)
	for r in shift.meter_readings:
		lines[(r.item, r.tank, flt(r.price))] += flt(r.net_volume_l)
	for cs in shift.credit_sales:
		if not is_fuel(cs.item):
			continue
		left = flt(cs.qty)
		tank = credit_tank(shift, cs)
		preferred = [(cs.item, tank, flt(cs.rate))]
		preferred += [k for k in lines if k[0] == cs.item and k[2] == flt(cs.rate) and k not in preferred]
		preferred += [k for k in lines if k[0] == cs.item and k not in preferred]
		for key in preferred:
			take = min(left, max(0.0, lines.get(key, 0.0)))
			lines[key] -= take
			left -= take
			if left <= QTY_EPS:
				break
		if left > QTY_EPS:
			frappe.throw(_("Credit slip {0}: {1} L of {2} has no metered litres").format(cs.slip_no, litres(left), cs.item))
	return {k: litres(v) for k, v in lines.items() if v > QTY_EPS}


def walk_in_item_lines(shift) -> dict[tuple[str, float, str | None], float]:
	"""(item, rate, warehouse) -> qty for non-fuel sales not already invoiced by POS."""
	lines: dict[tuple[str, float, str | None], float] = defaultdict(float)
	for r in shift.item_sales:
		if not r.pos_invoice:
			lines[(r.item, flt(r.rate), r.warehouse)] += flt(r.qty)
	return lines


def post_walk_in_sales(ctx: PostingContext) -> None:
	shift = ctx.shift
	fuel = walk_in_fuel_lines(shift)
	items = walk_in_item_lines(shift)
	if not fuel and not items:
		return
	si = frappe.new_doc("Sales Invoice")
	ctx.stamp(si)
	si.customer = ctx.walk_in_customer
	si.update_stock = 1
	si.ignore_pricing_rule = 1
	si.disable_rounded_total = 1  # cash PEs must settle it to the cent
	si.selling_price_list = frappe.get_cached_value("Station", ctx.station, "price_list")
	si.remarks = _("Shift sales {0}").format(shift.name)
	for (item, tank, price), qty in sorted(fuel.items()):
		si.append("items", {"item_code": item, "qty": qty, "rate": price, "warehouse": tank_warehouse(tank), "cost_center": ctx.cost_center})
	for (item, rate, warehouse), qty in sorted(items.items(), key=lambda kv: kv[0][0]):
		si.append(
			"items",
			{"item_code": item, "qty": qty, "rate": rate, "warehouse": warehouse or shop_warehouse(ctx, {}), "cost_center": ctx.cost_center},
		)
	ctx.submit(si)
	ctx.walk_in_invoice = si.name
	ctx.cashier_walk_in_share = cashier_shares(shift)


def cashier_shares(shift) -> dict[str, float]:
	"""Each cashier's part of the walk-in invoice: fuel + non-POS items - credit."""
	share: dict[str, float] = defaultdict(float)
	for c in shift.cashiers:
		share[c.cashier] = money(flt(c.fuel_amount) + flt(c.item_amount) - flt(c.credit))
	return dict(share)
```

### 6.4 `forecourt/posting/payments.py`

**Tasks:** FMS-F13 · 207 lines

Payment Entries are built field by field rather than with ERPNext's `get_payment_entry()`, so one function serves allocated, partly allocated and unallocated receipts. The largest cash receipt absorbs line-rounding cents; more than a few cents is treated as a bug.

```python
# forecourt/posting/payments.py
"""Payment Entries for a closed shift (FMS-F13; design guide 8.2 step 3 and 8.5).

- one Payment Entry per mobile money, card or voucher transaction, so each can be
  ticked off against the provider or bank statement by its reference;
- one cash Payment Entry per cashier for the balancing amount;
- one Payment Entry per debt receipt, allocated to the customer's oldest invoices.

All receipts against the walk-in invoice are allocated in order until it is settled.
Anything left over (only possible when a cashier gave change from the till for an
overpaid mobile transaction) stays as an unallocated advance and is offset by a
'Pay' entry from the till, so the walk-in customer still nets to zero.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate

from forecourt.calc.numbers import is_zero, money

from .context import PostingContext, mop_account

NON_CASH = ("Mobile Money", "Card", "Voucher")


class Allocator:
	"""Hands out the walk-in invoice's outstanding amount to receipts in order."""

	def __init__(self, invoice: str | None):
		self.invoice = invoice
		self.left = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")) if invoice else 0.0

	def take(self, amount: float) -> float:
		alloc = money(min(self.left, amount))
		self.left = money(self.left - alloc)
		return alloc


def receipt(
	ctx: PostingContext,
	*,
	party: str,
	amount: float,
	paid_to: str,
	mode_of_payment: str | None,
	cashier: str,
	reference_no: str,
	reference_date,
	allocations: list[tuple[str, float]] = (),
	remarks: str | None = None,
	payment_type: str = "Receive",
	collection=None,
):
	"""Build and submit one Payment Entry.

	Built field by field rather than with ERPNext's get_payment_entry() so the same
	code serves allocated, partly allocated and unallocated receipts. validate() fills
	account currencies and exchange rates.
	"""
	pe = frappe.new_doc("Payment Entry")
	ctx.stamp(pe)
	pe.payment_type = payment_type
	pe.party_type = "Customer"
	pe.party = party
	receivable = frappe.get_cached_value("Company", ctx.company, "default_receivable_account")
	if payment_type == "Receive":
		pe.paid_from, pe.paid_to = receivable, paid_to
	else:
		pe.paid_from, pe.paid_to = paid_to, receivable
	pe.paid_amount = pe.received_amount = amount
	pe.mode_of_payment = mode_of_payment
	pe.reference_no = reference_no
	pe.reference_date = getdate(reference_date)
	pe.fms_cashier = cashier
	if collection is not None:
		pe.fms_provider = collection.provider
		pe.fms_till_or_terminal = collection.till_or_terminal
		pe.fms_transaction_time = collection.transaction_time
	for invoice, alloc in allocations:
		if alloc:  # negative against a return (credit note)
			pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": invoice, "allocated_amount": alloc})
	pe.remarks = remarks or _("Shift {0} · {1}").format(ctx.shift.name, reference_no)
	ctx.submit(pe)
	if collection is not None:
		collection.db_set("payment_entry", pe.name, update_modified=False)
	return pe


def collection_account(ctx: PostingContext, c) -> tuple[str, str | None]:
	"""(account, mode of payment) for a non-cash collection row."""
	if c.collection_type == "Voucher" and not c.mode_of_payment:
		if not ctx.accounts.voucher_clearing_account:
			frappe.throw(_("Set the Voucher Clearing account in Forecourt Company Settings"))
		return ctx.accounts.voucher_clearing_account, None
	mop = c.mode_of_payment or frappe.get_cached_value("Payment Provider", c.provider, "mode_of_payment")
	return mop_account(mop, ctx.company), mop


def post_payments(ctx: PostingContext) -> None:
	shift = ctx.shift
	alloc = Allocator(ctx.walk_in_invoice)
	non_cash: dict[str, float] = defaultdict(float)

	# 1. one entry per mobile money, card and voucher transaction, oldest first
	rows = [c for c in shift.collections if c.collection_type in NON_CASH]
	rows.sort(key=lambda c: (get_datetime(c.transaction_time or shift.shift_end), c.idx))
	for c in rows:
		account, mop = collection_account(ctx, c)
		a = alloc.take(flt(c.amount))
		receipt(
			ctx,
			party=ctx.walk_in_customer,
			amount=flt(c.amount),
			paid_to=account,
			mode_of_payment=mop,
			cashier=c.cashier,
			reference_no=c.reference or f"{shift.name}-{c.idx}",
			reference_date=c.transaction_time or ctx.posting_date,
			allocations=[(ctx.walk_in_invoice, a)] if ctx.walk_in_invoice else [],
			collection=c,
		)
		non_cash[c.cashier] += flt(c.amount)

	# 2. cash: each cashier's share of the walk-in invoice less their non-cash receipts
	cash = {k: money(share - non_cash[k]) for k, share in ctx.cashier_walk_in_share.items()}
	settle_rounding(cash, alloc)
	cash_mop = frappe.db.get_value("Mode of Payment", {"type": "Cash", "enabled": 1}, "name")
	for cashier, amount in sorted(cash.items(), key=lambda kv: -kv[1]):
		if is_zero(amount):
			continue
		if amount > 0:
			receipt(
				ctx,
				party=ctx.walk_in_customer,
				amount=amount,
				paid_to=ctx.till_account,
				mode_of_payment=cash_mop,
				cashier=cashier,
				reference_no=f"{shift.name}-CASH-{cashier}",
				reference_date=ctx.posting_date,
				allocations=[(ctx.walk_in_invoice, alloc.take(amount))],
			)
		else:  # change given from the till for overpaid non-cash receipts
			receipt(
				ctx,
				party=ctx.walk_in_customer,
				amount=-amount,
				paid_to=ctx.till_account,
				mode_of_payment=cash_mop,
				cashier=cashier,
				reference_no=f"{shift.name}-CHANGE-{cashier}",
				reference_date=ctx.posting_date,
				payment_type="Pay",
				remarks=_("Change given from the till for overpaid non-cash receipts"),
			)

	# 3. debt receipts: cash from credit customers, oldest invoices first
	for c in shift.collections:
		if c.collection_type != "Debt Receipt":
			continue
		receipt(
			ctx,
			party=c.customer,
			amount=flt(c.amount),
			paid_to=ctx.till_account,
			mode_of_payment=cash_mop,
			cashier=c.cashier,
			reference_no=c.reference or f"{shift.name}-DEBT-{c.idx}",
			reference_date=ctx.posting_date,
			allocations=oldest_first(c.customer, ctx.company, flt(c.amount)),
			collection=c,
		)


def settle_rounding(cash: dict[str, float], alloc: Allocator) -> None:
	"""Line amounts on the invoice are rounded per line, cashier shares per reading row,
	so the two can differ by a few cents. The largest cash receipt absorbs it, which
	keeps the walk-in invoice exactly paid. More than one unit per line means a bug."""
	if not cash:
		return
	gap = money(alloc.left - sum(a for a in cash.values() if a > 0) + sum(-a for a in cash.values() if a < 0))
	if is_zero(gap):
		return
	tolerance = 0.05 * (len(cash) + 1)
	if abs(gap) > tolerance:
		frappe.throw(_("Walk-in invoice and cashier shares differ by {0}; recompute the shift").format(gap))
	largest = max(cash, key=lambda k: cash[k])
	cash[largest] = money(cash[largest] + gap)


def oldest_first(customer: str, company: str, amount: float) -> list[tuple[str, float]]:
	out, left = [], amount
	for inv in frappe.get_all(
		"Sales Invoice",
		{"customer": customer, "company": company, "docstatus": 1, "outstanding_amount": (">", 0)},
		["name", "outstanding_amount"],
		order_by="posting_date asc, creation asc",
	):
		if left <= 0:
			break
		take = money(min(left, flt(inv.outstanding_amount)))
		out.append((inv.name, take))
		left = money(left - take)
	return out  # any remainder stays as an advance on the customer
```

### 6.5 `forecourt/posting/journals.py`

**Tasks:** FMS-F14, FMS-G03 · 100 lines

`Lines` takes signed amounts, so a correction can reverse a resolution with the same code.

```python
# forecourt/posting/journals.py
"""One Journal Entry per shift for cash movements that are not sales (FMS-F14;
design guide 8.2 step 4): expenses paid from the till, drops to the safe, and the
cashier resolution lines. After it, the till holds exactly what was counted.

Shift Corrections reuse `resolution_journal` for the new differences they create.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.calc.numbers import is_zero, money

from .context import PostingContext


def expense_account(expense_type: str, company: str) -> str:
	account = frappe.db.get_value("Expense Type Account", {"parent": expense_type, "company": company}, "expense_account")
	if not account:
		frappe.throw(_("Expense Type {0} has no account for {1}").format(expense_type, company))
	return account


class Lines:
	"""Journal lines with signed amounts: positive debits, negative credits."""

	def __init__(self, ctx: PostingContext):
		self.ctx, self.rows = ctx, []

	def add(self, account: str, amount: float, remark: str, employee: str | None = None) -> None:
		amount = money(amount)
		if is_zero(amount):
			return
		row = {
			"account": account,
			"debit_in_account_currency": amount if amount > 0 else 0,
			"credit_in_account_currency": -amount if amount < 0 else 0,
			"cost_center": self.ctx.cost_center,
			"station": self.ctx.station,  # accounting dimension on Journal Entry Account
			"user_remark": remark,
		}
		if employee:
			row.update(party_type="Employee", party=employee)
		self.rows.append(row)

	def pair(self, debit_account: str, credit_account: str, amount: float, remark: str, employee: str | None = None, on_debit=True):
		"""DR one account, CR the other. A negative amount reverses the pair."""
		self.add(debit_account, amount, remark, employee if on_debit else None)
		self.add(credit_account, -amount, remark, None if on_debit else employee)

	def resolutions(self, rows) -> list:
		acc, till = self.ctx.accounts, self.ctx.till_account
		used = []
		for r in rows:
			if r.resolution_for != "Cashier" or is_zero(flt(r.amount)):
				continue
			remark = f"{r.action} · {r.cashier} · {r.reason}"
			if r.action == "Charge to cashier":
				self.pair(acc.staff_shortage_receivable_account, till, flt(r.amount), remark, employee=r.cashier)
			elif r.action == "Write off":
				self.pair(acc.cash_short_account, till, flt(r.amount), remark)
			elif r.action == "Record excess":
				self.pair(till, acc.cash_over_account, flt(r.amount), remark)
			used.append(r)
		return used

	def submit(self, remark: str):
		if not self.rows:
			return None
		je = frappe.new_doc("Journal Entry")
		self.ctx.stamp(je)
		je.voucher_type = "Journal Entry"
		je.user_remark = remark
		for row in self.rows:
			je.append("accounts", row)
		self.ctx.submit(je)
		return je


def post_journal(ctx: PostingContext) -> None:
	shift = ctx.shift
	lines = Lines(ctx)
	for c in shift.collections:
		if c.collection_type == "Expense":
			lines.pair(expense_account(c.expense_type, ctx.company), ctx.till_account, flt(c.amount), f"{c.expense_type} · {c.cashier}")
		elif c.collection_type == "Drop":
			lines.pair(ctx.safe_account, ctx.till_account, flt(c.amount), _("Drop {0} · {1}").format(c.reference or c.idx, c.cashier))
	used = lines.resolutions(shift.resolutions)
	je = lines.submit(_("Shift {0}: expenses, drops and cash differences").format(shift.name))
	if je:
		for r in used:
			r.db_set("journal_entry", je.name, update_modified=False)


def resolution_journal(ctx: PostingContext, rows, remark: str):
	lines = Lines(ctx)
	lines.resolutions(rows)
	return lines.submit(remark)
```

### 6.6 `forecourt/posting/stock.py`

**Tasks:** FMS-F14 · 64 lines

Policy from company settings: every shift with dips (default), last shift of the day, or outside tolerance only.

```python
# forecourt/posting/stock.py
"""Tank variance posting (FMS-F14; design guide 5.7).

One Stock Reconciliation per shift sets each dipped tank's book stock to the dip.
It is dated with the other shift documents, after the walk-in and credit invoices
have taken the sold litres out, so the difference it posts is the tank variance
and nothing else.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt

from forecourt.utils.stock import tank_book_stock, tank_valuation_rate

from .context import PostingContext

MIN_ADJUST_L = 0.001


def should_post(ctx: PostingContext, t) -> bool:
	policy = ctx.settings.post_tank_variance
	if t.dip_l in (None, ""):
		return False
	if policy == "Outside tolerance only":
		return not t.within_tolerance
	if policy == "Last shift of day":
		return is_last_shift_of_day(ctx.shift)
	return True  # "Every shift with dips"


def is_last_shift_of_day(shift) -> bool:
	"""The shift's template has the highest `sequence` of the station's active templates."""
	seqs = frappe.get_all("Forecourt Shift Template", {"station": shift.station, "active": 1}, ["name", "sequence"])
	last = max(seqs, key=lambda t: t.sequence or 0, default=None)
	return last is None or last.name == shift.shift_template


def post_stock_reconciliation(ctx: PostingContext) -> None:
	at = f"{ctx.posting_date} {ctx.posting_time}"
	sr = frappe.new_doc("Stock Reconciliation")
	ctx.stamp(sr)
	sr.purpose = "Stock Reconciliation"
	sr.expense_account = ctx.accounts.fuel_stock_variance_account
	for t in ctx.shift.tank_dips:
		if not should_post(ctx, t):
			continue
		# Book stock read now includes the invoices just submitted in this transaction.
		book = tank_book_stock(t.tank, at)
		if abs(flt(t.dip_l) - book) < MIN_ADJUST_L:
			continue
		item, warehouse = frappe.get_cached_value("Fuel Tank", t.tank, ["item", "warehouse"])
		sr.append(
			"items",
			{
				"item_code": item,
				"warehouse": warehouse,
				"qty": flt(t.dip_l),
				# Keep the tank's moving average: a variance is a loss of litres, not of value per litre.
				"valuation_rate": tank_valuation_rate(t.tank, at) or None,
			},
		)
	if sr.items:
		ctx.submit(sr)
```

### 6.7 `forecourt/posting/ledgers.py`

**Tasks:** FMS-F15, FMS-G03 · 301 lines

`frappe.db.bulk_insert` writes a 300-row Sales Ledger in one statement. Ledger `posting_date` is the shift date, so reports group by the business day even when a night shift posts the next morning.

```python
# forecourt/posting/ledgers.py
"""FMS ledgers (FMS-F15; design guide 10.4).

Four flat, append-only tables that reports read instead of joining shifts and their
child tables. Written once on close with bulk inserts; never updated except for
`is_cancelled` and `superseded_by`.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt, now_datetime

from forecourt.calc.attribution import ExactPayment, SalesLine, attribute

from .context import PostingContext

LEDGERS = ("Wetstock Ledger Entry", "Nozzle Ledger Entry", "Sales Ledger Entry", "Cashier Ledger Entry")


def insert_rows(doctype: str, rows: list[dict]) -> None:
	"""frappe.db.bulk_insert with the standard columns filled in.

	One INSERT per 10,000 rows instead of one get_doc().insert() per row: a shift with
	300 mobile money rows writes its Sales Ledger in milliseconds.
	"""
	if not rows:
		return
	now, user = now_datetime(), frappe.session.user
	std = {"owner": user, "modified_by": user, "creation": now, "modified": now, "docstatus": 0}
	fields = ["name", *std, *rows[0].keys()]
	values = [(frappe.generate_hash(length=12), *std.values(), *r.values()) for r in rows]
	frappe.db.bulk_insert(doctype, fields=fields, values=values)


def common(ctx: PostingContext) -> dict:
	return {
		"company": ctx.company,
		"station": ctx.station,
		"posting_date": ctx.shift.shift_date,  # reports group by shift date
		"forecourt_shift": ctx.shift.name,
		"voucher_type": "Forecourt Shift",
		"voucher_no": ctx.shift.name,
		"is_cancelled": 0,
		"correction": ctx.correction,
	}


def write_ledgers(ctx: PostingContext) -> None:
	insert_rows("Wetstock Ledger Entry", wetstock_rows(ctx))
	insert_rows("Nozzle Ledger Entry", nozzle_rows(ctx))
	insert_rows("Sales Ledger Entry", sales_rows(ctx))
	insert_rows("Cashier Ledger Entry", cashier_rows(ctx))


def supersede(shift: str, correction: str, doctypes=LEDGERS) -> None:
	"""Mark a shift's current rows as replaced by a correction (they stay for the audit view)."""
	for doctype in doctypes:
		frappe.db.set_value(
			doctype,
			{"forecourt_shift": shift, "is_cancelled": 0, "superseded_by": ("is", "not set")},
			"superseded_by",
			correction,
			update_modified=False,
		)


def mark_ledgers_cancelled(shift: str) -> None:
	for doctype in LEDGERS:
		frappe.db.set_value(doctype, {"forecourt_shift": shift, "is_cancelled": 0}, "is_cancelled", 1, update_modified=False)


# ---------------------------------------------------------------- wetstock


def wetstock_rows(ctx: PostingContext) -> list[dict]:
	s = ctx.shift
	cashiers_by_tank: dict[str, set] = defaultdict(set)
	test_by_tank: dict[str, float] = defaultdict(float)
	for r in s.meter_readings:
		cashiers_by_tank[r.tank].add(r.cashier)
		test_by_tank[r.tank] += flt(r.test_volume_l)
	out = []
	for t in s.tank_dips:
		rate = _rate(ctx, t.tank)
		out.append(
			{
				**common(ctx),
				"tank": t.tank,
				"item": t.item,
				"entry_type": "Shift",
				"shift_start": s.shift_start,
				"shift_end": s.shift_end,
				"opening_l": t.opening_l,
				"receipt_l": t.receipts_l,
				"sales_l": t.sales_l,
				"test_l": test_by_tank[t.tank],
				"own_use_l": t.own_use_l,
				"transfer_l": t.transfers_l,
				"expected_l": t.expected_l,
				"dip_l": t.dip_l,
				"variance_l": t.variance_l,
				"variance_pct": t.variance_pct,
				"cashiers": ", ".join(sorted(c for c in cashiers_by_tank[t.tank] if c)),
				"reason": t.reason,
				"approved_by": t.approved_by,
				"dip_entry_mode": s.dip_entry_mode,
				"source": t.source or "Manual",
				"valuation_rate": rate,
				"variance_value": flt(t.variance_l) * rate,
			}
		)
	return out


def _rate(ctx: PostingContext, tank: str) -> float:
	from forecourt.utils.stock import tank_valuation_rate

	return tank_valuation_rate(tank, f"{ctx.posting_date} {ctx.posting_time}")


# ---------------------------------------------------------------- nozzle


def nozzle_rows(ctx: PostingContext) -> list[dict]:
	s = ctx.shift
	out = []
	for r in s.meter_readings:
		dispenser = frappe.get_cached_value("Nozzle", r.nozzle, "dispenser")
		row = {
			**common(ctx),
			"shift_template": s.shift_template,
			"island": frappe.get_cached_value("Dispenser", dispenser, "island"),
			"dispenser": dispenser,
			"nozzle": r.nozzle,
			"tank": r.tank,
			"item": r.item,
			"cashier": r.cashier,
			"attendant": r.attendant,
			"segment_no": r.segment_no,
			"price": r.price,
			"basis_meter": r.basis_meter,
			"gross_l": r.basis_volume_l,
			"test_l": r.test_volume_l,
			"own_use_l": r.own_use_l,
			"net_l": r.net_volume_l,
			"amount": r.amount,
			"drift_evol_mvol_l": r.drift_evol_mvol_l,
			"drift_ecash_evol_l": r.drift_ecash_evol_l,
			"drift_ecash_mvol_l": r.drift_ecash_mvol_l,
			"source": r.source or "Manual",
		}
		for m in ("ecash", "evol", "mvol"):
			opening, closing = r.get(f"opening_{m}"), r.get(f"closing_{m}")
			row[f"opening_{m}"], row[f"closing_{m}"] = opening, closing
			row[f"{m}_delta"] = None if closing in (None, "") else _delta(r, m)
		out.append(row)
	return out


def _delta(r, m: str) -> float:
	from forecourt.calc.meters import MeterPair, meter_delta
	from forecourt.utils.stock import nozzle_modulus

	return meter_delta(
		MeterPair(flt(r.get(f"opening_{m}")), flt(r.get(f"closing_{m}")), bool(r.get(f"rollover_{m}")), nozzle_modulus(r.nozzle)[m] or None)
	)


# ---------------------------------------------------------------- sales


def sales_rows(ctx: PostingContext) -> list[dict]:
	"""Per cashier: every sales line with the payments that settled it.

	Lines: reading rows (fuel) and item rows. Exact payments: credit slips (on the
	cashier's reading row for that item and price) and POS invoices. Everything else
	the cashier received is attributed in proportion (calc.attribution).
	"""
	s = ctx.shift
	lines_by_cashier: dict[str, list[SalesLine]] = defaultdict(list)
	meta: dict[str, dict] = {}
	for r in s.meter_readings:
		key = f"NOZ:{r.name}"
		lines_by_cashier[r.cashier].append(SalesLine(key, flt(r.amount)))
		dispenser = frappe.get_cached_value("Nozzle", r.nozzle, "dispenser")
		meta[key] = {
			"item": r.item,
			"is_fuel": 1,
			"nozzle": r.nozzle,
			"dispenser": dispenser,
			"island": frappe.get_cached_value("Dispenser", dispenser, "island"),
			"tank": r.tank,
			"qty": flt(r.net_volume_l),
			"amount": flt(r.amount),
		}
	for r in s.item_sales:
		key = f"ITEM:{r.name}"
		lines_by_cashier[r.cashier].append(SalesLine(key, flt(r.amount)))
		meta[key] = {"item": r.item, "is_fuel": 0, "qty": flt(r.qty), "amount": flt(r.amount)}

	exact_by_cashier: dict[str, list[ExactPayment]] = defaultdict(list)
	exact_meta: dict[tuple[str, str], dict] = {}
	for cs in s.credit_sales:
		key = credit_line_key(s, cs)
		if key is None:  # non-fuel item on credit: its own line
			key = f"CREDIT:{cs.name}"
			lines_by_cashier[cs.cashier].append(SalesLine(key, flt(cs.amount)))
			meta[key] = {"item": cs.item, "is_fuel": 0, "qty": flt(cs.qty), "amount": flt(cs.amount)}
		exact_by_cashier[cs.cashier].append(ExactPayment(key, "Credit", flt(cs.amount)))
		exact_meta[(key, "Credit")] = {"customer": cs.customer, "customer_vehicle": cs.vehicle}
	for r in s.item_sales:
		if r.pos_invoice:
			exact_by_cashier[r.cashier].append(ExactPayment(f"ITEM:{r.name}", "POS", flt(r.amount)))

	out = []
	item_group = {}
	for c in s.cashiers:
		k = c.cashier
		cash_for_sales = flt(c.accounted) - flt(c.credit) - flt(c.mobile) - flt(c.card) - flt(c.voucher) - flt(c.debt_receipts)
		payments = {"Mobile Money": flt(c.mobile), "Card": flt(c.card), "Voucher": flt(c.voucher), "Cash": cash_for_sales}
		for a in attribute(lines_by_cashier[k], exact_by_cashier[k], payments):
			m = meta[a.key]
			share = a.amount / m["amount"] if m["amount"] else 0
			item_group.setdefault(m["item"], frappe.get_cached_value("Item", m["item"], "item_group"))
			out.append(
				{
					**common(ctx),
					"shift_template": s.shift_template,
					"cashier": k,
					"item": m["item"],
					"item_group": item_group[m["item"]],
					"is_fuel": m["is_fuel"],
					"nozzle": m.get("nozzle"),
					"dispenser": m.get("dispenser"),
					"island": m.get("island"),
					"tank": m.get("tank"),
					"payment_type": a.payment_type,
					"customer": exact_meta.get((a.key, a.payment_type), {}).get("customer"),
					"customer_vehicle": exact_meta.get((a.key, a.payment_type), {}).get("customer_vehicle"),
					"qty": round(m["qty"] * share, 3),
					"amount": a.amount,
					"basis": a.basis,
				}
			)
	return out


def credit_line_key(shift, cs) -> str | None:
	"""The reading row a fuel credit slip belongs to: same cashier, item and price,
	the slip's nozzle when given. None for non-fuel items."""
	rows = [r for r in shift.meter_readings if r.item == cs.item and r.cashier == cs.cashier]
	if not rows:
		return None
	match = [r for r in rows if flt(r.price) == flt(cs.rate)] or rows
	if cs.nozzle:
		match = [r for r in match if r.nozzle == cs.nozzle] or match
	return f"NOZ:{max(match, key=lambda r: flt(r.amount)).name}"


# ---------------------------------------------------------------- cashier


def cashier_rows(ctx: PostingContext) -> list[dict]:
	s = ctx.shift
	litres = defaultdict(float)
	for r in s.meter_readings:
		litres[r.cashier] += flt(r.net_volume_l)
	res = defaultdict(list)
	for r in s.resolutions:
		if r.resolution_for == "Cashier":
			res[r.cashier].append(r)
	out = []
	for c in s.cashiers:
		lines = res[c.cashier]
		out.append(
			{
				**common(ctx),
				"cashier": c.cashier,
				"fuel_l": litres[c.cashier],
				"fuel_amount": c.fuel_amount,
				"item_amount": c.item_amount,
				"debt_receipts": c.debt_receipts,
				"float_amount": c.float_amount,
				"cash": c.cash_counted,
				"mobile": c.mobile,
				"card": c.card,
				"credit": c.credit,
				"voucher": c.voucher,
				"expenses": c.expenses,
				"drops": c.drops,
				"expected": c.expected,
				"accounted": c.accounted,
				"difference": c.difference,
				"resolution_action": ", ".join(sorted({r.action for r in lines})) or None,
				"resolution_amount": sum(flt(r.amount) for r in lines),
				"reason": ", ".join(sorted({r.reason for r in lines if r.reason})) or None,
			}
		)
	return out
```

---

## 7. Document events on ERPNext DocTypes (`forecourt/events`) and hooks

ERPNext classes are never overridden. Everything attaches through `doc_events`, so ERPNext upgrades do not break the app.

### 7.1 `forecourt/hooks.py`

**Tasks:** FMS-B02, FMS-B08, FMS-C09, FMS-E03, FMS-E05, FMS-F13, FMS-I02 · 99 lines

Fixtures are filtered by module or name so a site's own customisations never enter the repository. `after_install` creates the Station accounting dimension and the root Station Group (not shown).

```python
# forecourt/hooks.py
"""forecourt/hooks.py (FMS-B02, FMS-B08, FMS-C09, FMS-E03, FMS-E05, FMS-F13, FMS-I02)."""

app_name = "forecourt"
app_title = "Forecourt"
app_publisher = "FMS"
app_description = "Forecourt management for ERPNext"
app_email = "dev@example.com"
app_license = "mit"
required_apps = ["frappe", "erpnext", "hrms"]

# ---------------------------------------------------------------- fixtures
# Only records this app owns: filter by module so a site's own customisations
# never end up in the repository.
_FMS_MODULES = ["Forecourt Setup", "Wetstock", "Forecourt Shift", "Forecourt Finance", "Forecourt Integrations"]
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "in", _FMS_MODULES]]},
	{"dt": "Property Setter", "filters": [["module", "in", _FMS_MODULES]]},
	{"dt": "Role", "filters": [["name", "like", "Forecourt %"]]},
	{"dt": "Stock Entry Type", "filters": [["name", "=", "Fuel Own Use"]]},
	{"dt": "Workflow", "filters": [["document_type", "in", ["Forecourt Shift", "Fuel Price Change", "Shift Correction"]]]},
	{"dt": "Workflow State", "filters": [["name", "like", "FMS %"]]},
	{"dt": "Workflow Action Master", "filters": [["name", "like", "FMS %"]]},
	"Variance Reason",
	"Own Use Purpose",
]

after_install = "forecourt.setup.install.after_install"  # Accounting Dimension "Station", root Station Group
after_migrate = "forecourt.setup.install.after_migrate"

# ---------------------------------------------------------------- client
doctype_js = {
	"Purchase Receipt": "public/js/purchase_receipt.js",  # delivery dips, shortage button
	"Stock Entry": "public/js/stock_entry.js",  # Fuel Own Use fields
}

# ---------------------------------------------------------------- document events
# Never override ERPNext classes: everything goes through doc_events, so ERPNext
# upgrades do not break the app. No frappe.db.commit() in any of these (v16 rule).
_GENERATED = "forecourt.events.guards.block_generated"
_CLEAR = "forecourt.utils.settings.clear_settings_cache"

doc_events = {
	"Purchase Receipt": {
		"validate": "forecourt.events.purchase_receipt.validate",
		"before_submit": "forecourt.events.guards.block_posting_into_closed_shift",
		"on_submit": "forecourt.events.purchase_receipt.on_submit",
		"before_cancel": "forecourt.events.guards.block_if_used_by_closed_shift",
		"on_cancel": "forecourt.events.purchase_receipt.on_cancel",
	},
	"Stock Entry": {
		"validate": "forecourt.events.stock_entry.validate",
		"before_submit": "forecourt.events.stock_entry.before_submit",
		"before_cancel": "forecourt.events.guards.block_if_used_by_closed_shift",
	},
	"Sales Invoice": {"before_cancel": _GENERATED},
	"Delivery Note": {"before_cancel": _GENERATED},
	"Payment Entry": {"before_cancel": _GENERATED},
	"Journal Entry": {"before_cancel": _GENERATED},
	"Stock Reconciliation": {"before_cancel": _GENERATED},
	"Forecourt Settings": {"on_update": _CLEAR},
	"Forecourt Company Settings": {"on_update": _CLEAR},
	"Station": {"on_update": _CLEAR},
	"Fuel Tank": {"on_update": _CLEAR},
	"Dispenser": {"on_update": _CLEAR},
}

# ---------------------------------------------------------------- permissions
_SG = "forecourt.permissions.station_group"
_STATION_BOUND = {
	"Station": "station",
	"Fuel Tank": "fuel_tank",
	"Dispenser": "dispenser",
	"Nozzle": "nozzle",
	"Forecourt Shift Template": "forecourt_shift_template",
	"Fuel Price Change": "fuel_price_change",
	"Meter Change": "meter_change",
	"Tank Dip": "tank_dip",
	"Forecourt Shift": "forecourt_shift",
	"Shift Correction": "shift_correction",
	"Wetstock Ledger Entry": "wetstock_ledger_entry",
	"Nozzle Ledger Entry": "nozzle_ledger_entry",
	"Sales Ledger Entry": "sales_ledger_entry",
	"Cashier Ledger Entry": "cashier_ledger_entry",
	"Payment Feed Entry": "payment_feed_entry",
	"Payment Import Batch": "payment_import_batch",
}
permission_query_conditions = {dt: f"{_SG}.{fn}" for dt, fn in _STATION_BOUND.items()}
has_permission = {dt: f"{_SG}.has_station_permission" for dt in _STATION_BOUND}

# ---------------------------------------------------------------- scheduler
scheduler_events = {
	"hourly": ["forecourt.tasks.flag_overdue_shifts"],
	"daily": ["forecourt.tasks.retry_failed_inbox"],
}

# ---------------------------------------------------------------- misc
# Ledgers are append-only; keep them out of global search and deletion cascades.
global_search_doctypes = {"Default": [{"doctype": "Forecourt Shift"}, {"doctype": "Station"}, {"doctype": "Fuel Tank"}]}
ignore_links_on_delete = ["Wetstock Ledger Entry", "Nozzle Ledger Entry", "Sales Ledger Entry", "Cashier Ledger Entry"]
```

### 7.2 `forecourt/events/purchase_receipt.py`

**Tasks:** FMS-E03, FMS-E04 · 150 lines

Manual GRN with delivery dips. *Record delivery shortage* creates a **draft** Stock Entry; a person reviews and submits it.

```python
# forecourt/events/purchase_receipt.py
"""Manual fuel GRN with delivery dips (FMS-E03, FMS-E04; design guide 5.5).

The manager posts the Purchase Receipt by hand. These hooks compute the dips section,
enforce it when the station requires dips, and write the Delivery row of the
Wetstock Ledger. The FMS never creates GRNs itself.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.calc.calibration import volume_at
from forecourt.calc.errors import CalcError
from forecourt.calc.wetstock import DeliveryDip, delivery_variance
from forecourt.errors import GateCollector, fms_throw, from_calc_error
from forecourt.utils.settings import get_settings
from forecourt.utils.stock import calibration_rows


def fuel_tank_lines(doc) -> dict[str, float]:
	"""tank -> invoiced litres, from item rows whose warehouse is a fuel tank."""
	by_wh = defaultdict(float)
	for it in doc.items:
		by_wh[it.warehouse] += flt(it.stock_qty)
	tanks = frappe.get_all("Fuel Tank", {"warehouse": ("in", list(by_wh))}, ["name", "warehouse"])
	return {t.name: by_wh[t.warehouse] for t in tanks}


def validate(doc, method=None) -> None:
	tanks = fuel_tank_lines(doc)
	if not tanks:
		return  # not a fuel delivery
	if not doc.get("station"):
		doc.station = frappe.get_cached_value("Fuel Tank", next(iter(tanks)), "station")
	s = get_settings(doc.station)
	dips = {d.tank: d for d in doc.get("fms_delivery_dips") or []}

	with GateCollector() as g:
		for tank, invoiced in tanks.items():
			d = dips.get(tank)
			if d is None:
				if s.delivery_dips_required:
					g.add("FMS-T204", _("Add delivery dips for tank {0}").format(tank))
				continue
			compute_dip(doc, d, invoiced, get_settings(doc.station, tank=tank), g)
		for tank in dips:
			g.check(tank in tanks, "FMS-T206", _("Tank {0} has dips but no item row").format(tank))


def compute_dip(doc, d, invoiced: float, s, g: GateCollector) -> None:
	d.item = frappe.get_cached_value("Fuel Tank", d.tank, "item")
	d.dip_entry_mode = s.dip_entry_mode
	d.invoiced_l = invoiced
	if s.dip_entry_mode == "Depth via calibration chart":
		rows, _water = calibration_rows(d.tank, doc.posting_date)
		try:
			d.volume_before_l = volume_at(flt(d.dip_before_mm), rows)
			d.volume_after_l = volume_at(flt(d.dip_after_mm), rows)
		except CalcError as e:
			from_calc_error(e)
	try:
		r = delivery_variance(
			DeliveryDip(flt(d.volume_before_l), flt(d.volume_after_l), flt(d.sales_during_drop_l), invoiced),
			s.delivery_tolerance_pct,
		)
	except CalcError as e:
		g.add(e.code, e.message)
		return
	d.received_l, d.variance_l, d.variance_pct = r.received_l, r.variance_l, r.variance_pct
	if r.needs_reason:
		g.check(bool(d.reason), "FMS-T206", _("Tank {0}: short by {1} L ({2}%); choose a reason").format(d.tank, -r.variance_l, -r.variance_pct))


def on_submit(doc, method=None) -> None:
	from forecourt.posting.ledgers import insert_rows

	rows = []
	for d in doc.get("fms_delivery_dips") or []:
		rows.append(
			{
				"company": doc.company,
				"station": doc.station,
				"posting_date": doc.posting_date,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"is_cancelled": 0,
				"tank": d.tank,
				"item": d.item,
				"entry_type": "Delivery",
				"opening_l": d.volume_before_l,
				"dip_l": d.volume_after_l,
				"sales_l": d.sales_during_drop_l,
				"receipt_l": d.received_l,
				"invoiced_l": d.invoiced_l,
				"delivery_variance_l": d.variance_l,
				"variance_pct": d.variance_pct,
				"supplier": doc.supplier,
				"transporter": doc.get("fms_transporter"),
				"driver": doc.get("fms_driver"),
				"reason": d.reason,
				"dip_entry_mode": d.dip_entry_mode,
				"source": "Manual",
			}
		)
	insert_rows("Wetstock Ledger Entry", rows)


def on_cancel(doc, method=None) -> None:
	# Blocked by guards.block_if_used_by_closed_shift (registered before this handler).
	frappe.db.set_value(
		"Wetstock Ledger Entry", {"voucher_type": doc.doctype, "voucher_no": doc.name}, "is_cancelled", 1, update_modified=False
	)


@frappe.whitelist()
def record_delivery_shortage(purchase_receipt: str, tank: str) -> str:
	"""'Record delivery shortage' button: a *draft* Material Issue for the short litres,
	charged to Delivery Shortage Claims, linked to the GRN. A person reviews and submits it.
	"""
	pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
	pr.check_permission("read")
	d = next((x for x in pr.fms_delivery_dips if x.tank == tank), None)
	if not d or flt(d.variance_l) >= 0:
		fms_throw("FMS-T206", _("Tank {0} has no shortage on {1}").format(tank, purchase_receipt))
	if d.shortage_stock_entry:
		return d.shortage_stock_entry
	item, warehouse = frappe.get_cached_value("Fuel Tank", tank, ["item", "warehouse"])
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Issue"
	se.company = pr.company
	se.station = pr.station
	se.posting_date = pr.posting_date
	se.fms_purchase_receipt = pr.name
	se.remarks = _("Delivery shortage on {0}, tank {1}").format(pr.name, tank)
	se.append(
		"items",
		{
			"item_code": item,
			"s_warehouse": warehouse,
			"qty": -flt(d.variance_l),
			"expense_account": frappe.get_cached_value("Forecourt Company Settings", pr.company, "delivery_shortage_claims_account"),
		},
	)
	se.insert()
	d.db_set("shortage_stock_entry", se.name)
	return se.name
```

### 7.3 `forecourt/events/stock_entry.py`

**Tasks:** FMS-E05 · 56 lines

Fuel Own Use: nozzle, purpose and narration are mandatory; the source tank, item and expense account are set from them.

```python
# forecourt/events/stock_entry.py
"""Fuel Own Use (FMS-E05; design guide 5.10).

Generator, company vehicle or staff fuel is a Stock Entry of type *Fuel Own Use*
(Material Issue). The shift pulls it in by nozzle and time and takes it out of the
cashier's litres, so nobody pays for fuel the station used itself.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime

from forecourt.errors import GateCollector
from forecourt.utils.shifts import get_shift_at

OWN_USE = "Fuel Own Use"


def validate(doc, method=None) -> None:
	if doc.stock_entry_type != OWN_USE:
		return
	with GateCollector() as g:
		g.check(bool(doc.fms_nozzle), "FMS-S113", _("Choose the nozzle the fuel was drawn from"))
		g.check(bool(doc.fms_use_purpose), "FMS-S113", _("Choose the purpose"))
		g.check(bool((doc.remarks or "").strip()), "FMS-S113", _("Write what the fuel was used for"))
		if doc.fms_use_purpose and frappe.get_cached_value("Own Use Purpose", doc.fms_use_purpose, "requires_vehicle"):
			g.check(bool(doc.fms_vehicle_or_asset), "FMS-S113", _("Enter the vehicle or asset"))
	tank = frappe.get_cached_value("Nozzle", doc.fms_nozzle, "tank")
	item, warehouse, station = frappe.get_cached_value("Fuel Tank", tank, ["item", "warehouse", "station"])
	doc.station = station
	account = purpose_account(doc.fms_use_purpose, doc.company)
	for row in doc.items:
		row.item_code = row.item_code or item
		row.s_warehouse = warehouse
		row.expense_account = account
		if row.item_code != item:
			frappe.throw(_("Row {0}: nozzle {1} dispenses {2}").format(row.idx, doc.fms_nozzle, item))
	at = get_datetime(f"{doc.posting_date} {doc.posting_time}")
	doc.fms_forecourt_shift = get_shift_at(station, at)


def purpose_account(purpose: str, company: str) -> str:
	account = frappe.db.get_value("Own Use Purpose Account", {"parent": purpose, "company": company}, "expense_account")
	if not account:
		frappe.throw(_("Own Use Purpose {0} has no expense account for {1}").format(purpose, company))
	return account


def before_submit(doc, method=None) -> None:
	"""Own use posted into a shift that is already closed would change its litres."""
	if doc.stock_entry_type == OWN_USE and doc.fms_forecourt_shift:
		if frappe.db.get_value("Forecourt Shift", doc.fms_forecourt_shift, "docstatus") == 1:
			from forecourt.errors import fms_throw

			fms_throw("FMS-C502", _("Shift {0} is closed; record this through a Shift Correction").format(doc.fms_forecourt_shift))
```

### 7.4 `forecourt/events/guards.py`

**Tasks:** FMS-F13, FMS-G01 · 54 lines

Generated documents, and GRNs or own-use entries inside a closed shift, cancel only under a Shift Correction.

```python
# forecourt/events/guards.py
"""Cancel guards (FMS-F13, FMS-G01; design guide 6.8).

Documents generated by a closed shift, and documents a closed shift consumed (GRNs,
own use, transfers), may only be cancelled by a Shift Correction, which sets
frappe.flags.fms_correction for the duration of its apply step.
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.errors import fms_throw


def allowed() -> bool:
	return bool(frappe.flags.fms_correction or frappe.flags.fms_posting)


def block_generated(doc, method=None) -> None:
	"""before_cancel on Sales Invoice, Payment Entry, Journal Entry, Stock Reconciliation, Delivery Note."""
	if doc.get("fms_forecourt_shift") and not allowed():
		fms_throw("FMS-C502", _("{0} was created by shift {1}").format(doc.name, doc.fms_forecourt_shift))


def block_if_used_by_closed_shift(doc, method=None) -> None:
	"""before_cancel on Purchase Receipt and Stock Entry: their litres are inside a closed shift."""
	if allowed():
		return
	if not doc.get("station"):
		return
	from frappe.utils import get_datetime

	from forecourt.utils.shifts import get_shift_at

	shift = get_shift_at(doc.station, get_datetime(f"{doc.posting_date} {doc.posting_time}"), include_drafts=False)
	if shift:
		fms_throw("FMS-C502", _("{0} is part of closed shift {1}").format(doc.name, shift))


def block_posting_into_closed_shift(doc, method=None) -> None:
	"""before_submit on Purchase Receipt: a GRN back-dated into a closed shift would change
	that shift's receipts after the fact. Post it at the real time, or correct the shift."""
	if allowed() or not doc.get("station"):
		return
	if not doc.get("fms_delivery_dips"):
		return
	from frappe.utils import get_datetime

	from forecourt.utils.shifts import get_shift_at

	shift = get_shift_at(doc.station, get_datetime(f"{doc.posting_date} {doc.posting_time}"), include_drafts=False)
	if shift:
		fms_throw("FMS-C502", _("The time {0} {1} is inside closed shift {2}").format(doc.posting_date, doc.posting_time, shift))
```

### 7.5 `forecourt/public/js/purchase_receipt.js`

**Tasks:** FMS-E03, FMS-E04 · 28 lines

```javascript
// forecourt/public/js/purchase_receipt.js
// Purchase Receipt: delivery dips and the shortage button (FMS-E03, FMS-E04).
frappe.ui.form.on("Purchase Receipt", {
	setup(frm) {
		frm.set_query("tank", "fms_delivery_dips", () => ({
			filters: { station: frm.doc.station, status: "Active" },
		}));
	},
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		for (const d of frm.doc.fms_delivery_dips || []) {
			if (d.variance_l < 0 && !d.shortage_stock_entry) {
				frm.add_custom_button(__("Record delivery shortage ({0})", [d.tank]), async () => {
					const name = await frappe.xcall("forecourt.events.purchase_receipt.record_delivery_shortage",
						{ purchase_receipt: frm.doc.name, tank: d.tank });
					frappe.set_route("Form", "Stock Entry", name);
				}, __("Fuel"));
			}
		}
	},
});

// Litres mode: received and variance are shown after save (server calculates);
// tell the user so they don't wait for live numbers.
frappe.ui.form.on("GRN Delivery Dip", {
	tank(frm, cdt, cdn) {
		frappe.show_alert({ message: __("Variance is calculated when you save"), indicator: "blue" }, 3);
	},
});
```

### 7.6 `forecourt/public/js/stock_entry.js`

**Tasks:** FMS-E05 · 22 lines

```javascript
// forecourt/public/js/stock_entry.js
// Stock Entry: show the FMS fields only for Fuel Own Use (FMS-E05).
const OWN_USE_FIELDS = ["fms_nozzle", "fms_attendant", "fms_use_purpose", "fms_vehicle_or_asset"];

frappe.ui.form.on("Stock Entry", {
	setup(frm) {
		frm.set_query("fms_nozzle", () => ({ filters: { station: frm.doc.station, status: "Active" } }));
		frm.set_query("fms_attendant", () => ({ filters: { fms_is_forecourt_cashier: 1, status: "Active" } }));
	},
	refresh: toggle,
	stock_entry_type: toggle,
	fms_nozzle(frm) {
		// The item and source tank come from the nozzle; the server sets them on validate.
		if (frm.doc.fms_nozzle && !(frm.doc.items || []).length) frm.add_child("items", { qty: 0 });
		frm.refresh_field("items");
	},
});

function toggle(frm) {
	const own_use = frm.doc.stock_entry_type === "Fuel Own Use";
	for (const f of OWN_USE_FIELDS) frm.toggle_display(f, own_use);
	frm.toggle_reqd(["fms_nozzle", "fms_use_purpose"], own_use);
}
```

### 7.7 `forecourt/tasks.py`

**Tasks:** FMS-I04, FMS-J03 · 40 lines

Scheduled jobs may commit; document hooks may not.

```python
# forecourt/tasks.py
"""Scheduled jobs (FMS-I04, FMS-J03). Jobs may commit; document hooks may not."""

from __future__ import annotations

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import now_datetime

OVERDUE_AFTER = timedelta(hours=2)


def flag_overdue_shifts() -> None:
	"""Remind the station manager when a shift is still open two hours after its window."""
	cutoff = now_datetime() - OVERDUE_AFTER
	for s in frappe.get_all(
		"Forecourt Shift",
		{"docstatus": 0, "shift_end": ("<", cutoff), "status": ("not in", ["Closing"])},
		["name", "station", "owner"],
	):
		if frappe.db.exists("Notification Log", {"document_name": s.name, "subject": ("like", "%still open%")}):
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": s.owner,
				"type": "Alert",
				"document_type": "Forecourt Shift",
				"document_name": s.name,
				"subject": _("Shift {0} is still open").format(s.name),
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()


def retry_failed_inbox() -> None:
	"""Re-process Integration Inbox rows that failed fewer than 5 times."""
	for name in frappe.get_all("Integration Inbox", {"status": "Failed", "attempts": ("<", 5)}, pluck="name", limit=500):
		frappe.enqueue("forecourt.forecourt_integrations.inbox.process", name=name, queue="short", job_id=f"inbox::{name}", deduplicate=True)
```

---

## 8. Permissions (`forecourt/permissions`)

A User Permission on a Station Group grants every station below it. Frappe already applies a User Permission on Station to Station links; these hooks add the group expansion for list queries (`permission_query_conditions`) and single documents (`has_permission`). In v16 a `has_permission` hook must return `True` explicitly to allow.

### 8.1 `forecourt/permissions/station_group.py`

**Tasks:** FMS-I02, FMS-I05 · 111 lines

```python
# forecourt/permissions/station_group.py
"""Row-level access by station and station group (FMS-I02; design guide 14.2).

A User Permission on a Station Group gives access to every station below it. Frappe
already applies User Permissions on Station directly; these hooks add the group
expansion for DocTypes that link to Station (shifts, tanks, ledgers…).

Registered in hooks.py under permission_query_conditions (list views, reports,
get_list) and has_permission (single documents).
"""

from __future__ import annotations

import frappe

UNRESTRICTED_ROLES = {"System Manager", "Administrator", "Forecourt Administrator", "Forecourt Director"}


def allowed_stations(user: str | None = None) -> set[str] | None:
	"""Stations the user may see, or None for no restriction. Memoised per request."""
	user = user or frappe.session.user
	cache = frappe.local.__dict__.setdefault("fms_allowed_stations", {})
	if user in cache:
		return cache[user]
	result: set[str] | None
	if user == "Administrator" or UNRESTRICTED_ROLES & set(frappe.get_roles(user)):
		result = None
	else:
		perms = frappe.get_all("User Permission", {"user": user, "allow": ("in", ["Station", "Station Group"])}, ["allow", "for_value"])
		if not perms:
			result = None  # no station permissions at all: role permissions decide
		else:
			result = {p.for_value for p in perms if p.allow == "Station"}
			for p in perms:
				if p.allow == "Station Group":
					result |= stations_under(p.for_value)
	cache[user] = result
	return result


def stations_under(group: str) -> set[str]:
	lft, rgt = frappe.get_cached_value("Station Group", group, ["lft", "rgt"])
	groups = frappe.get_all("Station Group", {"lft": (">=", lft), "rgt": ("<=", rgt)}, pluck="name")
	return set(frappe.get_all("Station", {"station_group": ("in", groups)}, pluck="name"))


def query_conditions(doctype: str, user: str | None = None, field: str = "station") -> str:
	stations = allowed_stations(user)
	if stations is None:
		return ""
	if not stations:
		return "1=0"
	values = ", ".join(frappe.db.escape(s) for s in sorted(stations))
	return f"`tab{doctype}`.`{field}` in ({values})"


def has_station_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Only narrows access; role permissions still apply first.

	v16: a has_permission hook that returns None denies, so return True explicitly."""
	stations = allowed_stations(user)
	if stations is None:
		return True
	station = doc.name if doc.doctype == "Station" else doc.get("station")
	if not station:
		return True  # not station-bound (e.g. a draft before the station is chosen)
	return station in stations


# One function per DocType, because permission_query_conditions passes only `user`.
def _make(doctype: str, field: str = "station"):
	def fn(user: str | None = None, doctype: str = doctype) -> str:
		return query_conditions(doctype, user, "name" if doctype == "Station" else field)

	return fn


STATION_BOUND = (
	"Station",
	"Fuel Tank",
	"Dispenser",
	"Nozzle",
	"Forecourt Shift Template",
	"Fuel Price Change",
	"Meter Change",
	"Tank Dip",
	"Forecourt Shift",
	"Shift Correction",
	"Wetstock Ledger Entry",
	"Nozzle Ledger Entry",
	"Sales Ledger Entry",
	"Cashier Ledger Entry",
	"Payment Feed Entry",
	"Payment Import Batch",
)

station = _make("Station")
fuel_tank = _make("Fuel Tank")
dispenser = _make("Dispenser")
nozzle = _make("Nozzle")
forecourt_shift_template = _make("Forecourt Shift Template")
fuel_price_change = _make("Fuel Price Change")
meter_change = _make("Meter Change")
tank_dip = _make("Tank Dip")
forecourt_shift = _make("Forecourt Shift")
shift_correction = _make("Shift Correction")
wetstock_ledger_entry = _make("Wetstock Ledger Entry")
nozzle_ledger_entry = _make("Nozzle Ledger Entry")
sales_ledger_entry = _make("Sales Ledger Entry")
cashier_ledger_entry = _make("Cashier Ledger Entry")
payment_feed_entry = _make("Payment Feed Entry")
payment_import_batch = _make("Payment Import Batch")
```

---

## 9. Corrections (`forecourt/corrections`)

A closed shift is never edited in place. A Shift Correction, applied by a director who did not prepare it, does the precise fix in one transaction while `frappe.flags.fms_correction` opens the guards. Native-document and meter-reading corrections and whole-shift cancellation are written out; dip, cashier-count and reclassification corrections (FMS-G04) follow the meter pattern (recompute in memory, post the differences, supersede the ledger rows) and are left as the next step.

### 9.1 `forecourt/forecourt_shift/doctype/shift_correction/shift_correction.py`

**Tasks:** FMS-G01 · 62 lines

```python
# forecourt/forecourt_shift/doctype/shift_correction/shift_correction.py
# Copyright (c) 2026, the FMS authors. MIT licence.
"""Shift Correction controller (FMS-G01).

Workflow: Draft -> Pending Director Approval -> Approved -> Applied (submit) / Rejected.
Submitting is applying, and only a Forecourt Director may submit (role permission S).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.corrections import apply
from forecourt.errors import fms_throw


class ShiftCorrection(Document):
	def validate(self) -> None:
		shift = frappe.db.get_value("Forecourt Shift", self.forecourt_shift, ["docstatus", "station", "company"], as_dict=True)
		if not shift or shift.docstatus != 1:
			fms_throw("FMS-C501", _("Only closed shifts are corrected"))
		self.station, self.company = shift.station, shift.company
		self.fill_old_values()

	def fill_old_values(self) -> None:
		"""Show what is being replaced, so the director approves a visible before/after."""
		for it in self.items:
			if it.target_type == "Document" and it.target_doctype and it.field and "." not in it.field:
				it.old_value = str(frappe.db.get_value(it.target_doctype, it.target_name, it.field))
			elif it.target_row and it.field:
				row_doctype = {
					"Meter Reading": "Shift Meter Reading",
					"Tank Dip": "Shift Tank Dip",
					"Credit Sale": "Shift Credit Sale",
					"Collection": "Shift Collection",
					"Cash Count": "Shift Cash Count",
					"Resolution": "Shift Resolution",
				}[it.target_type]
				it.old_value = str(frappe.db.get_value(row_doctype, it.target_row, it.field))

	def before_submit(self) -> None:
		if "Forecourt Director" not in frappe.get_roles():
			fms_throw("FMS-C501", _("Only a Forecourt Director can apply a correction"))
		if self.owner == frappe.session.user:
			fms_throw("FMS-C501", _("The person who prepared the correction cannot apply it"))
		self.approved_by = frappe.session.user

	def on_submit(self) -> None:
		log = apply(self)
		self.db_set("applied_documents", "\n".join(log))
		if self.correction_type != "Whole-shift cancellation":
			frappe.flags.fms_correction = True
			try:
				shift = frappe.get_doc("Forecourt Shift", self.forecourt_shift)
				shift.db_set("status", "Corrected")
				shift.add_comment("Info", _("Corrected by {0}").format(self.name))
			finally:
				frappe.flags.fms_correction = False

	def before_cancel(self) -> None:
		fms_throw("FMS-C501", _("A correction cannot be cancelled; correct it with another correction"))
```

### 9.2 `forecourt/corrections/__init__.py`

**Tasks:** FMS-G01, FMS-G05 · 66 lines

`period_is_open` posts a correction at the original date when the period is open, otherwise today, as design guide 6.8 requires.

```python
# forecourt/corrections/__init__.py
"""Shift Correction apply step (FMS-G01 … FMS-G05; design guide 6.8).

Everything runs inside the correction's on_submit, so it is one transaction: either the
whole correction applies or nothing does. `frappe.flags.fms_correction` opens the
cancel guards for exactly that duration.
"""

from __future__ import annotations

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import getdate, today

from forecourt.errors import fms_throw


@contextmanager
def correction_mode():
	frappe.flags.fms_correction = True
	try:
		yield
	finally:
		frappe.flags.fms_correction = False


def period_is_open(company: str, on) -> bool:
	"""False when the date is frozen for the company or inside a closed Accounting Period."""
	on = getdate(on)
	frozen = frappe.get_cached_value("Company", company, "accounts_frozen_till_date")
	if frozen and on <= getdate(frozen):
		return False
	return not frappe.db.exists(
		"Accounting Period", {"company": company, "start_date": ("<=", on), "end_date": (">=", on), "disabled": 0}
	)


def apply(correction) -> list[str]:
	"""Returns the documents created, cancelled or amended, for `applied_documents`."""
	from . import meter, native

	handlers = {
		"Native document": native.apply,
		"Meter reading": meter.apply,
		"Whole-shift cancellation": cancel_whole_shift,
	}
	handler = handlers.get(correction.correction_type)
	if handler is None:
		# Dip, Cashier count and Reclassification follow the same pattern as meter.apply:
		# recompute in memory, post the differences, supersede the ledger rows (FMS-G04).
		frappe.throw(_("{0} corrections are not implemented yet").format(correction.correction_type))
	with correction_mode():
		return handler(correction)


def cancel_whole_shift(correction) -> list[str]:
	"""FMS-G05: wrong station or date. System Manager, latest closed shift, open period."""
	if "System Manager" not in frappe.get_roles():
		fms_throw("FMS-C501", _("Whole-shift cancellation needs the System Manager role"))
	shift = frappe.get_doc("Forecourt Shift", correction.forecourt_shift)
	if not period_is_open(shift.company, shift.shift_date):
		fms_throw("FMS-C501", _("The accounting period of {0} is closed").format(shift.shift_date))
	shift.flags.ignore_permissions = True
	shift.cancel()  # ForecourtShift.before_cancel checks "latest closed shift"
	return [f"Cancelled Forecourt Shift {shift.name}"]
```

### 9.3 `forecourt/corrections/native.py`

**Tasks:** FMS-G02 · 95 lines

Cancelling a paid invoice needs Accounts Settings → *Unlink Payment on Cancellation of Invoice*; the payments are re-linked to the amended invoice.

```python
# forecourt/corrections/native.py
"""Native document corrections (FMS-G02).

Cancel the one wrong ERPNext document and submit an amended copy with the corrected
field. Nothing else in the shift changes. Supported targets: Sales Invoice, Payment
Entry, Journal Entry, Delivery Note generated by the shift.

`field` is a header field ("customer") or a child path "items.2.item_code"
(table, 1-based idx, field).
"""

from __future__ import annotations

import frappe
from frappe import _

ALLOWED = {"Sales Invoice", "Payment Entry", "Journal Entry", "Delivery Note"}


def set_path(doc, path: str, value: str) -> None:
	parts = path.split(".")
	target = doc
	if len(parts) == 3:
		table, idx, path = parts
		target = next((r for r in doc.get(table) if r.idx == int(idx)), None)
		if target is None:
			frappe.throw(_("{0} has no row {1} in {2}").format(doc.name, idx, table))
	df = target.meta.get_field(path)
	if df is None:
		frappe.throw(_("{0} has no field {1}").format(target.doctype, path))
	target.set(path, frappe.utils.cast(df.fieldtype, value))


def apply(correction) -> list[str]:
	log = []
	for it in correction.items:
		if it.target_type != "Document":
			continue
		if it.target_doctype not in ALLOWED:
			frappe.throw(_("{0} cannot be corrected this way").format(it.target_doctype))
		old = frappe.get_doc(it.target_doctype, it.target_name)
		if old.get("fms_forecourt_shift") != correction.forecourt_shift:
			frappe.throw(_("{0} does not belong to shift {1}").format(old.name, correction.forecourt_shift))
		old.flags.ignore_permissions = True
		# A paid Sales Invoice can only be cancelled if Accounts Settings
		# "Unlink Payment on Cancellation of Invoice" is on; its payments are then
		# re-allocated to the amended invoice below.
		payments = linked_payments(old) if old.doctype == "Sales Invoice" else []
		old.cancel()
		new = frappe.copy_doc(old)
		new.amended_from = old.name
		set_path(new, it.field, it.new_value)
		new.flags.ignore_permissions = True
		new.insert()
		new.submit()
		reallocate(payments, new)
		log += [f"Cancelled {old.doctype} {old.name}", f"Amended as {new.name}"]
	return log


def linked_payments(invoice) -> list[tuple[str, float]]:
	return frappe.get_all(
		"Payment Entry Reference",
		{"reference_doctype": "Sales Invoice", "reference_name": invoice.name, "docstatus": 1},
		["parent", "allocated_amount"],
		as_list=True,
	)


def reallocate(payments, invoice) -> None:
	"""Re-link the unlinked receipts to the amended invoice with Payment Reconciliation's API."""
	if not payments:
		return
	from erpnext.accounts.utils import reconcile_against_document

	entries = []
	for pe, amount in payments:
		entries.append(
			frappe._dict(
				voucher_type="Payment Entry",
				voucher_no=pe,
				voucher_detail_no=None,
				against_voucher_type="Sales Invoice",
				against_voucher=invoice.name,
				account=invoice.debit_to,
				party_type="Customer",
				party=invoice.customer,
				dr_or_cr="credit_in_account_currency",
				unreconciled_amount=amount,
				unadjusted_amount=amount,
				allocated_amount=amount,
				difference_amount=0,
				is_advance=0,
			)
		)
	reconcile_against_document(entries)
```

### 9.4 `forecourt/corrections/meter.py`

**Tasks:** FMS-G03 · 176 lines

A wrong closing moves litres to the next shift. Both shifts are reposted as differences (an extra invoice or a credit note with its cash), and each cashier whose difference moves must be covered exactly by the correction's resolution lines.

```python
# forecourt/corrections/meter.py
"""Meter reading corrections (FMS-G03; design guide 6.8).

A wrong closing reading moves litres between this shift and the next one, whose
opening is the same number. The correction:

1. recomputes the shift in memory with the corrected value (the stored shift is not
   edited: FMS data is never changed in place);
2. posts the change in walk-in sales as an extra Sales Invoice or a Credit Note, with
   the cash receipt or refund that goes with it;
3. posts the correction's own resolution lines for the cashier difference it creates;
4. re-posts the tank Stock Reconciliation so book stock equals the dip again;
5. supersedes the shift's ledger rows and writes corrected ones;
6. does the same for the next shift if it is closed, or updates its opening if open;
7. updates the nozzle's last readings if no later shift exists.
"""

from __future__ import annotations

import copy

import frappe
from frappe import _
from frappe.utils import flt, today

from forecourt.calc.numbers import is_zero, money
from forecourt.forecourt_shift.shift.compute import recompute
from forecourt.posting.context import PostingContext
from forecourt.posting.journals import resolution_journal
from forecourt.posting.ledgers import supersede, write_ledgers
from forecourt.posting.payments import receipt
from forecourt.posting.sales import tank_warehouse, walk_in_fuel_lines
from forecourt.posting.stock import post_stock_reconciliation
from forecourt.utils.shifts import get_next_shift

from forecourt.errors import fms_throw

from . import period_is_open

METER_FIELDS = {f"{p}_{m}" for p in ("opening", "closing") for m in ("ecash", "evol", "mvol")}


def apply(correction) -> list[str]:
	shift = frappe.get_doc("Forecourt Shift", correction.forecourt_shift)
	changes = [(it.target_row, it.field, flt(it.new_value)) for it in correction.items if it.target_type == "Meter Reading"]
	for _row, field, _v in changes:
		if field not in METER_FIELDS or not field.startswith("closing_"):
			frappe.throw(_("Only closing meter readings can be corrected; the next opening follows"))

	pool = [r for r in correction.resolutions if r.resolution_for == "Cashier"]
	log = repost(shift, correction, changes, pool)

	nxt = get_next_shift(shift.name)
	if nxt:
		correction.db_set("next_shift", nxt)
		follow = frappe.get_doc("Forecourt Shift", nxt)
		opening_changes = next_openings(shift, follow, changes)
		if follow.docstatus == 0:
			for row_name, field, value in opening_changes:
				follow.getone("meter_readings", {"name": row_name}).set(field, value)
			follow.flags.ignore_permissions = True
			follow.save()
			log.append(f"Updated openings of open shift {nxt}")
		else:
			# Its cashier differences are new as well; they are resolved on the same correction
			# (resolution rows with cashier set apply to whichever shift that cashier worked).
			log += repost(follow, correction, opening_changes, pool)
	else:
		from forecourt.utils.stock import set_nozzle_last_readings

		for row_name, field, value in changes:
			row = shift.getone("meter_readings", {"name": row_name})
			set_nozzle_last_readings(row.nozzle, {field.removeprefix("closing_"): value}, shift.name)
	if pool:
		frappe.throw(_("Resolution lines for {0} match no cashier difference").format(", ".join(r.cashier for r in pool)))
	return log


def next_openings(shift, follow, changes) -> list[tuple[str, str, float]]:
	"""The first row per nozzle of the next shift opens at the corrected closing."""
	out = []
	for row_name, field, value in changes:
		nozzle = shift.getone("meter_readings", {"name": row_name}).nozzle
		rows = sorted((r for r in follow.meter_readings if r.nozzle == nozzle), key=lambda r: (r.segment_no or 1, r.idx))
		if rows:
			out.append((rows[0].name, field.replace("closing_", "opening_"), value))
	return out


def repost(shift, correction, changes, pool: list) -> list[str]:
	before = copy.deepcopy(shift)
	after = copy.deepcopy(shift)
	for row_name, field, value in changes:
		after.getone("meter_readings", {"name": row_name}).set(field, value)
	after.status = "Reconciled"
	recompute(after, strict=True)

	ctx = PostingContext.from_shift(after)
	ctx.correction = correction.name
	if not period_is_open(shift.company, ctx.posting_date):
		ctx.posting_date = frappe.utils.getdate(today())
	log = post_sales_difference(ctx, before, after, cashier_of(shift, changes))
	used = take_resolutions(before, after, pool)
	if used:
		resolution_journal(ctx, used, _("Correction {0}: cash differences").format(correction.name))
	post_stock_reconciliation(ctx)
	supersede(shift.name, correction.name)
	write_ledgers(ctx)
	return log + [f"{dt} {name}" for dt, name in ctx.created]


def cashier_of(shift, changes) -> str | None:
	return shift.getone("meter_readings", {"name": changes[0][0]}).cashier if changes else None


def take_resolutions(before, after, pool: list) -> list:
	"""Each cashier whose difference moved needs resolution lines that cancel the move
	exactly, under the same rules as closing (FMS-S105). Lines are taken from the pool."""
	from forecourt.forecourt_shift.shift.compute import RESOLUTION_SIGN

	old = {c.cashier: flt(c.difference) for c in before.cashiers}
	used = []
	for c in after.cashiers:
		moved = money(flt(c.difference) - old.get(c.cashier, 0))
		if is_zero(moved):
			continue
		mine = [r for r in pool if r.cashier == c.cashier]
		covered = money(sum(RESOLUTION_SIGN[r.action] * flt(r.amount) for r in mine))
		if not is_zero(moved + covered):
			fms_throw("FMS-S105", _("{0}: the correction changes the difference by {1}; resolution lines cover {2}").format(c.cashier, moved, -covered))
		used += mine
		for r in mine:
			pool.remove(r)
	return used


def post_sales_difference(ctx: PostingContext, before, after, cashier: str | None) -> list[str]:
	old, new = walk_in_fuel_lines(before), walk_in_fuel_lines(after)
	diff = {k: round(new.get(k, 0) - old.get(k, 0), 3) for k in set(old) | set(new)}
	more = {k: q for k, q in diff.items() if q > 0}
	less = {k: -q for k, q in diff.items() if q < 0}
	original = frappe.db.get_value(
		"Sales Invoice",
		{"fms_forecourt_shift": before.name, "customer": ctx.walk_in_customer, "docstatus": 1, "is_return": 0},
		"name",
	)
	cash_mop = frappe.db.get_value("Mode of Payment", {"type": "Cash", "enabled": 1}, "name")
	for lines, is_return in ((more, 0), (less, 1)):
		if not lines:
			continue
		si = frappe.new_doc("Sales Invoice")
		ctx.stamp(si)
		si.customer = ctx.walk_in_customer
		si.update_stock = 1
		si.ignore_pricing_rule = 1
		si.disable_rounded_total = 1
		if is_return:
			si.is_return = 1
			si.return_against = original
		sign = -1 if is_return else 1
		for (item, tank, price), qty in lines.items():
			si.append("items", {"item_code": item, "qty": sign * qty, "rate": price, "warehouse": tank_warehouse(tank)})
		ctx.submit(si)
		amount = money(abs(si.grand_total))
		receipt(
			ctx,
			party=ctx.walk_in_customer,
			amount=amount,
			paid_to=ctx.till_account,
			mode_of_payment=cash_mop,
			cashier=cashier,
			reference_no=f"{ctx.correction}-{'REFUND' if is_return else 'CASH'}",
			reference_date=ctx.posting_date,
			allocations=[(si.name, sign * amount)],
			payment_type="Pay" if is_return else "Receive",
		)
	return []
```

---

## 10. Integrations: statement import

Phase 1 brings mobile money and card transactions in from the provider's export file, so managers do not type references. The mapping lives on the Payment Provider. The module is named `statement_import.py` because `import` is a Python keyword; the catalogue's method path changes accordingly.

### 10.1 `forecourt/forecourt_integrations/statement_import.py`

**Tasks:** FMS-J01, FMS-J02 · 154 lines

```python
# forecourt/forecourt_integrations/statement_import.py
"""Payment Import Batch: Phase 1 provider statement import (FMS-J01).

The module is not called `import.py` (a Python keyword cannot be imported by path).

Each Payment Provider stores an `import_mapping` (JSON) that maps the provider's
export columns to ours:

    {
      "reference": "Receipt No.",
      "transaction_time": "Completion Time",
      "amount": "Paid In",
      "payer": "Other Party Info",
      "till_or_terminal": "Till",
      "time_format": "%d-%m-%Y %H:%M:%S",   # optional; otherwise parsed leniently
      "skip_rows": 6,                       # optional header lines before the table
      "amount_negative_is_refund": true     # optional
    }

Rows go to the target shift as Shift Collection rows (cashier from the terminal's
default cashier, else left blank for the manager), or to Payment Feed Entry when the
batch has no shift. Duplicates (provider + reference already anywhere) are skipped.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import flt, get_datetime

from forecourt.errors import fms_throw

REQUIRED = ("reference", "transaction_time", "amount")


def parse_rows(content: bytes, filename: str, mapping: dict) -> list[dict]:
	"""File -> list of {our field: raw value}. Pure apart from the Excel reader."""
	skip = int(mapping.get("skip_rows") or 0)
	if filename.lower().endswith((".xlsx", ".xls")):
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		table = read_xlsx_file_from_attached_file(fcontent=content)
	else:
		text = content.decode("utf-8-sig", errors="replace")
		table = list(csv.reader(io.StringIO(text)))
	table = [r for r in table[skip:] if any(str(c).strip() for c in r)]
	if not table:
		return []
	header = [str(h).strip() for h in table[0]]
	cols = {}
	for ours, theirs in mapping.items():
		if ours in ("time_format", "skip_rows", "amount_negative_is_refund"):
			continue
		if theirs not in header:
			fms_throw("FMS-I401", _("Column '{0}' (for {1}) is not in the file").format(theirs, ours))
		cols[ours] = header.index(theirs)
	missing = [f for f in REQUIRED if f not in cols]
	if missing:
		fms_throw("FMS-I401", _("The mapping has no column for {0}").format(", ".join(missing)))
	return [{ours: (row[i] if i < len(row) else None) for ours, i in cols.items()} for row in table[1:]]


def clean_amount(raw) -> float:
	"""'KES 1,250.00' -> 1250.0; '(500)' -> -500."""
	s = str(raw or "").strip()
	neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
	s = re.sub(r"[^0-9.]", "", s)
	return -flt(s) if neg else flt(s)


def clean_time(raw, fmt: str | None) -> datetime:
	if isinstance(raw, datetime):
		return raw
	return datetime.strptime(str(raw).strip(), fmt) if fmt else get_datetime(str(raw).strip())


@frappe.whitelist()
def run(batch: str) -> dict:
	b = frappe.get_doc("Payment Import Batch", batch)
	b.check_permission("write")
	provider = frappe.get_cached_doc("Payment Provider", b.provider)
	mapping = frappe.parse_json(provider.import_mapping or "{}")
	file_doc = frappe.get_doc("File", {"file_url": b.file})
	rows = parse_rows(file_doc.get_content(), file_doc.file_name, mapping)

	shift = frappe.get_doc("Forecourt Shift", b.forecourt_shift) if b.forecourt_shift else None
	if shift and shift.docstatus != 0:
		fms_throw("FMS-I401", _("Shift {0} is closed").format(shift.name))
	terminals = {
		t.till_or_terminal: t.default_cashier
		for t in frappe.get_cached_doc("Station", b.station).payment_terminals
		if t.provider == b.provider and t.active
	}
	collection_type = "Card" if provider.provider_type == "Card" else "Mobile Money"
	log, created, dup, rejected = [], 0, 0, 0

	for n, raw in enumerate(rows, start=1 + int(mapping.get("skip_rows") or 0) + 1):
		try:
			ref = str(raw["reference"] or "").strip()
			amount = clean_amount(raw["amount"])
			at = clean_time(raw["transaction_time"], mapping.get("time_format"))
			if not ref or amount <= 0:
				raise ValueError(_("no reference or non-positive amount"))
			if provider.reference_pattern and not re.fullmatch(provider.reference_pattern, ref):
				raise ValueError(_("reference {0} does not match the provider pattern").format(ref))
		except Exception as e:
			rejected += 1
			log.append(f"Row {n}: {e}")
			continue
		if is_duplicate(b.provider, ref, shift):
			dup += 1
			continue
		till = str(raw.get("till_or_terminal") or "").strip()
		values = {
			"provider": b.provider,
			"till_or_terminal": till,
			"reference": ref,
			"transaction_time": at,
			"amount": amount,
			"payer": raw.get("payer"),
		}
		if shift:
			if not (get_datetime(shift.shift_start) <= at < get_datetime(shift.shift_end)):
				rejected += 1
				log.append(f"Row {n}: {ref} at {at} is outside the shift window")
				continue
			shift.append(
				"collections",
				{**values, "collection_type": collection_type, "cashier": terminals.get(till), "import_batch": b.name,
				 "mode_of_payment": provider.mode_of_payment},
			)
		else:
			frappe.get_doc(
				{"doctype": "Payment Feed Entry", **values, "station": b.station, "cashier": terminals.get(till), "status": "Unmatched"}
			).insert(ignore_permissions=True)
		created += 1

	if shift:
		shift.save()  # recompute runs; rows without a cashier are listed by gate FMS-S111
	b.db_set({"rows_read": len(rows), "rows_created": created, "rows_duplicate": dup, "rows_rejected": rejected, "log": "\n".join(log)})
	return {"read": len(rows), "created": created, "duplicate": dup, "rejected": rejected}


def is_duplicate(provider: str, reference: str, shift) -> bool:
	if shift and any(c.provider == provider and (c.reference or "").strip() == reference for c in shift.collections):
		return True
	return bool(
		frappe.db.exists("Shift Collection", {"provider": provider, "reference": reference})
		or frappe.db.exists("Payment Feed Entry", {"provider": provider, "reference": reference})
	)
```

---

## 11. Tests: factories and the shift scenario

`factories.py` builds a small station on ERPNext's `_Test Company`. `test_shift_close.py` runs the design guide's worked example (section 8.2) end to end and checks what an accountant would: invoice totals, one Payment Entry per reference, the till balance, the cashier receivable, book stock equal to the dip, and ledgers that add up. Run with `bench --site test.localhost run-tests --app forecourt`.

### 11.1 `forecourt/tests/factories.py`

**Tasks:** FMS-B07 · 195 lines

```python
# forecourt/tests/factories.py
"""Test factories (FMS-B07). One function per record, sensible defaults, idempotent.

Integration tests build a tiny station with these: one tank, one dispenser, one or
two nozzles, one template, one or two cashiers. Every factory returns the document
and reuses an existing one with the same key, so tests can call them freely.
Uses ERPNext's standard test company ("_Test Company", KES not required: the
company currency is used everywhere).
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, today

COMPANY = "_Test Company"


def _get_or_make(doctype: str, key: dict, values: dict):
	name = frappe.db.get_value(doctype, key, "name")
	if name:
		return frappe.get_doc(doctype, name)
	doc = frappe.get_doc({"doctype": doctype, **key, **values})
	doc.insert(ignore_permissions=True)
	return doc


def make_account(name: str, parent: str, account_type: str = "", root_type: str | None = None):
	abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
	return _get_or_make(
		"Account",
		{"account_name": name, "company": COMPANY},
		{"parent_account": f"{parent} - {abbr}", "account_type": account_type, **({"root_type": root_type} if root_type else {})},
	).name


def make_company_settings():
	"""Forecourt Company Settings with dedicated test accounts."""
	if frappe.db.exists("Forecourt Company Settings", COMPANY):
		return frappe.get_doc("Forecourt Company Settings", COMPANY)
	return frappe.get_doc(
		{
			"doctype": "Forecourt Company Settings",
			"company": COMPANY,
			"staff_shortage_receivable_account": make_account("FMS Staff Shortage", "Accounts Receivable", "Receivable"),
			"cash_short_account": make_account("FMS Cash Short", "Indirect Expenses"),
			"cash_over_account": make_account("FMS Cash Over", "Indirect Income"),
			"fuel_stock_variance_account": make_account("FMS Fuel Variance", "Stock Expenses"),
			"delivery_shortage_claims_account": make_account("FMS Delivery Claims", "Current Assets"),
			"voucher_clearing_account": make_account("FMS Voucher Clearing", "Current Assets"),
			"tank_tolerance_pct": 0.5,
			"tank_tolerance_l": 20,
			"approval_multiplier": 2,
			"small_difference_pct": 0.1,
			"post_tank_variance": "Every shift with dips",
			"sales_posting_mode": "Shift summary",
			"credit_invoicing": "Per customer per shift",
		}
	).insert(ignore_permissions=True)


def make_fuel_item(code: str = "_FMS PMS", rate: float = 180.0):
	item = _get_or_make(
		"Item",
		{"item_code": code},
		{"item_name": code, "item_group": "Products", "stock_uom": "Litre", "is_stock_item": 1, "fms_is_fuel": 1, "valuation_rate": 150},
	)
	return item


def make_station(code: str = "KE-TST-ST1", **overrides):
	make_company_settings()
	abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
	group = _get_or_make("Warehouse", {"warehouse_name": f"FMS {code}", "company": COMPANY}, {"is_group": 1})
	till = make_account(f"Till {code}", "Cash In Hand", "Cash")
	safe = make_account(f"Safe {code}", "Cash In Hand", "Cash")
	values = {
		"station_name": f"Test {code}",
		"company": COMPANY,
		"station_group": "All Station Groups",
		"country": frappe.get_cached_value("Company", COMPANY, "country"),
		"ownership_type": "Company-owned",
		"timezone": frappe.get_system_settings("time_zone") or "Africa/Nairobi",
		"warehouse_group": group.name,
		"price_list": "Standard Selling",
		"cost_center": f"Main - {abbr}",
		"safe_account": safe,
		"till_accounts": [{"currency": frappe.get_cached_value("Company", COMPANY, "default_currency"), "account": till}],
		"dip_entry_mode": "Litres entered directly",
		**overrides,
	}
	return _get_or_make("Station", {"station_code": code}, values)


def make_tank(station, item, code: str = "T1", capacity: float = 30000, opening_l: float = 0):
	tank = _get_or_make(
		"Fuel Tank",
		{"station": station.name, "tank_code": code},
		{"item": item.name, "capacity_l": capacity, "tank_label": f"{code} {item.name}"},
	)
	if opening_l and not frappe.db.exists("Stock Ledger Entry", {"warehouse": tank.warehouse, "is_cancelled": 0}):
		receive_stock(tank, opening_l, posting_date=add_days(today(), -2))
	return tank


def receive_stock(tank, qty: float, rate: float = 150, posting_date=None):
	"""Opening stock via a Material Receipt (tests only; real deliveries are GRNs)."""
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": COMPANY,
			"posting_date": posting_date or today(),
			"set_posting_time": 1,
			"posting_time": "00:00:00",
			"items": [{"item_code": tank.item, "t_warehouse": tank.warehouse, "qty": qty, "basic_rate": rate}],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def make_nozzle(station, tank, dispenser_code: str = "D01", nozzle_no: int = 1, last_ecash: float = 0):
	disp = _get_or_make("Dispenser", {"station": station.name, "dispenser_code": dispenser_code}, {"island": "Island 1"})
	nozzle = _get_or_make("Nozzle", {"dispenser": disp.name, "nozzle_no": nozzle_no}, {"tank": tank.name})
	if last_ecash:
		frappe.db.set_value("Nozzle", nozzle.name, "last_ecash", last_ecash)
	return nozzle


def make_cashier(first_name: str = "Amina"):
	return _get_or_make(
		"Employee",
		{"first_name": f"_FMS {first_name}", "company": COMPANY},
		{"gender": "Female", "date_of_birth": "1990-01-01", "date_of_joining": "2020-01-01", "fms_is_forecourt_cashier": 1},
	)


def make_template(station, nozzles, cashier, name: str = "Day", start="06:00:00", end="18:00:00"):
	return _get_or_make(
		"Forecourt Shift Template",
		{"station": station.name, "template_name": name},
		{
			"start_time": start,
			"end_time": end,
			"sequence": 1,
			"dips_required": 1,
			"cashiers": [{"cashier": cashier.name, "float_amount": 5000}],
			"nozzle_assignments": [{"nozzle": n.name, "cashier": cashier.name} for n in nozzles],
		},
	)


def set_price(station, item, price: float, at):
	fpc = frappe.get_doc(
		{"doctype": "Fuel Price Change", "station": station.name, "effective_at": at, "items": [{"item": item.name, "price": price}]}
	)
	fpc.insert(ignore_permissions=True)
	fpc.submit()
	return fpc


def make_shift(station, template, shift_date=None):
	"""A draft shift. before_insert pre-fills rows from the template and last readings."""
	return frappe.get_doc(
		{"doctype": "Forecourt Shift", "station": station.name, "shift_template": template.name, "shift_date": getdate(shift_date or add_days(today(), -1))}
	).insert(ignore_permissions=True)


def make_customer(name: str = "_FMS Coast Haulage", credit_limit: float = 0):
	c = _get_or_make("Customer", {"customer_name": name}, {"customer_group": "Commercial", "territory": "All Territories"})
	if credit_limit and not c.credit_limits:
		c.append("credit_limits", {"company": COMPANY, "credit_limit": credit_limit})
		c.save(ignore_permissions=True)
	return c


def make_provider(name: str = "_FMS M-Pesa", provider_type: str = "Mobile Money"):
	mop = _get_or_make("Mode of Payment", {"mode_of_payment": name}, {"type": "Bank"})
	if not mop.accounts:
		mop.append("accounts", {"company": COMPANY, "default_account": make_account(f"{name} Clearing", "Bank Accounts", "Bank")})
		mop.save(ignore_permissions=True)
	return _get_or_make("Payment Provider", {"provider_name": name}, {"provider_type": provider_type, "mode_of_payment": mop.name})


def make_expense_type(name: str = "Cleaning", max_per_line: float = 10_000):
	return _get_or_make(
		"Expense Type",
		{"expense_type": name},
		{
			"max_per_line": max_per_line,
			"receipt_required": 0,
			"accounts": [{"company": COMPANY, "expense_account": make_account(f"FMS {name}", "Indirect Expenses")}],
		},
	)
```

### 11.2 `forecourt/tests/test_shift_close.py`

**Tasks:** FMS-F18, FMS-K01 · 150 lines

```python
# forecourt/tests/test_shift_close.py
"""Shift close end to end (FMS-F18): the worked example of design guide 8.2.

One cashier, two nozzles (PMS 180, AGO 170), a credit slip, mobile money, an expense
and a 500 shortage charged to the cashier. Asserts what an accountant would check:
invoice totals, one Payment Entry per transaction, the till balance, the receivable
from the cashier, book stock equal to the dip, and ledgers that add up.
"""

from __future__ import annotations

import frappe
from frappe.tests.classes import IntegrationTestCase
from frappe.utils import add_to_date, flt, get_datetime

from forecourt.tests import factories as f

PMS_L, AGO_L = 1200, 900


def gl_balance(account: str, shift: str, party: str | None = None) -> float:
	filters = {"account": account, "is_cancelled": 0, "voucher_no": ("in", generated(shift))}
	if party:
		filters["party"] = party
	rows = frappe.get_all("GL Entry", filters, ["sum(debit) - sum(credit) as bal"])
	return flt(rows[0].bal)


def generated(shift: str) -> list[str]:
	names = []
	for dt in ("Sales Invoice", "Payment Entry", "Journal Entry", "Stock Reconciliation"):
		names += frappe.get_all(dt, {"fms_forecourt_shift": shift, "docstatus": 1}, pluck="name")
	return names


class TestShiftClose(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.station = f.make_station("KE-TST-WL")
		pms, ago = f.make_fuel_item("_FMS PMS"), f.make_fuel_item("_FMS AGO")
		cls.t1 = f.make_tank(cls.station, pms, "T1", opening_l=20000)
		cls.t2 = f.make_tank(cls.station, ago, "T2", opening_l=15000)
		cls.n1 = f.make_nozzle(cls.station, cls.t1, nozzle_no=1, last_ecash=1_000_000)
		cls.n2 = f.make_nozzle(cls.station, cls.t2, nozzle_no=2, last_ecash=2_000_000)
		cls.amina = f.make_cashier("Amina")
		cls.template = f.make_template(cls.station, [cls.n1, cls.n2], cls.amina)
		cls.customer = f.make_customer()
		cls.mpesa = f.make_provider()
		f.make_expense_type("Cleaning")
		yesterday = add_to_date(None, days=-3)
		f.set_price(cls.station, pms, 180, yesterday)
		f.set_price(cls.station, ago, 170, yesterday)

	def build_shift(self):
		s = f.make_shift(self.station, self.template)
		row = {r.nozzle: r for r in s.meter_readings}
		row[self.n1.name].closing_ecash = 1_000_000 + PMS_L * 180
		row[self.n2.name].closing_ecash = 2_000_000 + AGO_L * 170
		at = add_to_date(get_datetime(s.shift_start), hours=2)
		s.append("credit_sales", {"cashier": self.amina.name, "customer": self.customer.name, "item": "_FMS AGO",
			"qty": 200, "slip_no": "CS-0001", "sold_at": at})
		for i in range(3):
			s.append("collections", {"cashier": self.amina.name, "collection_type": "Mobile Money", "provider": self.mpesa.name,
				"reference": f"QK{i:08d}", "transaction_time": at, "amount": 60_000})
		s.append("collections", {"cashier": self.amina.name, "collection_type": "Expense", "expense_type": "Cleaning", "amount": 1_500})
		# Expected 369,000 (no lubricants here). Accounted: credit 34,000 + mobile 180,000 + expense 1,500
		# + cash. Cash for a 500 shortage: 369,000 - 500 - 215,500 = 153,000, counted with the 5,000 float.
		currency = frappe.get_cached_value("Company", f.COMPANY, "default_currency")
		s.append("cash_counts", {"cashier": self.amina.name, "currency": currency, "amount": 158_000})
		s.save()
		# Expected tank stock needs the sales first; dip exactly at expected (no variance), save again.
		for t in s.tank_dips:
			t.dip_l = t.expected_l
		s.save()
		return s

	def test_cashier_balance_before_close(self):
		s = self.build_shift()
		c = s.cashiers[0]
		self.assertEqual(flt(c.expected), 369_000)
		self.assertEqual(flt(c.difference), -500)
		self.assertEqual(s.status, "Counting")  # unresolved difference

	def test_close_posts_everything(self):
		s = self.build_shift()
		s.append("resolutions", {"resolution_for": "Cashier", "cashier": self.amina.name, "action": "Charge to cashier",
			"amount": 500, "reason": "Counting error", "note": "test"})
		s.save()
		self.assertEqual(s.status, "Reconciled")
		s.submit()
		s.reload()
		self.assertEqual(s.status, "Closed")

		# 1. invoices: credit 34,000; walk-in 216,000 + (153,000 - 34,000) = 335,000
		credit = frappe.get_all("Sales Invoice", {"fms_forecourt_shift": s.name, "customer": self.customer.name}, pluck="grand_total")
		self.assertEqual([flt(x) for x in credit], [34_000])
		walk_in = frappe.get_value("Sales Invoice", {"fms_forecourt_shift": s.name, "customer": self.station.walk_in_customer},
			["grand_total", "outstanding_amount"], as_dict=True)
		self.assertEqual(flt(walk_in.grand_total), 335_000)
		self.assertEqual(flt(walk_in.outstanding_amount), 0)

		# 2. one Payment Entry per mobile money reference, plus one cash entry
		refs = frappe.get_all("Payment Entry", {"fms_forecourt_shift": s.name, "mode_of_payment": self.mpesa.mode_of_payment},
			pluck="reference_no")
		self.assertEqual(sorted(refs), ["QK00000000", "QK00000001", "QK00000002"])

		# 3. the till holds what was counted (net of float); Amina owes 500
		till = self.station.till_accounts[0].account
		self.assertEqual(gl_balance(till, s.name), 153_000)
		receivable = f.make_company_settings().staff_shortage_receivable_account
		self.assertEqual(gl_balance(receivable, s.name, party=self.amina.name), 500)

		# 4. book stock equals the dip
		from forecourt.utils.stock import tank_book_stock

		for t in s.tank_dips:
			self.assertAlmostEqual(tank_book_stock(t.tank, s.shift_end), flt(t.dip_l), places=3)

		# 5. ledgers add up to the shift
		sales = frappe.get_all("Sales Ledger Entry", {"forecourt_shift": s.name}, ["payment_type", "sum(amount) as amount"],
			group_by="payment_type")
		by_type = {r.payment_type: flt(r.amount) for r in sales}
		self.assertEqual(sum(by_type.values()), 369_000)
		self.assertEqual(by_type["Credit"], 34_000)
		self.assertEqual(by_type["Mobile Money"], 180_000)
		self.assertEqual(by_type.get("Shortage"), 500)
		self.assertEqual(frappe.db.count("Nozzle Ledger Entry", {"forecourt_shift": s.name}), 2)

		# 6. nozzles remember the closing
		self.assertEqual(flt(frappe.db.get_value("Nozzle", self.n1.name, "last_ecash")), 1_000_000 + PMS_L * 180)

	def test_generated_documents_cannot_be_cancelled(self):
		s = self.build_shift()
		s.append("resolutions", {"resolution_for": "Cashier", "cashier": self.amina.name, "action": "Write off",
			"amount": 500, "reason": "Counting error", "note": "test"})
		s.save()
		s.submit()
		pe = frappe.get_doc("Payment Entry", {"fms_forecourt_shift": s.name, "reference_no": "QK00000000"})
		from forecourt.errors import FMSValidationError

		with self.assertRaises(FMSValidationError):
			pe.cancel()

	def test_gates_list_every_problem(self):
		s = f.make_shift(self.station, self.template)
		from forecourt.forecourt_shift.shift.gates import collect_problems

		codes = {p.code for p in collect_problems(s)}
		self.assertIn("FMS-S101", codes)  # no closing readings
		self.assertIn("FMS-S103", codes)  # no dips
```

---

## 12. Verification status and what to check on a bench

| Part | Status |
|---|---|
| `forecourt/calc/*` | Run: 30 unit tests pass, including the guide's examples and 300 random attribution cases |
| Everything else | Compiles; written against Frappe/ERPNext v16 but not yet executed on a bench |

Check these first when the app is installed (FMS-B09, FMS-K04). They are the calls most likely to differ between ERPNext releases:

| Call | Where | What to verify |
|---|---|---|
| `erpnext.stock.utils.get_stock_balance(item, warehouse, date, time, with_valuation_rate=True)` | `utils/stock.py` | Returns `(qty, rate)` (newer releases add a third value for serial/batch) |
| `frappe.db.bulk_insert(doctype, fields, values)` | `posting/ledgers.py` | Signature and `chunk_size` default |
| Payment Entry built field by field | `posting/payments.py` | `validate()` fills account currencies and exchange rates; references with negative `allocated_amount` against a credit note |
| `erpnext.accounts.utils.reconcile_against_document` | `corrections/native.py` | Entry keys expected by the installed version |
| `Company.accounts_frozen_till_date` | `corrections/__init__.py` | Field name (older releases keep it in Accounts Settings as `acc_frozen_upto`) |
| `get_credit_limit`, `get_customer_outstanding` | `shift/compute.py` | Import path and arguments |
| `Stock Ledger Entry.posting_datetime` | `shift/sources.py` | Column exists (v15+) |
| `frappe.utils.xlsxutils.read_xlsx_file_from_attached_file(fcontent=…)` | `statement_import.py` | Keyword name |
| `has_permission` returning `True` | `permissions/station_group.py` | v16 behaviour for hooks that return `None` |
| Accounting dimension field `station` on Journal Entry Account | `posting/journals.py` | Dimension is enabled for that child table |

**Known limits, by design for now**

- Foreign-currency cash is counted at its base amount into the company-currency till; a separate foreign-currency till needs a currency-exchange journal (later task).
- Dip, cashier-count and reclassification corrections (FMS-G04) are not written; they follow `corrections/meter.py`.
- `after_install` (accounting dimension, root Station Group, fixtures check) is described in `hooks.py` but not shown.

**Catalogue changes this code relies on** (applied to `FMS_DocType_Catalogue.md` with this document):

- Shift Meter Reading `drift_breach`; Shift Tank Dip `needs_approval`; Shift Credit Sale `over_limit` and `delivery_note`.
- Stock Entry and Purchase Receipt use the accounting dimension field `station`, not a custom `fms_station`.
- Payment Import Batch method path `forecourt.forecourt_integrations.statement_import.run`.
- Error codes FMS-P301, FMS-I401, FMS-I402.
