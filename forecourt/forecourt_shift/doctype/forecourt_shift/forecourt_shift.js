// F11: Resolve buttons on cashier and tank-dip rows (inline form_render).
frappe.ui.form.on("Shift Cashier", {
	form_render(frm, cdt, cdn) {
		_add_cashier_resolve_button(frm, cdn);
	},
});

frappe.ui.form.on("Shift Tank Dip", {
	form_render(frm, cdt, cdn) {
		_add_tank_resolve_button(frm, cdn);
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
		if (frm.doc.docstatus === 0 && frm.doc.status === "Reconciled") {
			frm.add_custom_button(__("Close"), function () {
				frappe.confirm(
					__("Close this shift and post all accounting entries?"),
					function () {
						frappe.call({
							method: "forecourt.forecourt_shift.close.close_shift",
							args: { shift_name: frm.docname },
							freeze: true,
							freeze_message: __("Closing shift…"),
							callback(r) {
								if (r.message === "submitted") {
									frm.reload_doc();
								} else if (r.message === "enqueued") {
									frm.reload_doc();
									frappe.show_alert(
										{
											message: __(
												"Large shift queued for background close. Status will update automatically."
											),
											indicator: "blue",
										},
										8
									);
								}
							},
						});
					}
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.docstatus === 0 && ["Open", "Counting"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Reconcile"), function () {
				frm.call({
					method: "reconcile",
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
