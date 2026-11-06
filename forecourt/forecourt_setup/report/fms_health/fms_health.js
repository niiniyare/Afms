frappe.query_reports["FMS Health"] = {
	filters: [
		{
			fieldname: "station",
			label: __("Station"),
			fieldtype: "Link",
			options: "Station",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_default("company"),
		},
	],
};
