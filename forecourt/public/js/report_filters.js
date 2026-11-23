/**
 * FMS standard report filter builders — FMS-R02.
 *
 * Usage in a report's .js file:
 *
 *   frappe.query_reports["My Report"] = {
 *     filters: [
 *       ...forecourt.report_filters.scope(),
 *       ...forecourt.report_filters.period(),
 *       ...forecourt.report_filters.product(),
 *     ],
 *     onload(report) {
 *       forecourt.report_filters.setup_period_handler(report);
 *     },
 *   };
 */

frappe.provide("forecourt.report_filters");

Object.assign(forecourt.report_filters, {
	// ------------------------------------------------------------------
	// Scope filters: Company → Station Group → Station (always in this order)
	// ------------------------------------------------------------------

	scope(opts = {}) {
		return [
			{
				fieldname: "company",
				label: __("Company"),
				fieldtype: "Link",
				options: "Company",
				default: frappe.defaults.get_default("company"),
				...(opts.company || {}),
			},
			{
				fieldname: "station_group",
				label: __("Station Group"),
				fieldtype: "Link",
				options: "Station Group",
				...(opts.station_group || {}),
			},
			{
				fieldname: "station",
				label: __("Station"),
				fieldtype: "Link",
				options: "Station",
				get_query() {
					const company = frappe.query_report.get_filter_value("company");
					const sg = frappe.query_report.get_filter_value("station_group");
					const f = {};
					if (company) f.company = company;
					if (sg) f.station_group = sg;
					return { filters: f };
				},
				...(opts.station || {}),
			},
		];
	},

	// ------------------------------------------------------------------
	// Period filters: period select + from_date + to_date
	// ------------------------------------------------------------------

	period(opts = {}) {
		const today = frappe.datetime.get_today();
		return [
			{
				fieldname: "period",
				label: __("Period"),
				fieldtype: "Select",
				options: [
					"",
					__("Today"),
					__("Yesterday"),
					__("This Week"),
					__("Last Week"),
					__("Month to Date"),
					__("Last Month"),
					__("Quarter to Date"),
					__("Last Quarter"),
					__("Year to Date"),
					__("Last 7 Days"),
					__("Last 30 Days"),
					__("Last 90 Days"),
					__("Custom"),
				].join("\n"),
				default: opts.default_period || __("Month to Date"),
				...(opts.period || {}),
			},
			{
				fieldname: "from_date",
				label: __("From Date"),
				fieldtype: "Date",
				default: frappe.datetime.add_months(today, -1),
				depends_on: "eval:doc.period === 'Custom' || !doc.period",
				...(opts.from_date || {}),
			},
			{
				fieldname: "to_date",
				label: __("To Date"),
				fieldtype: "Date",
				default: today,
				depends_on: "eval:doc.period === 'Custom' || !doc.period",
				...(opts.to_date || {}),
			},
		];
	},

	// ------------------------------------------------------------------
	// Wire period select change → update from_date / to_date
	// Call from report's onload(report) hook.
	// ------------------------------------------------------------------

	setup_period_handler(report) {
		// Apply immediately on load
		this._apply_period(report);

		// Re-apply when the period filter changes
		const periodFilter = report.get_filter("period");
		if (periodFilter && periodFilter.$input) {
			periodFilter.$input.on("change", () => this._apply_period(report));
		}
	},

	_apply_period(report) {
		const period = report.get_filter_value("period");
		if (!period || period === __("Custom")) return;

		const { from_date, to_date } = this._period_dates(period);
		if (from_date) report.set_filter_value("from_date", from_date);
		if (to_date) report.set_filter_value("to_date", to_date);
	},

	_period_dates(period) {
		const today = frappe.datetime.get_today();
		const gd = frappe.datetime;

		switch (period) {
			case __("Today"):
				return { from_date: today, to_date: today };

			case __("Yesterday"): {
				const y = gd.add_days(today, -1);
				return { from_date: y, to_date: y };
			}

			case __("This Week"): {
				// Monday of current week to today
				const dow = frappe.moment(today).isoWeekday(); // 1=Mon … 7=Sun
				const mon = gd.add_days(today, -(dow - 1));
				return { from_date: mon, to_date: today };
			}

			case __("Last Week"): {
				const dow = frappe.moment(today).isoWeekday();
				const thisMon = gd.add_days(today, -(dow - 1));
				const lastMon = gd.add_days(thisMon, -7);
				const lastSun = gd.add_days(thisMon, -1);
				return { from_date: lastMon, to_date: lastSun };
			}

			case __("Month to Date"): {
				const mtd = gd.month_start(today);
				return { from_date: mtd, to_date: today };
			}

			case __("Last Month"): {
				const lm1 = gd.add_months(today, -1);
				return {
					from_date: gd.month_start(lm1),
					to_date: gd.month_end(lm1),
				};
			}

			case __("Quarter to Date"): {
				const qStart = frappe.datetime.quarter_start(today);
				return { from_date: qStart, to_date: today };
			}

			case __("Last Quarter"): {
				const prevQ = gd.add_months(today, -3);
				return {
					from_date: frappe.datetime.quarter_start(prevQ),
					to_date: frappe.datetime.quarter_end(prevQ),
				};
			}

			case __("Year to Date"): {
				const yStart = gd.year_start(today);
				return { from_date: yStart, to_date: today };
			}

			case __("Last 7 Days"):
				return { from_date: gd.add_days(today, -6), to_date: today };

			case __("Last 30 Days"):
				return { from_date: gd.add_days(today, -29), to_date: today };

			case __("Last 90 Days"):
				return { from_date: gd.add_days(today, -89), to_date: today };

			default:
				return {};
		}
	},

	// ------------------------------------------------------------------
	// Individual dimension filters
	// ------------------------------------------------------------------

	tank(opts = {}) {
		return {
			fieldname: "fuel_tank",
			label: __("Fuel Tank"),
			fieldtype: "Link",
			options: "Fuel Tank",
			get_query() {
				const station = frappe.query_report.get_filter_value("station");
				return station ? { filters: { station } } : {};
			},
			...(opts || {}),
		};
	},

	cashier(opts = {}) {
		return {
			fieldname: "cashier",
			label: __("Cashier"),
			fieldtype: "Link",
			options: "Employee",
			get_query() {
				return { filters: { fms_is_forecourt_cashier: 1 } };
			},
			...(opts || {}),
		};
	},

	shift_template(opts = {}) {
		return {
			fieldname: "shift_template",
			label: __("Shift Template"),
			fieldtype: "Link",
			options: "Forecourt Shift Template",
			get_query() {
				const station = frappe.query_report.get_filter_value("station");
				return station ? { filters: { station } } : {};
			},
			...(opts || {}),
		};
	},

	product(opts = {}) {
		return {
			fieldname: "item",
			label: __("Product"),
			fieldtype: "Link",
			options: "Item",
			get_query() {
				return { filters: { is_stock_item: 1 } };
			},
			...(opts || {}),
		};
	},

	supplier(opts = {}) {
		return {
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
			...(opts || {}),
		};
	},

	customer(opts = {}) {
		return {
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			...(opts || {}),
		};
	},

	only_exceptions(opts = {}) {
		return {
			fieldname: "only_exceptions",
			label: __("Only Exceptions"),
			fieldtype: "Check",
			default: 0,
			...(opts || {}),
		};
	},

	// ------------------------------------------------------------------
	// Single "as of" date (snapshot reports)
	// ------------------------------------------------------------------

	as_of(opts = {}) {
		return {
			fieldname: "date",
			label: __("As Of Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			...(opts || {}),
		};
	},

	// ------------------------------------------------------------------
	// Shift link (optional dimension on reconciliation reports)
	// ------------------------------------------------------------------

	shift_link(opts = {}) {
		return {
			fieldname: "forecourt_shift",
			label: __("Shift"),
			fieldtype: "Link",
			options: "Forecourt Shift",
			get_query() {
				const station = frappe.query_report.get_filter_value("station");
				return station ? { filters: { station } } : {};
			},
			...(opts || {}),
		};
	},

	// ------------------------------------------------------------------
	// Nozzle / Dispenser (wetstock detail reports)
	// ------------------------------------------------------------------

	nozzle(opts = {}) {
		return {
			fieldname: "nozzle",
			label: __("Nozzle"),
			fieldtype: "Link",
			options: "Nozzle",
			get_query() {
				const station = frappe.query_report.get_filter_value("station");
				return station ? { filters: { station } } : {};
			},
			...(opts || {}),
		};
	},

	dispenser(opts = {}) {
		return {
			fieldname: "dispenser",
			label: __("Dispenser / Pump"),
			fieldtype: "Link",
			options: "Pump",
			get_query() {
				const station = frappe.query_report.get_filter_value("station");
				return station ? { filters: { station } } : {};
			},
			...(opts || {}),
		};
	},

	// ------------------------------------------------------------------
	// Payment-specific filters
	// ------------------------------------------------------------------

	provider(opts = {}) {
		return {
			fieldname: "provider",
			label: __("Payment Provider"),
			fieldtype: "Link",
			options: "Payment Provider",
			...(opts || {}),
		};
	},

	payment_status(opts = {}) {
		return {
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nMatched\nUnmatched\nFailed",
			...(opts || {}),
		};
	},

	mode_of_payment(opts = {}) {
		return {
			fieldname: "mode_of_payment",
			label: __("Mode of Payment"),
			fieldtype: "Link",
			options: "Mode of Payment",
			...(opts || {}),
		};
	},

	// ------------------------------------------------------------------
	// Wetstock entry_type (tank stock movement)
	// ------------------------------------------------------------------

	entry_type(opts = {}) {
		return {
			fieldname: "entry_type",
			label: __("Entry Type"),
			fieldtype: "Select",
			options: "\nShift\nDelivery\nCorrection",
			...(opts || {}),
		};
	},

	// ------------------------------------------------------------------
	// Boolean: show only drifting nozzles
	// ------------------------------------------------------------------

	has_drift(opts = {}) {
		return {
			fieldname: "has_drift",
			label: __("Only Drifting Nozzles"),
			fieldtype: "Check",
			default: 0,
			...(opts || {}),
		};
	},
});
