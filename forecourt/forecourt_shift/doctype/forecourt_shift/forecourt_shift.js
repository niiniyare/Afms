// Status indicator colours — overrides the workflow approval_state badge.
const STATUS_COLOUR = {
	Open: "orange",
	Counting: "yellow",
	"Pending Approval": "purple",
	Reconciled: "blue",
	Closing: "blue",
	Closed: "green",
};

function _set_status_indicator(frm) {
	if (frm.doc.docstatus === 1) return; // submitted; Frappe shows green "Submitted"
	const colour = STATUS_COLOUR[frm.doc.status] || "grey";
	frm.page.set_indicator(__(frm.doc.status), colour);
}

// F11: Resolve buttons on cashier and tank-dip rows (inline form_render).
frappe.ui.form.on("Shift Cashier", {
	form_render(frm, cdt, cdn) {
		_add_cashier_resolve_button(frm, cdn);
	},
});

frappe.ui.form.on("Shift Tank Dip", {
	form_render(frm, cdt, cdn) {
		_add_tank_resolve_button(frm, cdn);
		_set_tank_dip_flag(frm, cdt, cdn);
	},
	dip_l(frm, cdt, cdn) {
		_set_tank_dip_flag(frm, cdt, cdn);
	},
	dip_mm(frm, cdt, cdn) {
		_set_tank_dip_flag(frm, cdt, cdn);
	},
});

// FMS-U04: Meter reading field changes — update flag column inline.
frappe.ui.form.on("Shift Meter Reading", {
	form_render(frm, cdt, cdn) {
		_add_meter_history_button(frm, cdn);
		_set_meter_flag(frm, cdt, cdn);
	},
	closing_elec_cash(frm, cdt, cdn) {
		_set_meter_flag(frm, cdt, cdn);
	},
	closing_elec_meter(frm, cdt, cdn) {
		_set_meter_flag(frm, cdt, cdn);
	},
	closing_man_meter(frm, cdt, cdn) {
		_set_meter_flag(frm, cdt, cdn);
	},
	drift_breach(frm, cdt, cdn) {
		_set_meter_flag(frm, cdt, cdn);
	},
});

// F16: Close button and background-close realtime handling.
frappe.ui.form.on("Forecourt Shift", {
	onload(frm) {
		// Register once; reload when background close finishes or fails.
		frappe.realtime.on("shift_closed", function (data) {
			if (data.shift !== frm.docname) return;
			frm.reload_doc();
			if (data.error) {
				frappe.msgprint({
					title: __("Close Failed"),
					message: __("Background close failed. See document comments for details."),
					indicator: "red",
				});
			}
		});
	},

	refresh(frm) {
		_set_status_indicator(frm);

		// U04: Show all meters toggle and flag/status coloring.
		_setup_meters_toggle(frm);
		_color_grid_flags(frm, "meter_readings", "Shift Meter Reading");
		_color_grid_flags(frm, "tank_dips", "Shift Tank Dip");

		// U06: readiness panel on Overview tab for active draft shifts.
		if (
			frm.doc.docstatus === 0 &&
			["Counting", "Reconciled", "Pending Approval"].includes(frm.doc.status)
		) {
			_load_readiness_panel(frm);
		} else if (frm.fields_dict.readiness_html) {
			frm.fields_dict.readiness_html.$wrapper.html("");
		}

		if (frm.doc.docstatus === 0 && frm.doc.status === "Reconciled") {
			frm.add_custom_button(__("Close"), function () {
				_show_close_confirm_dialog(frm);
			}).addClass("btn-primary");
		}

		if (frm.doc.docstatus === 0 && ["Open", "Counting"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Reconcile"), function () {
				frappe.call({
					method: "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift.reconcile",
					args: { shift_name: frm.docname },
					freeze: true,
					freeze_message: __("Checking shift…"),
					callback(r) {
						if (r.message) {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Shift is now {0}", [__(r.message)]),
								indicator: r.message === "Reconciled" ? "green" : "orange",
							});
						}
					},
				});
			}).addClass("btn-primary");

			frm.add_custom_button(
				__("Import Transactions"),
				function () {
					_import_transactions_dialog(frm);
				},
				__("Tools")
			);
			frm.add_custom_button(
				__("Refresh Feeds"),
				function () {
					frm.call("refresh_feeds").then((r) => {
						if (r.message) {
							const n = r.message.created;
							frappe.show_alert({
								message: n
									? __("{0} feed transaction(s) added", [n])
									: __("No new feed transactions"),
								indicator: n ? "green" : "blue",
							});
							frm.reload_doc();
						}
					});
				},
				__("Tools")
			);
		}

		if (frm.doc.status === "Closing") {
			frm.disable_save();
			frm.set_intro(__("Closing in background…"), "blue");
		}
	},
});

function _add_cashier_resolve_button(frm, cdn) {
	const row = locals["Shift Cashier"] && locals["Shift Cashier"][cdn];
	if (!row || frm.doc.docstatus !== 0) return;
	const diff = frappe.utils.flt(row.difference);
	if (diff === 0 || row.resolved) return;

	const grid = frm.fields_dict.cashiers && frm.fields_dict.cashiers.grid;
	if (!grid || !grid.grid_form) return;
	const $wrapper = $(grid.grid_form.wrapper);
	if ($wrapper.find(".fms-resolve-cashier-btn").length) return;

	const default_action = diff < 0 ? "Charge to cashier" : "Record excess";
	const $section = $(`<div class="fms-resolve-section" style="padding:6px 15px 8px">
		<button class="btn btn-sm btn-default fms-resolve-cashier-btn">
			${__("Resolve")} (${frappe.format(Math.abs(diff), { fieldtype: "Currency" })})
		</button>
	</div>`);
	$section.find(".fms-resolve-cashier-btn").on("click", function () {
		_resolve_cashier_dialog(frm, row, default_action);
	});
	$wrapper.append($section);
}

function _add_tank_resolve_button(frm, cdn) {
	const row = locals["Shift Tank Dip"] && locals["Shift Tank Dip"][cdn];
	if (!row || frm.doc.docstatus !== 0) return;
	if (row.within_tolerance) return;

	const grid = frm.fields_dict.tank_dips && frm.fields_dict.tank_dips.grid;
	if (!grid || !grid.grid_form) return;
	const $wrapper = $(grid.grid_form.wrapper);
	if ($wrapper.find(".fms-resolve-tank-btn").length) return;

	const $section = $(`<div class="fms-resolve-section" style="padding:6px 15px 8px">
		<button class="btn btn-sm btn-default fms-resolve-tank-btn">
			${__("Resolve Variance")} (${frappe.format(row.variance_l, { fieldtype: "Float" })} L)
		</button>
	</div>`);
	$section.find(".fms-resolve-tank-btn").on("click", function () {
		_resolve_tank_dialog(frm, row);
	});
	$wrapper.append($section);
}

function _resolve_cashier_dialog(frm, row, default_action) {
	const diff = frappe.utils.flt(row.difference);
	const dialog = new frappe.ui.Dialog({
		title: __("Resolve: {0}", [row.cashier]),
		fields: [
			{
				fieldname: "action",
				fieldtype: "Select",
				label: __("Action"),
				options: "Charge to cashier\nWrite off\nRecord excess",
				default: default_action,
				reqd: 1,
			},
			{
				fieldname: "amount",
				fieldtype: "Currency",
				label: __("Amount"),
				default: Math.abs(diff),
				reqd: 1,
			},
			{
				fieldname: "reason",
				fieldtype: "Link",
				label: __("Reason"),
				options: "Variance Reason",
				get_query() {
					return { filters: { applies_to_cashier: 1, disabled: 0 } };
				},
				reqd: 1,
			},
			{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
		],
		primary_action_label: __("Add Resolution"),
		primary_action(values) {
			dialog.hide();
			const res = frm.add_child("resolutions");
			res.resolution_for = "Cashier";
			res.cashier = row.cashier;
			res.action = values.action;
			res.amount = values.amount;
			res.reason = values.reason;
			res.note = values.note || "";
			frm.refresh_field("resolutions");
			frm.dirty();
		},
	});
	dialog.show();
}

function _resolve_tank_dialog(frm, row) {
	const dialog = new frappe.ui.Dialog({
		title: __("Resolve Tank Variance: {0}", [row.tank]),
		fields: [
			{
				fieldname: "volume_l",
				fieldtype: "Float",
				label: __("Volume (L)"),
				default: row.variance_l,
				reqd: 1,
			},
			{
				fieldname: "reason",
				fieldtype: "Link",
				label: __("Reason"),
				options: "Variance Reason",
				get_query() {
					return { filters: { applies_to_tank: 1, disabled: 0 } };
				},
				reqd: 1,
			},
			{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
		],
		primary_action_label: __("Add Resolution"),
		primary_action(values) {
			dialog.hide();
			const res = frm.add_child("resolutions");
			res.resolution_for = "Tank";
			res.tank = row.tank;
			res.action = "Accept variance";
			res.volume_l = values.volume_l;
			res.reason = values.reason;
			res.note = values.note || "";
			frm.refresh_field("resolutions");
			frm.dirty();
		},
	});
	dialog.show();
}

// FMS-U05: New Shift dialog —————————————————————————————————————————————

function _new_shift_dialog(preset) {
	preset = preset || {};
	const dialog = new frappe.ui.Dialog({
		title: __("New Shift"),
		fields: [
			{
				fieldname: "station",
				fieldtype: "Link",
				options: "Station",
				label: __("Station"),
				reqd: 1,
				read_only: preset.station ? 1 : 0,
				default: preset.station || "",
				onchange() {
					dialog.set_values({ shift_template: "", shift_date: "" });
					_set_dialog_info(dialog, "");
					if (dialog.get_value("station")) {
						_refresh_shift_dialog_defaults(dialog);
					}
				},
			},
			{
				fieldname: "shift_template",
				fieldtype: "Link",
				options: "Forecourt Shift Template",
				label: __("Shift Template"),
				reqd: 1,
				get_query() {
					return {
						filters: { station: dialog.get_value("station") || "", active: 1 },
					};
				},
			},
			{
				fieldname: "shift_date",
				fieldtype: "Date",
				label: __("Shift Date"),
				reqd: 1,
			},
			{
				fieldname: "info_html",
				fieldtype: "HTML",
				label: "",
				options: "",
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			dialog.disable_primary_action();
			frappe.call({
				method: "forecourt.forecourt_shift.create.create_shift",
				args: {
					station: values.station,
					shift_template: values.shift_template,
					shift_date: values.shift_date,
				},
				callback(r) {
					if (!r.exc && r.message) {
						dialog.hide();
						frappe.set_route("Form", "Forecourt Shift", r.message.shift);
					} else {
						dialog.enable_primary_action();
					}
				},
			});
		},
	});

	if (preset.station) {
		_refresh_shift_dialog_defaults(dialog);
	}
	dialog.show();
}

function _refresh_shift_dialog_defaults(dialog) {
	const station = dialog.get_value("station");
	if (!station) return;
	frappe.call({
		method: "forecourt.forecourt_shift.create.get_new_shift_defaults",
		args: { station },
		callback(r) {
			if (r.exc || !r.message) return;
			const d = r.message;
			if (d.next_template) dialog.set_value("shift_template", d.next_template);
			if (d.next_date) dialog.set_value("shift_date", d.next_date);
			_set_dialog_info(dialog, d.previous_shift_label || "");
		},
	});
}

function _set_dialog_info(dialog, text) {
	const $html = dialog.get_field("info_html").$wrapper;
	if (text) {
		$html.html(
			`<p class="text-muted small" style="margin:4px 0">${frappe.utils.escape_html(
				text
			)}</p>`
		);
	} else {
		$html.html("");
	}
}

// FMS-U07: Close confirmation dialog with shift totals summary ———————————————

function _show_close_confirm_dialog(frm) {
	const d = frm.doc;
	const fmt_cur = (v) => frappe.format(v || 0, { fieldtype: "Currency" });
	const fmt_flt = (v, prec) =>
		frappe.format(v || 0, { fieldtype: "Float", precision: prec || 3 });

	const rows = [
		[__("Station"), frappe.utils.escape_html(d.station || "")],
		[__("Shift Template"), frappe.utils.escape_html(d.shift_template || "")],
		[__("Shift Date"), frappe.format(d.shift_date, { fieldtype: "Date" })],
		["—", ""],
		[__("Fuel Volume (L)"), fmt_flt(d.total_fuel_volume)],
		[__("Fuel Amount"), fmt_cur(d.total_fuel_amount)],
		["—", ""],
		[__("Cash"), fmt_cur(d.total_cash)],
		[__("Mobile Money"), fmt_cur(d.total_mobile)],
		[__("Card"), fmt_cur(d.total_card)],
		[__("Credit Sales"), fmt_cur(d.total_credit)],
		[__("Expenses"), fmt_cur(d.total_expenses)],
		["—", ""],
		[__("Net Difference"), fmt_cur(d.total_difference)],
	];

	let table_html =
		`<table class="table table-condensed" style="font-size:0.9em;margin:0">` + `<tbody>`;
	for (const [label, value] of rows) {
		if (label === "—") {
			table_html += `<tr><td colspan="2"><hr style="margin:4px 0"></td></tr>`;
		} else {
			table_html +=
				`<tr>` +
				`<td style="color:#888;padding:2px 8px 2px 0;white-space:nowrap">${label}</td>` +
				`<td style="text-align:right;padding:2px 0">${value}</td>` +
				`</tr>`;
		}
	}
	table_html += `</tbody></table>`;

	const dialog = new frappe.ui.Dialog({
		title: __("Close Shift"),
		fields: [
			{
				fieldname: "summary_html",
				fieldtype: "HTML",
				options: table_html,
			},
		],
		primary_action_label: __("Close and Post"),
		secondary_action_label: __("Cancel"),
		primary_action() {
			dialog.disable_primary_action();
			frappe.call({
				method: "forecourt.forecourt_shift.close.close_shift",
				args: { shift_name: frm.docname },
				callback(r) {
					if (r.exc) {
						dialog.enable_primary_action();
						return;
					}
					dialog.hide();
					if (r.message === "submitted") {
						frm.reload_doc();
						_after_close_prompt(frm);
					} else {
						frm.reload_doc();
						frappe.show_alert({
							message: __("Closing shift in background…"),
							indicator: "blue",
						});
					}
				},
			});
		},
		secondary_action() {
			dialog.hide();
		},
	});
	dialog.show();
}

function _after_close_prompt(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Shift Closed"),
		fields: [
			{
				fieldname: "info",
				fieldtype: "HTML",
				options: `<p>${__("Shift {0} is now closed.", [
					frappe.utils.escape_html(frm.docname),
				])}</p>`,
			},
		],
		primary_action_label: __("Open Next Shift"),
		primary_action() {
			d.hide();
			_new_shift_dialog({ station: frm.doc.station });
		},
		secondary_action_label: __("Done"),
		secondary_action() {
			d.hide();
		},
	});
	d.show();
}

// FMS-U04: Grid standards — flag column, Show all meters toggle, History ————

const _METER_FLAG_COLOR = {
	Missing: "#888",
	"Below opening": "#d9534f",
	"Over limit": "#d9534f",
	Drift: "#e67e22",
	Unusual: "#e67e22",
	OK: "#5cb85c",
};
const _TANK_FLAG_COLOR = {
	Approval: "#f0ad4e",
	Outside: "#d9534f",
	Within: "#5cb85c",
};

function _set_meter_flag(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row) return;
	let flag;
	const closing = frappe.utils.flt(row.closing_elec_cash);
	const opening = frappe.utils.flt(row.opening_elec_cash);
	if (!closing && !row.rollover_elec_cash) {
		flag = __("Missing");
	} else if (closing < opening && !row.rollover_elec_cash) {
		flag = __("Below opening");
	} else if (row.drift_breach) {
		flag = __("Drift");
	} else {
		flag = __("OK");
	}
	frappe.model.set_value(cdt, cdn, "flag", flag);
}

function _set_tank_dip_flag(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row) return;
	let flag;
	if (row.needs_approval) {
		flag = __("Approval");
	} else if (row.within_tolerance) {
		flag = __("Within");
	} else {
		flag = __("Outside");
	}
	frappe.model.set_value(cdt, cdn, "flag", flag);
}

function _color_grid_flags(frm, grid_fieldname, child_doctype) {
	const $grid = frm.fields_dict[grid_fieldname] && frm.fields_dict[grid_fieldname].$wrapper;
	if (!$grid) return;
	const color_map =
		child_doctype === "Shift Meter Reading" ? _METER_FLAG_COLOR : _TANK_FLAG_COLOR;
	$grid
		.find('[data-fieldname="flag"] .like-disabled-input, [data-fieldname="flag"] .static-area')
		.each(function () {
			const text = $(this).text().trim();
			const c = color_map[text];
			if (c) {
				$(this).css({ color: c, "font-weight": "bold" });
			}
		});
}

function _setup_meters_toggle(frm) {
	const $wrapper = frm.fields_dict.meter_readings && frm.fields_dict.meter_readings.$wrapper;
	if (!$wrapper) return;
	// Only show when station records more than basis meter.
	const has_extra = frm.doc.record_elec_meter || frm.doc.record_man_meter;
	if (!has_extra) return;
	if ($wrapper.find(".fms-meters-toggle").length) return;

	const $toggle = $(
		`<span class="fms-meters-toggle" style="margin-left:10px;font-size:0.85em">` +
			`<label style="font-weight:normal;cursor:pointer">` +
			`<input type="checkbox" style="margin-right:4px">` +
			`${__("Show all meters")}` +
			`</label></span>`
	);
	$wrapper.find(".grid-heading-row").first().find(".col-header-label").first().after($toggle);
	$toggle.find("input").on("change", function () {
		_set_all_meters_view(frm, this.checked);
	});
}

// Toggle between basis-only view (10 col default) and all-meters view (10 col).
// Default:   nozzle(1) item(1) cashier(2) opening(1) closing(2) litres(1) amount(1) flag(1)
// All-meters: nozzle(1) cashier(2) closing_ecash(2) closing_evol(2) closing_mvol(2) flag(1)
function _set_all_meters_view(frm, show_all) {
	const basis_only = ["item", "opening_elec_cash", "net_volume_l", "amount"];
	const extra = [
		["closing_elec_meter", 2],
		["closing_man_meter", 2],
	];
	for (const fn of basis_only) {
		const df = frappe.meta.get_docfield("Shift Meter Reading", fn);
		if (df) df.in_list_view = show_all ? 0 : 1;
	}
	for (const [fn, col] of extra) {
		const df = frappe.meta.get_docfield("Shift Meter Reading", fn);
		if (df) {
			df.in_list_view = show_all ? 1 : 0;
			df.columns = col;
		}
	}
	frm.refresh_field("meter_readings");
	_color_grid_flags(frm, "meter_readings", "Shift Meter Reading");
}

function _add_meter_history_button(frm, cdn) {
	const row = locals["Shift Meter Reading"] && locals["Shift Meter Reading"][cdn];
	if (!row || !row.nozzle) return;
	const grid = frm.fields_dict.meter_readings && frm.fields_dict.meter_readings.grid;
	if (!grid || !grid.grid_form) return;
	const $wrapper = $(grid.grid_form.wrapper);
	if ($wrapper.find(".fms-meter-history-btn").length) return;

	const $section = $(
		`<div class="fms-history-section" style="padding:4px 15px 8px">` +
			`<button class="btn btn-xs btn-default fms-meter-history-btn">` +
			`${__("View History")}` +
			`</button></div>`
	);
	$section.find(".fms-meter-history-btn").on("click", function () {
		frappe.set_route("query-report", "Meter Movement", {
			nozzle: row.nozzle,
			from_date: frappe.datetime.add_days(frappe.datetime.nowdate(), -30),
			to_date: frappe.datetime.nowdate(),
		});
	});
	$wrapper.append($section);
}

// FMS-U06: Close Readiness Panel ————————————————————————————————————————————

function _load_readiness_panel(frm) {
	const $html = frm.fields_dict.readiness_html && frm.fields_dict.readiness_html.$wrapper;
	if (!$html) return;
	$html.html(`<p class="text-muted small" style="margin:4px 0">${__("Checking…")}</p>`);
	frappe.call({
		method: "forecourt.forecourt_shift.readiness.get_close_readiness",
		args: { shift_name: frm.docname },
		callback(r) {
			if (r.exc || !r.message) {
				$html.html("");
				return;
			}
			_render_readiness_panel(frm, r.message);
		},
	});
}

function _render_readiness_panel(frm, data) {
	const STATE_COLOR = {
		Blocked: "#d9534f",
		Waiting: "#f0ad4e",
		Attention: "#e67e22",
		Ready: "#5cb85c",
	};
	const STATE_LABEL = {
		Blocked: __("Blocked — issues must be resolved before closing"),
		Waiting: __("Waiting for Approval"),
		Attention: __("Attention — drift reasons required"),
		Ready: __("Ready to Close"),
	};

	const color = STATE_COLOR[data.state] || "#888";
	const label = STATE_LABEL[data.state] || data.state;

	let html =
		`<div style="margin:6px 0 8px;display:flex;align-items:center;gap:8px">` +
		`<span style="display:inline-block;padding:3px 10px;border-radius:3px;` +
		`background:${color};color:#fff;font-weight:bold;font-size:0.88em">${label}</span>` +
		`<button class="btn btn-xs btn-default fms-readiness-refresh">${__(
			"Check again"
		)}</button>` +
		`</div>`;

	if (data.items && data.items.length) {
		const SEV_COLOR = { blocking: "#d9534f", waiting: "#f0ad4e", attention: "#e67e22" };
		html +=
			`<table class="table table-condensed" style="font-size:0.82em;margin:0 0 4px">` +
			`<thead><tr>` +
			`<th style="width:90px">${__("Code")}</th>` +
			`<th style="width:100px">${__("Area")}</th>` +
			`<th>${__("Issue")}</th>` +
			`<th>${__("Fix")}</th>` +
			`</tr></thead><tbody>`;
		for (const item of data.items) {
			const sc = SEV_COLOR[item.severity] || "#888";
			// Strip the [FMS-Sxxx] prefix from message for the table cell; it's shown in Code column.
			const msg = frappe.utils.escape_html(item.message.replace(/^\[.*?\]\s*/, ""));
			html +=
				`<tr>` +
				`<td><code style="color:${sc}">${frappe.utils.escape_html(
					item.code
				)}</code></td>` +
				`<td>${frappe.utils.escape_html(item.area)}</td>` +
				`<td>${msg}</td>` +
				`<td><em>${frappe.utils.escape_html(item.fix)}</em></td>` +
				`</tr>`;
		}
		html += `</tbody></table>`;
	} else {
		html +=
			`<p class="text-muted small" style="margin:0">` +
			`${__("All checks passed. Click Close to submit the shift.")}` +
			`</p>`;
	}

	const $html = frm.fields_dict.readiness_html && frm.fields_dict.readiness_html.$wrapper;
	if (!$html) return;
	$html.html(html);
	$html.find(".fms-readiness-refresh").on("click", function () {
		_load_readiness_panel(frm);
	});
}

// ————————————————————————————————————————————————————————————————————————————

function _import_transactions_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Import Transactions"),
		fields: [
			{
				fieldname: "provider",
				fieldtype: "Link",
				label: __("Payment Provider"),
				options: "Payment Provider",
				reqd: 1,
			},
			{
				fieldname: "file",
				fieldtype: "Attach",
				label: __("Statement File"),
				reqd: 1,
			},
		],
		primary_action_label: __("Import"),
		primary_action(values) {
			dialog.hide();
			frappe.show_alert({ message: __("Importing…"), indicator: "blue" });
			frappe.call({
				method: "forecourt.forecourt_integrations.statement_import.run_for_shift",
				args: {
					shift: frm.docname,
					provider: values.provider,
					file_url: values.file,
				},
				callback(r) {
					if (!r.exc && r.message) {
						const m = r.message;
						frappe.msgprint({
							title: __("Import Complete"),
							message: __(
								"Read: {0} · Created: {1} · Duplicate: {2} · Rejected: {3}",
								[m.rows_read, m.rows_created, m.rows_duplicate, m.rows_rejected]
							),
							indicator: m.rows_rejected ? "orange" : "green",
						});
						frm.reload_doc();
					}
				},
			});
		},
	});
	dialog.show();
}
