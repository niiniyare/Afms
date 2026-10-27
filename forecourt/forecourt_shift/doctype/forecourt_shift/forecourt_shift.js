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

		if (frm.doc.status === "Closing") {
			frm.disable_save();
			frm.set_intro(__("Closing in background…"), "blue");
		}
	},
});
