/* Tank Stock Position is an "as of" snapshot — single date, no range. */
frappe.query_reports["Tank Stock Position"] = {
	filters: [
		...forecourt.report_filters.scope(),
		forecourt.report_filters.as_of(),
		forecourt.report_filters.tank({ fieldname: "tank" }),
	],
};
