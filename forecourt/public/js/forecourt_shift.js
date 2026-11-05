// Forecourt Shift client script — F03: live calculations
// Debounce-calls the server preview() method on grid changes;
// updates totals section. Enter-to-next-row on meter and tank grids.

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
