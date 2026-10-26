// Forecourt Shift client script
// F03: live calculations (debounce → preview())
// F11: Resolve buttons on cashier and tank rows

frappe.ui.form.on("Forecourt Shift", {
	setup(frm) {
		frm._preview_timer = null;
	},

	refresh(frm) {
		if (!frm.is_new()) {
			_schedule_preview(frm);
		}
	},
});

// ---- Resolve button on Shift Cashier rows ----
frappe.ui.form.on("Shift Cashier", {
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.cashier || flt(row.difference) === 0) return;
		if (row.resolved) return;
		const grid_form = frm.cur_grid_row?.grid_form;
		if (!grid_form) return;
		const $target = grid_form.fields_dict?.resolved?.$wrapper;
		if (!$target || $target.find(".btn-fms-resolve").length) return;
		const $btn = $('<button class="btn btn-xs btn-primary btn-fms-resolve ml-2">')
			.text(__("Resolve"))
			.appendTo($target);
		$btn.on("click", () => {
			frappe.call({
				method: "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift.add_resolution",
				args: { shift_name: frm.docname, resolution_for: "Cashier", ref: row.cashier },
				callback() {
					frm.reload_doc();
				},
			});
		});
	},
});

// ---- Resolve button on Shift Tank Dip rows ----
frappe.ui.form.on("Shift Tank Dip", {
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.tank || row.within_tolerance) return;
		const grid_form = frm.cur_grid_row?.grid_form;
		if (!grid_form) return;
		const $target = grid_form.fields_dict?.needs_approval?.$wrapper;
		if (!$target || $target.find(".btn-fms-resolve").length) return;
		const $btn = $('<button class="btn btn-xs btn-primary btn-fms-resolve ml-2">')
			.text(__("Resolve Variance"))
			.appendTo($target);
		$btn.on("click", () => {
			frappe.call({
				method: "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift.add_resolution",
				args: { shift_name: frm.docname, resolution_for: "Tank", ref: row.tank },
				callback() {
					frm.reload_doc();
				},
			});
		});
	},
});

// ---- Meter Reading grid: enter moves to next row ----
frappe.ui.form.on("Shift Meter Reading", {
	closing_elec_cash(frm) {
		_schedule_preview(frm);
	},
	closing_elec_meter(frm) {
		_schedule_preview(frm);
	},
	closing_man_meter(frm) {
		_schedule_preview(frm);
	},
	rollover_elec_cash(frm) {
		_schedule_preview(frm);
	},
	rollover_elec_meter(frm) {
		_schedule_preview(frm);
	},
	rollover_man_meter(frm) {
		_schedule_preview(frm);
	},
	test_volume_l(frm) {
		_schedule_preview(frm);
	},
});

// ---- Tank Dip grid ----
frappe.ui.form.on("Shift Tank Dip", {
	dip_mm(frm) {
		_schedule_preview(frm);
	},
	dip_l(frm) {
		_schedule_preview(frm);
	},
	water_mm(frm) {
		_schedule_preview(frm);
	},
	water_l(frm) {
		_schedule_preview(frm);
	},
});

// ---- Cashier / Collection grids ----
frappe.ui.form.on("Shift Cash Count", {
	amount(frm) {
		_schedule_preview(frm);
	},
});

frappe.ui.form.on("Shift Collection", {
	amount(frm) {
		_schedule_preview(frm);
	},
	collection_type(frm) {
		_schedule_preview(frm);
	},
});

frappe.ui.form.on("Shift Credit Sale", {
	qty(frm) {
		_schedule_preview(frm);
	},
	amount(frm) {
		_schedule_preview(frm);
	},
});

frappe.ui.form.on("Shift Item Sale", {
	qty(frm) {
		_schedule_preview(frm);
	},
	rate(frm) {
		_schedule_preview(frm);
	},
});

function _schedule_preview(frm) {
	if (frm.is_new()) return;
	clearTimeout(frm._preview_timer);
	frm._preview_timer = setTimeout(() => _run_preview(frm), 600);
}

function _run_preview(frm) {
	frappe.call({
		method: "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift.preview",
		args: { shift_name: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			const d = r.message;
			const fields = [
				"total_fuel_volume",
				"total_fuel_amount",
				"total_item_amount",
				"total_credit",
				"total_mobile",
				"total_card",
				"total_cash",
				"total_expenses",
				"total_difference",
				"total_tank_variance_l",
			];
			fields.forEach((f) => {
				if (d[f] !== undefined) {
					frm.set_value(f, d[f]);
				}
			});
		},
	});
}
