frappe.ui.form.on('Production Request', {
    setup: function (frm) {
        frm.set_query('item', 'items', function () {
            return {
                filters: {
                    include_item_in_manufacturing: 1
                }
            };
        });

        frm.set_query('bom_no', 'items', function (doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                filters: {
                    item: row.item || '',
                    is_active: 1,
                    docstatus: 1
                }
            };
        });
    },
    items_add: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (frm.doc.fg_warehouse) {
            frappe.model.set_value(cdt, cdn, 'fg_warehouse', frm.doc.fg_warehouse);
        }
        if (frm.doc.required_date) {
            frappe.model.set_value(cdt, cdn, 'required_date', frm.doc.required_date);
        }
    },
    refresh: function (frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Get Items from Sales Order'), function () {
                let d = new frappe.ui.Dialog({
                    title: __('Select Sales Order'),
                    fields: [
                        {
                            label: __('Sales Order'),
                            fieldname: 'sales_order',
                            fieldtype: 'Link',
                            options: 'Sales Order',
                            reqd: 1,
                            get_query: function () {
                                return {
                                    filters: {
                                        company: frm.doc.company || frappe.defaults.get_user_default("company") || "Test",
                                        docstatus: 1,
                                        status: ["not in", ["Closed", "Completed"]]
                                    }
                                };
                            }
                        }
                    ],
                    primary_action_label: __('Get Items'),
                    primary_action: function (values) {
                        d.hide();
                        frappe.call({
                            method: "outpost_assessment.outpost_assessment.doctype.production_request.production_request.get_items_from_sales_order",
                            args: {
                                sales_order: values.sales_order
                            },
                            callback: function (r) {
                                if (r.message && r.message.length > 0) {
                                    frm.clear_table("items");
                                    $.each(r.message, function (i, d) {
                                        let row = frm.add_child("items");
                                        row.item = d.item;
                                        row.item_name = d.item_name;
                                        row.stock_uom = d.stock_uom;
                                        row.production_qty = d.production_qty;
                                        row.required_date = d.required_date;
                                        row.bom_no = d.bom_no;
                                        if (frm.doc.fg_warehouse) {
                                            row.fg_warehouse = frm.doc.fg_warehouse;
                                        }
                                    });
                                    frm.refresh_field("items");
                                    frm.save();
                                    frappe.show_alert(__('Fetched {0} items from Sales Order.').format(r.message.length));
                                } else {
                                    frappe.msgprint(__('No items belonging to Product group found in the Sales Order.'));
                                }
                            }
                        });
                    }
                });
                d.show();
            }, __('Actions'));

            frm.add_custom_button(__('Get Items from Material Request'), function () {
                let d = new frappe.ui.Dialog({
                    title: __('Select Material Request'),
                    fields: [
                        {
                            label: __('Material Request'),
                            fieldname: 'material_request',
                            fieldtype: 'Link',
                            options: 'Material Request',
                            reqd: 1,
                            get_query: function () {
                                return {
                                    filters: {
                                        company: frm.doc.company || frappe.defaults.get_user_default("company") || "Test",
                                        docstatus: 1,
                                        material_request_type: "Manufacture",
                                        status: ["not in", ["Closed", "Stopped"]]
                                    }
                                };
                            }
                        }
                    ],
                    primary_action_label: __('Get Items'),
                    primary_action: function (values) {
                        d.hide();
                        frappe.call({
                            method: "outpost_assessment.outpost_assessment.doctype.production_request.production_request.get_items_from_material_request",
                            args: {
                                material_request: values.material_request
                            },
                            callback: function (r) {
                                if (r.message && r.message.length > 0) {
                                    frm.clear_table("items");
                                    $.each(r.message, function (i, d) {
                                        let row = frm.add_child("items");
                                        row.item = d.item;
                                        row.item_name = d.item_name;
                                        row.stock_uom = d.stock_uom;
                                        row.production_qty = d.production_qty;
                                        row.required_date = d.required_date;
                                        row.bom_no = d.bom_no;
                                        if (frm.doc.fg_warehouse) {
                                            row.fg_warehouse = frm.doc.fg_warehouse;
                                        }
                                    });
                                    frm.refresh_field("items");
                                    frm.save();
                                    frappe.show_alert(__('Fetched {0} items from Material Request.').format(r.message.length));
                                } else {
                                    frappe.msgprint(__('No items belonging to Product group found in the Material Request.'));
                                }
                            }
                        });
                    }
                });
                d.show();
            }, __('Actions'));
        }
 
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            let has_shortage = false;
            if (frm.doc.material_requirements) {
                $.each(frm.doc.material_requirements, function (i, r) {
                    if (flt(r.shortage_qty) > 0) {
                        has_shortage = true;
                        return false;
                    }
                });
            }

            if (has_shortage) {
                frm.add_custom_button(__('Material Request for Shortage'), function () {
                    frappe.call({
                        method: "outpost_assessment.outpost_assessment.doctype.production_request.production_request.create_material_request_for_shortages",
                        args: {
                            docname: frm.doc.name
                        },
                        freeze: true,
                        freeze_message: __('Creating Material Request...'),
                        callback: function (r) {
                            if (r && r.message) {
                                let mr_name = r.message;
                                let link = `<a href="/app/material-request/${mr_name}" target="_blank"><b>${mr_name}</b></a>`;
                                frappe.msgprint({
                                    title: __('Material Request Created'),
                                    message: __('Material Request {0} has been created and submitted successfully.', [link]),
                                    indicator: 'green'
                                });
                                frm.reload_doc();
                            }
                        }
                    });
                }, __('Create'));
            }
        }
 
        render_progress_bar(frm);
    },

    fg_warehouse: function (frm) {
        if (frm.doc.fg_warehouse && frm.doc.items && frm.doc.items.length > 0) {
            $.each(frm.doc.items, function (i, row) {
                frappe.model.set_value(row.doctype, row.name, 'fg_warehouse', frm.doc.fg_warehouse);
            });
        }
    },
    required_date: function (frm) {
        if (frm.doc.required_date && frm.doc.items && frm.doc.items.length > 0) {
            $.each(frm.doc.items, function (i, row) {
                frappe.model.set_value(row.doctype, row.name, 'required_date', frm.doc.required_date);
            });
        }
    },

    get_sub_assembly_items: function (frm) {
        frappe.call({
            method: "outpost_assessment.outpost_assessment.doctype.production_request.production_request.run_get_sub_assembly_items",
            args: {
                doc: frm.doc
            },
            callback: function (r) {
                frm.clear_table("sub_assemblies");
                if (r.message && r.message.length > 0) {
                    $.each(r.message, function (i, d) {
                        let row = frm.add_child("sub_assemblies");
                        row.sub_assembly = d.sub_assembly;
                        row.bom_no = d.bom_no;
                        row.required_qty = d.required_qty;
                        row.available_qty = d.available_qty;
                        row.produce_qty = d.produce_qty;
                        row.sub_assembly_warehouse = d.sub_assembly_warehouse;
                    });
                    frm.refresh_field("sub_assemblies");
                    frappe.show_alert(__('Calculated sub-assembly requirements.'));
                } else {
                    frm.refresh_field("sub_assemblies");
                    frappe.msgprint({
                        title: __('Notification'),
                        message: __('No sub-assembly items retrieved or needed for the selected items.'),
                        indicator: 'blue'
                    });
                }
            }
        });
    },


    get_raw_material: function (frm) {
        frappe.call({
            method: "outpost_assessment.outpost_assessment.doctype.production_request.production_request.run_get_raw_material",
            args: {
                doc: frm.doc
            },
            callback: function (r) {
                frm.clear_table("material_requirements");
                if (r.message && r.message.length > 0) {
                    $.each(r.message, function (i, d) {
                        let row = frm.add_child("material_requirements");
                        row.raw_material = d.raw_material;
                        row.item_name = d.item_name;
                        row.required_qty = d.required_qty;
                        row.available_qty = d.available_qty;
                        row.shortage_qty = d.shortage_qty;
                        row.rm_warehouse = d.rm_warehouse;
                    });
                    frm.refresh_field("material_requirements");
                    frappe.show_alert(__('Calculated raw material requirements.'));
                } else {
                    frm.refresh_field("material_requirements");
                    frappe.msgprint({
                        title: __('Notification'),
                        message: __('No raw material items retrieved or needed for the selected items.'),
                        indicator: 'blue'
                    });
                }
            }
        });
    }
});

function render_progress_bar(frm) {
    const $wrapper = frm.get_field('production_progress').$wrapper;
    $wrapper.empty();

    const items = frm.doc.items || [];
    const sub_assemblies = frm.doc.sub_assemblies || [];

    if (!items.length || frm.doc.docstatus === 0) {
        $wrapper.html('<p class="text-muted small" style="padding:6px 0">'
            + __('Progress will be visible after submission.') + '</p>');
        return;
    }

    let blocks_html = '';

    const render_block = function (item_code, item_name, planned, produced, type_label) {
        const pct = planned > 0 ? Math.min(100, produced / planned * 100) : 0;
        const pct_str = pct.toFixed(1);

        let bar_color = '#d1d8e0';          // grey  = 0 %
        if (pct >= 100) bar_color = '#2ecc71';  // green = done
        else if (pct > 0) bar_color = '#5e64ff'; // indigo = in-progress

        const item_label = item_name
            ? `${item_code} <span style="color:#888;font-weight:400">&mdash; ${item_name}</span>`
            : item_code;

        return `
        <div style="margin-bottom:12px">
            <div style="font-size:13px;font-weight:600;margin-bottom:4px">
                <span class="badge" style="margin-right: 5px; background-color: #f0f4f8; color: #4b5563;">${type_label}</span>
                ${item_label}
            </div>
            <div style="position:relative;height:10px;border-radius:5px;background:#eaecef;overflow:hidden">
                <div style="
                    width:${pct_str}%;
                    height:100%;
                    background:${bar_color};
                    border-radius:5px;
                    transition:width 0.6s ease;
                    min-width:${pct > 0 ? '10px' : '0'}
                "></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;color:#6c7680;margin-top:4px">
                <span>${__('Item')} ${item_code}
                    &nbsp;|&nbsp; ${produced} ${__('qty produced')}
                    &nbsp;|&nbsp; ${__('Planned')}: ${planned}
                </span>
                <span style="font-weight:600;color:${bar_color === '#eaecef' ? '#888' : bar_color}">${pct_str}%</span>
            </div>
        </div>`;
    };

    items.forEach(function (row) {
        blocks_html += render_block(
            row.item,
            row.item_name,
            flt(row.production_qty),
            flt(row.produced_qty) || 0,
            __('FG')
        );
    });

    sub_assemblies.forEach(function (row) {
        if (flt(row.produce_qty) > 0) {
            blocks_html += render_block(
                row.sub_assembly,
                '', // SA item name might not be fetched, could use blank or fetch it
                flt(row.produce_qty),
                flt(row.produced_qty) || 0,
                __('Sub-Assembly')
            );
        }
    });

    $wrapper.html(`<div style="padding:8px 2px 2px 2px">${blocks_html}</div>`);
}

frappe.ui.form.on('Production Request Item', {
    item: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.item) {

            if (!row.fg_warehouse && frm.doc.fg_warehouse) {
                frappe.model.set_value(cdt, cdn, 'fg_warehouse', frm.doc.fg_warehouse);
            }

            if (!row.required_date && frm.doc.required_date) {
                frappe.model.set_value(cdt, cdn, 'required_date', frm.doc.required_date);
            }

            let target_wh = row.fg_warehouse || frm.doc.fg_warehouse;
            if (target_wh) {
                frappe.call({
                    method: "outpost_assessment.outpost_assessment.doctype.production_request.production_request.get_available_stock",
                    args: {
                        item_code: row.item,
                        warehouse: target_wh
                    },
                    callback: function (r) {
                        frappe.model.set_value(cdt, cdn, 'available_qty', r.message || 0.0);
                    }
                });
            }
        }
    },
    production_qty: function (frm, cdt, cdn) {
        frm.trigger("get_sub_assembly_items");
        frm.trigger("get_raw_material");
    },
    fg_warehouse: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item && row.fg_warehouse) {
            frappe.call({
                method: "outpost_assessment.outpost_assessment.doctype.production_request.production_request.get_available_stock",
                args: {
                    item_code: row.item,
                    warehouse: row.fg_warehouse
                },
                callback: function (r) {
                    frappe.model.set_value(cdt, cdn, 'available_qty', r.message || 0.0);
                }
            });
        }
    }
});
