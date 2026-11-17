/* Open Items shows current state — no date range filter needed. */
frappe.query_reports["Open Items"] = {
	filters: [...forecourt.report_filters.scope()],
};
