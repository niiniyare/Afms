frappe.query_reports["Cash Position by Station"] = {
	filters: [...forecourt.report_filters.scope(), forecourt.report_filters.as_of()],
};
