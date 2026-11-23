frappe.query_reports["Approvals Log"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("company"),
			reqd: 1,
		},
		...forecourt.report_filters.scope_stations(),
		...forecourt.report_filters.period(),
		{
			fieldname: "document_type",
			label: __("Document Type"),
			fieldtype: "Select",
			options: "\nForecourt Shift\nFuel Price Change\nShift Correction",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
