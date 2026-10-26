import frappe


def execute() -> None:
	"""Rename Forecourt Settings meter field keys in tabSingles.

	C02b renamed five fields and updated sales_basis option values.
	This patch runs pre_model_sync so the old key names are still present.
	"""
	renames = [
		("record_ecash", "record_elec_cash"),
		("record_evol", "record_elec_meter"),
		("record_mvol", "record_man_meter"),
		("allow_time_estimated_segments", "allow_estimated_segments"),
		("require_meter_photo", "require_meter_reading_photo"),
	]
	for old, new in renames:
		frappe.db.sql(
			"UPDATE `tabSingles` SET field = %s WHERE doctype = %s AND field = %s",
			(new, "Forecourt Settings", old),
		)

	basis_renames = [
		("E-cash", "Elec Cash"),
		("E-vol", "Elec Meter"),
		("M-vol", "Man Meter"),
	]
	for old_val, new_val in basis_renames:
		frappe.db.sql(
			"UPDATE `tabSingles` SET value = %s WHERE doctype = %s AND field = %s AND value = %s",
			(new_val, "Forecourt Settings", "sales_basis", old_val),
		)
