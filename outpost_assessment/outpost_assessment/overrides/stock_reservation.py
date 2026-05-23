# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt

@frappe.whitelist()
def check_reservation_status(work_order_name):
    sres = frappe.get_all(
        "Stock Reservation Entry",
        filters={
            "voucher_type": "Work Order",
            "voucher_no": work_order_name,
            "docstatus": 1
        },
        fields=["name", "item_code", "warehouse", "reserved_qty", "status"]
    )
    return {
        "has_reservation": len(sres) > 0,
        "reservations": sres
    }

@frappe.whitelist()
def reserve_stock_for_work_order(work_order_name):
    wo = frappe.get_doc("Work Order", work_order_name)
    if wo.docstatus != 1:
        frappe.throw(_("Work Order must be submitted to reserve stock."))

    existing_sres = check_reservation_status(work_order_name)["reservations"]
    reserved_qtys = {}
    for r in existing_sres:
        reserved_qtys[r["item_code"]] = reserved_qtys.get(r["item_code"], 0.0) + flt(r["reserved_qty"])

    item_codes = list(set(row.item_code for row in wo.required_items if row.item_code))
    
    item_details = {}
    if item_codes:
        items_data = frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "is_stock_item", "stock_uom"]
        )
        item_details = {d.name: d for d in items_data}

    created_any = False
    for row in wo.required_items:
        meta = item_details.get(row.item_code)
        if not meta or not meta.get("is_stock_item"):
            continue

        required_qty = flt(row.required_qty)
        already_reserved = flt(reserved_qtys.get(row.item_code, 0.0))
        qty_to_reserve = required_qty - already_reserved

        if qty_to_reserve <= 0.0:
            continue

        from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import get_available_qty_to_reserve
        available_qty = get_available_qty_to_reserve(row.item_code, row.source_warehouse)

        if available_qty <= 0.0:
            continue

        reserve_qty = min(qty_to_reserve, available_qty)

        sre = frappe.new_doc("Stock Reservation Entry")
        sre.item_code = row.item_code
        sre.warehouse = row.source_warehouse
        sre.voucher_type = "Work Order"
        sre.voucher_no = wo.name
        sre.voucher_detail_no = row.name
        sre.voucher_qty = required_qty
        sre.reserved_qty = reserve_qty
        sre.stock_uom = row.stock_uom or meta.get("stock_uom")
        sre.company = wo.company
        sre.available_qty = available_qty
        sre.insert(ignore_permissions=True)
        sre.submit()
        
        frappe.db.set_value("Work Order Item", row.name, "stock_reserved_qty", already_reserved + reserve_qty)
        
        created_any = True

    if created_any:
        return {"status": "Success", "message": _("Stock reserved successfully.")}
    else:
        return {"status": "No action", "message": _("No items could be reserved (either already fully reserved or out of stock).")}

@frappe.whitelist()
def unreserve_stock_for_work_order(work_order_name):
    sres = frappe.get_all(
        "Stock Reservation Entry",
        filters={
            "voucher_type": "Work Order",
            "voucher_no": work_order_name,
            "docstatus": 1
        },
        fields=["name"]
    )
    for r in sres:
        sre = frappe.get_doc("Stock Reservation Entry", r["name"])
        sre.cancel()
    
    return {"status": "Success", "message": _("Stock unreserved successfully.")}

@frappe.whitelist()
def map_reservations_to_stock_entry(doc, method=None):
    if doc.purpose == "Material Transfer for Manufacture" and doc.work_order:
        sres = frappe.get_all(
            "Stock Reservation Entry",
            filters={
                "voucher_type": "Work Order",
                "voucher_no": doc.work_order,
                "docstatus": 1,
                "status": ["not in", ["Delivered", "Cancelled"]]
            },
            fields=["name", "item_code", "warehouse", "reserved_qty", "delivered_qty", "voucher_detail_no"]
        )
        
        sre_map = {}
        for r in sres:
            key = (r.item_code, r.warehouse)
            if key not in sre_map:
                sre_map[key] = []
            sre_map[key].append(r)
            
        for row in doc.get("items"):
            key = (row.item_code, row.s_warehouse)
            if key in sre_map and not row.get("against_stock_reservation_entry"):
                sre = sre_map[key][0]
                row.against_stock_reservation_entry = sre.name
                row.original_item_name = sre.voucher_detail_no

@frappe.whitelist()
def consume_reservation_on_stock_entry(doc, method=None):
    if doc.purpose == "Material Transfer for Manufacture" and doc.work_order:
        for row in doc.get("items"):
            sre_name = row.get("against_stock_reservation_entry")
            qty_to_consume = flt(row.qty)
            
            if sre_name and qty_to_consume > 0:
                sre_doc = frappe.get_doc("Stock Reservation Entry", sre_name)
                available_to_deliver = flt(sre_doc.reserved_qty) - flt(sre_doc.delivered_qty)
                
                if available_to_deliver > 0:
                    consume_qty = min(qty_to_consume, available_to_deliver)
                    sre_doc.db_set("delivered_qty", flt(sre_doc.delivered_qty) + consume_qty)
                    sre_doc.update_status()
                    sre_doc.update_reserved_stock_in_bin()
                    
                    if sre_doc.voucher_type == "Work Order" and sre_doc.voucher_detail_no:
                        current_reserved = flt(frappe.db.get_value("Work Order Item", sre_doc.voucher_detail_no, "stock_reserved_qty"))
                        frappe.db.set_value("Work Order Item", sre_doc.voucher_detail_no, "stock_reserved_qty", max(0.0, current_reserved - consume_qty))

@frappe.whitelist()
def restore_reservation_on_stock_entry_cancel(doc, method=None):
    if doc.purpose == "Material Transfer for Manufacture" and doc.work_order:
        for row in doc.get("items"):
            sre_name = row.get("against_stock_reservation_entry")
            qty_to_restore = flt(row.qty)
            
            if sre_name and qty_to_restore > 0:
                sre_doc = frappe.get_doc("Stock Reservation Entry", sre_name)
                delivered_qty = flt(sre_doc.delivered_qty)
                
                if delivered_qty > 0:
                    restore_qty = min(qty_to_restore, delivered_qty)
                    sre_doc.db_set("delivered_qty", delivered_qty - restore_qty)
                    sre_doc.update_status()
                    sre_doc.update_reserved_stock_in_bin()
                    
                    if sre_doc.voucher_type == "Work Order" and sre_doc.voucher_detail_no:
                        current_reserved = flt(frappe.db.get_value("Work Order Item", sre_doc.voucher_detail_no, "stock_reserved_qty"))
                        frappe.db.set_value("Work Order Item", sre_doc.voucher_detail_no, "stock_reserved_qty", current_reserved + restore_qty)

@frappe.whitelist()
def reserve_stock_for_production_request(pr_name):
    pr = frappe.get_doc("Production Request", pr_name)
    if pr.docstatus != 1:
        frappe.throw(_("Production Request must be submitted to reserve stock."))

    existing_sres = frappe.get_all(
        "Stock Reservation Entry",
        filters={
            "voucher_type": "Production Request",
            "voucher_no": pr_name,
            "docstatus": 1
        },
        fields=["name", "item_code", "warehouse", "reserved_qty", "status"]
    )
    reserved_qtys = {}
    for r in existing_sres:
        reserved_qtys[r["item_code"]] = reserved_qtys.get(r["item_code"], 0.0) + flt(r["reserved_qty"])

    item_codes = list(set(row.raw_material for row in pr.material_requirements if row.raw_material))
    
    item_details = {}
    if item_codes:
        items_data = frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "is_stock_item", "stock_uom"]
        )
        item_details = {d.name: d for d in items_data}

    created_any = False
    for row in pr.material_requirements:
        meta = item_details.get(row.raw_material)
        if not meta or not meta.get("is_stock_item"):
            continue

        required_qty = flt(row.required_qty)
        already_reserved = flt(reserved_qtys.get(row.raw_material, 0.0))
        qty_to_reserve = required_qty - already_reserved

        if qty_to_reserve <= 0.0:
            continue

        from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import get_available_qty_to_reserve
        available_qty = get_available_qty_to_reserve(row.raw_material, pr.wip_warehouse)

        if available_qty <= 0.0:
            continue

        reserve_qty = min(qty_to_reserve, available_qty)

        sre = frappe.new_doc("Stock Reservation Entry")
        sre.item_code = row.raw_material
        sre.warehouse = pr.wip_warehouse
        sre.voucher_type = "Production Request"
        sre.voucher_no = pr.name
        sre.voucher_detail_no = row.name
        sre.voucher_qty = required_qty
        sre.reserved_qty = reserve_qty
        sre.stock_uom = meta.get("stock_uom")
        sre.company = pr.company
        sre.available_qty = available_qty
        sre.insert(ignore_permissions=True)
        sre.submit()
        created_any = True

    if created_any:
        return {"status": "Success", "message": _("Stock reserved successfully.")}
    else:
        return {"status": "No action", "message": _("No items could be reserved (either already fully reserved or out of stock).")}