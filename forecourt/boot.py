import frappe


def get_bootinfo(bootinfo: object) -> None:
	"""Extend boot with the current user's default station."""
	station: str = (
		frappe.db.get_value(
			"Employee",
			{"user_id": frappe.session.user},
			"fms_default_station",
		)
		or ""
	)
	bootinfo.fms_user_station = station
