frappe.ui.form.on('Work Order', {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1) {
            // Check stock reservation status from the reorganized overrides backend
            frappe.call({
                method: 'outpost_assessment.outpost_assessment.overrides.stock_reservation.check_reservation_status',
                args: {
                    work_order_name: frm.doc.name
                },
                callback: function (r) {
                    if (r.message) {
                        frm.remove_custom_button('Reserve Stock');
                        frm.remove_custom_button('Unreserve Stock');

                        if (r.message.has_reservation) {
                            frm.add_custom_button(__('Unreserve Stock'), function () {
                                frappe.confirm(__('Are you sure you want to unreserve stock for this Work Order?'), function () {
                                    frappe.call({
                                        method: 'outpost_assessment.outpost_assessment.overrides.stock_reservation.unreserve_stock_for_work_order',
                                        args: {
                                            work_order_name: frm.doc.name
                                        },
                                        callback: function (res) {
                                            if (res.message && res.message.status === 'Success') {
                                                frappe.msgprint({
                                                    title: __('Success'),
                                                    indicator: 'green',
                                                    message: res.message.message
                                                });
                                                frm.refresh();
                                            }
                                        }
                                    });
                                });
                            }, __('Stock Reservation'));
                        } else {
                            frm.add_custom_button(__('Reserve Stock'), function () {
                                frappe.call({
                                    method: 'outpost_assessment.outpost_assessment.overrides.stock_reservation.reserve_stock_for_work_order',
                                    args: {
                                        work_order_name: frm.doc.name
                                    },
                                    callback: function (res) {
                                        if (res.message) {
                                            frappe.msgprint({
                                                title: res.message.status === 'Success' ? __('Success') : __('Info'),
                                                indicator: res.message.status === 'Success' ? 'green' : 'orange',
                                                message: res.message.message
                                            });
                                            frm.refresh();
                                        }
                                    }
                                });
                            }, __('Stock Reservation'));
                        }
                    }
                }
            });
        }
    }
});
