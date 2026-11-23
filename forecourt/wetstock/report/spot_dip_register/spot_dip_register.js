frappe.query_reports["Spot Dip Register"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 30 days" }),
		...forecourt.report_filters.tank(),
		{
			fieldname: "purpose",
			label: __("Purpose"),
			fieldtype: "Select",
			options: "\nSpot Check\nInvestigation\nMonthly Count\nOther",
		},
		{
			fieldname: "dipped_by",
			label: __("Dipped By"),
			fieldtype: "Link",
			options: "Employee",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
