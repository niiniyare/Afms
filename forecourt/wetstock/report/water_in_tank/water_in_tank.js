frappe.query_reports["Water in Tank"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		{
			fieldname: "tank",
			label: __("Tank"),
			fieldtype: "Link",
			options: "Fuel Tank",
			get_query: () => forecourt.report_filters.tank_query(),
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
