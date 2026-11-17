frappe.query_reports["Meter Change Register"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		{
			fieldname: "nozzle",
			label: __("Nozzle"),
			fieldtype: "Link",
			options: "Nozzle",
			get_query: () => forecourt.report_filters.nozzle_query(),
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
