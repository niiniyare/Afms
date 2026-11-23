"""Rename meter field keys in tabSingles before schema sync removes old names.

Fields renamed:
  record_ecash                  → record_elec_cash
  record_evol                   → record_elec_meter
  record_mvol                   → record_man_meter
  allow_time_estimated_segments → allow_estimated_segments
  require_meter_photo           → require_meter_reading_photo

sales_basis option values updated:
  E-cash → Elec Cash
  E-vol  → Elec Meter
  M-vol  → Man Meter
"""

import frappe

_DOC = "Forecourt Settings"

_FIELD_RENAMES = [
	("record_ecash", "record_elec_cash"),
	("record_evol", "record_elec_meter"),
	("record_mvol", "record_man_meter"),
	("allow_time_estimated_segments", "allow_estimated_segments"),
	("require_meter_photo", "require_meter_reading_photo"),
]

_SALES_BASIS_MAP = {
	"E-cash": "Elec Cash",
	"E-vol": "Elec Meter",
	"M-vol": "Man Meter",
}


def execute() -> None:
	for old_field, new_field in _FIELD_RENAMES:
		frappe.db.sql(
			"UPDATE `tabSingles` SET `field` = %s WHERE `doctype` = %s AND `field` = %s",
			(new_field, _DOC, old_field),
		)

	rows = frappe.db.sql(
		"SELECT `value` FROM `tabSingles` WHERE `doctype` = %s AND `field` = %s",
		(_DOC, "sales_basis"),
		as_dict=True,
	)
	if rows and rows[0].value in _SALES_BASIS_MAP:
		frappe.db.sql(
			"UPDATE `tabSingles` SET `value` = %s WHERE `doctype` = %s AND `field` = %s",
			(_SALES_BASIS_MAP[rows[0].value], _DOC, "sales_basis"),
		)
