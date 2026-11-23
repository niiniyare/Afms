frappe.query_reports["Inventory Value"] = {
	filters: [...forecourt.report_filters.scope(), ...forecourt.report_filters.as_of()],
};
