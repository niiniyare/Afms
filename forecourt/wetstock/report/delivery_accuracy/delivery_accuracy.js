frappe.query_reports["Delivery Accuracy"] = {
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
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
