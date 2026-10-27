frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		const dips = frm.doc.fms_delivery_dips || [];
		dips.forEach(function (row) {
			const shortage = flt(row.invoiced_l) - flt(row.received_l);
			if (shortage > 0 && !row.shortage_stock_entry) {
				frm.add_custom_button(
					__("Record Shortage ({0})", [row.tank]),
					function () {
						frappe.call({
							method: "forecourt.wetstock.delivery_shortage.create_shortage_entry",
							args: {
								purchase_receipt: frm.doc.name,
								tank: row.tank,
							},
							callback: function (r) {
								if (r.message) {
									frappe.show_alert({
										message: __("Shortage entry {0} created.", [r.message]),
										indicator: "green",
									});
									frm.reload_doc();
								}
							},
						});
					},
					__("Deliveries")
				);
			}
		});
	},
});
