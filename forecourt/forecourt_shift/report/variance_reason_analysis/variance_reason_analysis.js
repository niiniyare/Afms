frappe.query_reports["Variance Reason Analysis"] = {
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
			fieldname: "resolution_for",
			label: __("Resolution For"),
			fieldtype: "Select",
			options: "\nCashier\nTank\nDrift\nCredit\nDelivery",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
