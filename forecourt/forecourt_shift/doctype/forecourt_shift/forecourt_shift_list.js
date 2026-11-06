// FMS-U05: "New Shift" button on the Forecourt Shift list view.
// The form JS is not loaded in list context, so the dialog helpers are
// duplicated here rather than shared through a module.

frappe.listview_settings["Forecourt Shift"] = {
	onload(listview) {
		listview.page.add_inner_button(__("New Shift"), function () {
			_new_shift_dialog();
		});
	},
};

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
