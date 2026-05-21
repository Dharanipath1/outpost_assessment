# -*- coding: utf-8 -*-

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, today

class ProductionRequest(Document):
    def validate(self):
        if not self.company:
            self.company = frappe.db.get_single_value("Global Defaults", "default_company") or "Test"
            
        if not self.posting_date:
            self.posting_date = today()
        if not self.posting_time:
            self.posting_time = now_datetime().strftime("%H:%M:%S")
        if not self.required_date:
            self.required_date = self.posting_date or today()

        if not self.items:
            frappe.throw(_("Please add at least one Item to the Production Items table."))

        for row in self.items:
            if not row.required_date:
                row.required_date = self.required_date
            if flt(row.production_qty) <= 0:
                frappe.throw(_("Quantity for Item {0} must be greater than zero.").format(row.item))
                
            if not row.item_name or not row.stock_uom:
                details = frappe.db.get_value("Item", row.item, ["item_name", "stock_uom"], as_dict=True)
                if details:
                    row.item_name = details.item_name
                    row.stock_uom = details.stock_uom
                    
            if not row.fg_warehouse:
                row.fg_warehouse = self.fg_warehouse

            if not row.bom_no:
                row.bom_no = frappe.db.get_value("BOM", {"item": row.item, "is_active": 1, "docstatus": 1}, "name")

            if self.docstatus == 1 and not row.bom_no:
                frappe.throw(_("No active and submitted BOM exists for Item: {0}").format(row.item))

            row.available_qty = get_available_stock(row.item, row.fg_warehouse)

        self.calculate_material_requirements()

    def calculate_material_requirements(self):
        self.set("material_requirements", [])
        self.set("sub_assemblies", [])
        
        requirements = {}
        sub_assemblies_map = {}
        sub_assemblies_flat_list = []
        
        parent_items = [row.item for row in self.items]
        
        for row in self.items:
            if not row.bom_no:
                continue
            row_fg_wh = row.fg_warehouse or self.fg_warehouse
            
            get_bom_requirements_by_bom(row.bom_no, flt(row.production_qty), self.rm_warehouse, row_fg_wh, self.sub_assembly_warehouse, True, requirements)
            
            if row.bom_no:
                bom_doc = frappe.get_doc("BOM", row.bom_no)
                bom_qty = flt(bom_doc.quantity) or 1.0
                available_fg_stock = get_available_stock(row.item, row_fg_wh)
                net_fg_needed = flt(row.production_qty)
                
                if net_fg_needed > 0.0:
                    for bom_item in bom_doc.items:
                        item_qty_needed = (flt(bom_item.qty) / bom_qty) * net_fg_needed
                        child_bom = frappe.db.get_value("BOM", {"item": bom_item.item_code, "is_active": 1, "docstatus": 1}, "name")
                        if child_bom:
                            get_sub_assemblies_flat(bom_item.item_code, item_qty_needed, self.sub_assembly_warehouse, sub_assemblies_flat_list)
                
        for raw_mat, req_qty in requirements.items():
            if raw_mat in parent_items:
                continue
            avail_qty = get_available_stock(raw_mat, self.rm_warehouse)
            shortage = max(0.0, req_qty - avail_qty)
            self.append("material_requirements", {
                "raw_material": raw_mat,
                "item_name": frappe.db.get_value("Item", raw_mat, "item_name"),
                "required_qty": req_qty,
                "available_qty": avail_qty,
                "shortage_qty": shortage,
                "rm_warehouse": self.rm_warehouse
            })
            
        for item in sub_assemblies_flat_list:
            self.append("sub_assemblies", {
                "sub_assembly": item["sub_assembly"],
                "bom_no": item["bom_no"],
                "required_qty": item["required_qty"],
                "available_qty": item["available_qty"],
                "produce_qty": item["produce_qty"],
                "sub_assembly_warehouse": self.sub_assembly_warehouse
            })

    def on_submit(self):
        self.calculate_material_requirements()

        shortages = []
        for row in self.material_requirements:
            if flt(row.shortage_qty) > 0:
                needed_for = []
                for pr_item in self.items:
                    if pr_item.bom_no and frappe.db.exists("BOM Item", {"parent": pr_item.bom_no, "item_code": row.raw_material}):
                        needed_for.append(pr_item.item)
                        
                shortages.append({
                    "item_code": row.raw_material,
                    "item_name": row.item_name or frappe.db.get_value("Item", row.raw_material, "item_name"),
                    "required_qty": row.required_qty,
                    "available_qty": row.available_qty,
                    "shortage_qty": row.shortage_qty,
                    "used_by": ", ".join(list(set(needed_for)))
                })

        if shortages:
            shortage_html = (
                "<style>.modal-dialog { max-width: 900px !important; width: 80vw !important; }</style>"
                "<table class='table table-bordered' style='width:100%; border-collapse: collapse; border: 1px solid #d1d8e0;'>"
            )
            shortage_html += (
                f"<tr style='background-color: #f5f6fa;'>"
                f"<th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Raw Material')}</th>"
                f"<th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Item Name')}</th>"
                f"<th style='padding: 10px; border: 1px solid #d1d8e0; text-align: right;'>{_('Required Qty')}</th>"
                f"<th style='padding: 10px; border: 1px solid #d1d8e0; text-align: right;'>{_('Available Qty')}</th>"
                f"<th style='padding: 10px; border: 1px solid #d1d8e0; text-align: right; color: #e74c3c;'>{_('Shortage')}</th>"
                f"</tr>"
            )
            for s in shortages:
                shortage_html += (
                    f"<tr>"
                    f"<td style='padding: 10px; border: 1px solid #d1d8e0;'><b>{s['item_code']}</b></td>"
                    f"<td style='padding: 10px; border: 1px solid #d1d8e0;'>{s['item_name'] or ''}</td>"
                    f"<td style='padding: 10px; border: 1px solid #d1d8e0; text-align: right;'>{s['required_qty']:.2f}</td>"
                    f"<td style='padding: 10px; border: 1px solid #d1d8e0; text-align: right;'>{s['available_qty']:.2f}</td>"
                    f"<td style='padding: 10px; border: 1px solid #d1d8e0; text-align: right; color: #e74c3c; font-weight: bold;'>{s['shortage_qty']:.2f}</td>"
                    f"</tr>"
                )
            shortage_html += "</table>"
            
            frappe.throw(
                _("Cannot submit Production Request due to raw material stock shortages:<br><br>{0}").format(shortage_html),
                title=_("Stock Shortage Alert"),
                wide=True
            )

        created_wos = []
        created_sub_wos = []

        for row in self.items:
            try:
                wo = frappe.new_doc("Work Order")
                wo.production_item = row.item
                wo.bom_no = row.bom_no
                wo.qty = row.production_qty
                wo.company = self.company
                wo.expected_delivery_date = row.required_date
                wo.planned_start_date = now_datetime()
                
                wo.wip_warehouse = get_warehouse("wip", self.company)
                wo.fg_warehouse = row.fg_warehouse or self.fg_warehouse
                wo.source_warehouse = self.rm_warehouse
                wo.reserve_stock = 1
                wo.production_request = self.name
                wo.production_request_item = row.name
                
                wo.description = _("Automatically created via Production Request: {0}").format(self.name)
                
                wo.insert()
                wo.submit()

                from outpost_assessment.outpost_assessment.overrides.stock_reservation import reserve_stock_for_work_order
                reserve_stock_for_work_order(wo.name)

                created_wos.append({"wo": wo.name, "item": row.item})
            except Exception as e:
                frappe.throw(_("Failed to automatically create and submit Work Order for Item {0}: {1}").format(row.item, str(e)))

        for row in self.sub_assemblies:
            if flt(row.produce_qty) <= 0.0:
                continue
                
            try:
                wo = frappe.new_doc("Work Order")
                wo.production_item = row.sub_assembly
                wo.bom_no = row.bom_no
                wo.qty = row.produce_qty
                wo.company = self.company
                wo.expected_delivery_date = self.required_date
                wo.planned_start_date = now_datetime()
                
                wo.wip_warehouse = get_warehouse("wip", self.company)
                wo.fg_warehouse = row.sub_assembly_warehouse or self.sub_assembly_warehouse
                wo.source_warehouse = self.rm_warehouse
                wo.reserve_stock = 1
                wo.production_request = self.name
                wo.production_request_sub_assembly = row.name
                
                wo.description = _("Automatically created as Sub Assembly via Production Request: {0}").format(self.name)
                
                wo.insert()
                wo.submit()

                from outpost_assessment.outpost_assessment.overrides.stock_reservation import reserve_stock_for_work_order
                reserve_stock_for_work_order(wo.name)

                created_sub_wos.append({"wo": wo.name, "item": row.sub_assembly})
            except Exception as e:
                frappe.throw(_("Failed to automatically create and submit Sub Assembly Work Order for Item {0}: {1}").format(row.sub_assembly, str(e)))

        pr_reservation_success = False
        try:
            from outpost_assessment.outpost_assessment.overrides.stock_reservation import reserve_stock_for_production_request
            res = reserve_stock_for_production_request(self.name)
            if res.get("status") == "Success":
                pr_reservation_success = True
        except Exception as e:
            frappe.log_error(message=frappe.get_traceback(), title="Production Request Stock Reservation Failed")
            frappe.msgprint(_("Failed to reserve stock for Production Request: {0}").format(str(e)), indicator="orange")

        if created_wos or created_sub_wos or pr_reservation_success:
            msg_html = f"<div style='margin-bottom: 15px;'>{_('The following Work Orders have been successfully created and submitted:')}</div>"
            msg_html += "<table class='table table-bordered' style='width: 100%; border-collapse: collapse; border: 1px solid #d1d8e0;'>"
            msg_html += f"<tr style='background-color: #f5f6fa;'><th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Type')}</th><th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Work Order')}</th><th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Item')}</th></tr>"
            
            for wo in created_wos:
                msg_html += f"<tr><td style='padding: 10px; border: 1px solid #d1d8e0;'>{_('Finished Good')}</td><td style='padding: 10px; border: 1px solid #d1d8e0;'><b><a href='/app/work-order/{wo['wo']}'>{wo['wo']}</a></b></td><td style='padding: 10px; border: 1px solid #d1d8e0;'>{wo['item']}</td></tr>"
            for wo in created_sub_wos:
                msg_html += f"<tr><td style='padding: 10px; border: 1px solid #d1d8e0;'>{_('Sub Assembly')}</td><td style='padding: 10px; border: 1px solid #d1d8e0;'><b><a href='/app/work-order/{wo['wo']}'>{wo['wo']}</a></b></td><td style='padding: 10px; border: 1px solid #d1d8e0;'>{wo['item']}</td></tr>"
            
            msg_html += "</table>"
            if pr_reservation_success:
                msg_html += f"<div class='text-success' style='margin-top: 15px; font-weight: bold; color: #2ecc71;'><i class='fa fa-check'></i> {_('Raw materials reserved successfully for Production Request in WIP warehouse.')}</div>"
            
            frappe.msgprint(msg_html, title=_("Submission Successful"), indicator="green", wide=True)

        self.db_set("status", "Not Started")

    def on_cancel(self):
        wos = frappe.get_all("Work Order", filters={
            "description": ["like", f"%Production Request: {self.name}%"],
            "docstatus": ["<", 2]
        })
        
        for wo_ref in wos:
            wo_status = frappe.db.get_value("Work Order", wo_ref.name, "status")
            if wo_status in ["In Progress", "Completed"]:
                frappe.throw(_("Cannot cancel Production Request because linked Work Order {0} is already {1}.").format(wo_ref.name, wo_status))

        for wo_ref in wos:
            try:
                wo = frappe.get_doc("Work Order", wo_ref.name)
                if wo.docstatus == 1:
                    wo.cancel()
            except Exception as e:
                frappe.throw(_("Failed to cancel linked Work Order {0}: {1}").format(wo_ref.name, str(e)))

        self.db_set("status", "Cancelled")


def get_warehouse(warehouse_type, company):
    w = None
    if warehouse_type == "wip":
        w = frappe.db.get_value("Warehouse", {"company": company, "name": ["like", "%Work In Progress%"], "is_group": 0}, "name")
        if not w:
            w = frappe.db.get_value("Warehouse", {"company": company, "name": ["like", "%WIP%"], "is_group": 0}, "name")
    elif warehouse_type == "fg":
        w = frappe.db.get_value("Warehouse", {"company": company, "name": ["like", "%Finished Goods%"], "is_group": 0}, "name")
        if not w:
            w = frappe.db.get_value("Warehouse", {"company": company, "name": ["like", "%FG%"], "is_group": 0}, "name")
    elif warehouse_type == "source":
        w = frappe.db.get_value("Warehouse", {"company": company, "name": ["like", "%Stores%"], "is_group": 0}, "name")
        if not w:
            w = frappe.db.get_value("Warehouse", {"company": company, "name": ["like", "%Raw Material%"], "is_group": 0}, "name")

    if not w:
        w = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
    
    return w


@frappe.whitelist()
def get_available_stock(item_code=None, warehouse=None):
    if not item_code:
        return 0.0
    from frappe.query_builder.functions import Sum
    bin_tb = frappe.qb.DocType("Bin")
    query = frappe.qb.from_(bin_tb).select(
        Sum(
            bin_tb.actual_qty - 
            bin_tb.reserved_qty - 
            bin_tb.reserved_qty_for_production - 
            bin_tb.reserved_qty_for_sub_contract - 
            bin_tb.reserved_qty_for_production_plan - 
            bin_tb.reserved_stock
        )
    )
    if warehouse:
        query = query.where((bin_tb.item_code == item_code) & (bin_tb.warehouse == warehouse))
    else:
        query = query.where(bin_tb.item_code == item_code)
    
    result = query.run()
    if result and result[0][0] is not None:
        return max(0.0, flt(result[0][0]))
    return 0.0


def get_bom_requirements_by_bom(bom_no, qty_needed, rm_warehouse, fg_warehouse, sub_assembly_warehouse, is_top_level=True, requirements=None):
    if requirements is None:
        requirements = {}
        
    if not bom_no:
        return requirements
        
    bom_doc = frappe.get_doc("BOM", bom_no)
    bom_qty = flt(bom_doc.quantity) or 1.0
    
    target_wh = fg_warehouse if is_top_level else sub_assembly_warehouse
    available_stock = get_available_stock(bom_doc.item, target_wh)
    net_needed = qty_needed
    
    if net_needed > 0.0:
        for bom_item in bom_doc.items:
            item_qty_needed = (flt(bom_item.qty) / bom_qty) * net_needed
            child_bom = frappe.db.get_value("BOM", {"item": bom_item.item_code, "is_active": 1, "docstatus": 1}, "name")
            if child_bom:
                get_bom_requirements_by_bom(child_bom, item_qty_needed, rm_warehouse, fg_warehouse, sub_assembly_warehouse, False, requirements)
            else:
                if bom_item.item_code not in requirements:
                    requirements[bom_item.item_code] = 0.0
                requirements[bom_item.item_code] += item_qty_needed
                
    return requirements


def get_sub_assemblies(item_code, qty_needed, sub_assembly_warehouse, sub_assemblies=None):
    if sub_assemblies is None:
        sub_assemblies = {}
        
    bom_no = frappe.db.get_value("BOM", {"item": item_code, "is_active": 1, "docstatus": 1}, "name")
    if not bom_no:
        return sub_assemblies
        
    available_stock = get_available_stock(item_code, sub_assembly_warehouse)
    
    net_needed = max(0.0, qty_needed - available_stock)
    
    if item_code not in sub_assemblies:
        sub_assemblies[item_code] = {
            "bom_no": bom_no,
            "required_qty": 0.0,
            "available_qty": available_stock,
        }
    sub_assemblies[item_code]["required_qty"] += qty_needed
    
    if net_needed > 0.0:
        bom_doc = frappe.get_doc("BOM", bom_no)
        bom_qty = flt(bom_doc.quantity) or 1.0
        for bom_item in bom_doc.items:
            item_qty_needed = (flt(bom_item.qty) / bom_qty) * net_needed
            child_bom = frappe.db.get_value("BOM", {"item": bom_item.item_code, "is_active": 1, "docstatus": 1}, "name")
            if child_bom:
                get_sub_assemblies(bom_item.item_code, item_qty_needed, sub_assembly_warehouse, sub_assemblies)
                
    return sub_assemblies


def get_sub_assemblies_flat(item_code, qty_needed, sub_assembly_warehouse, lst=None):
    if lst is None:
        lst = []
        
    bom_no = frappe.db.get_value("BOM", {"item": item_code, "is_active": 1, "docstatus": 1}, "name")
    if not bom_no:
        return lst
        
    available_stock = get_available_stock(item_code, sub_assembly_warehouse)
    net_needed = qty_needed
    
    lst.append({
        "sub_assembly": item_code,
        "bom_no": bom_no,
        "required_qty": qty_needed,
        "available_qty": available_stock,
        "produce_qty": qty_needed
    })
    
    if net_needed > 0.0:
        bom_doc = frappe.get_doc("BOM", bom_no)
        bom_qty = flt(bom_doc.quantity) or 1.0
        for bom_item in bom_doc.items:
            item_qty_needed = (flt(bom_item.qty) / bom_qty) * net_needed
            child_bom = frappe.db.get_value("BOM", {"item": bom_item.item_code, "is_active": 1, "docstatus": 1}, "name")
            if child_bom:
                get_sub_assemblies_flat(bom_item.item_code, item_qty_needed, sub_assembly_warehouse, lst)
                
    return lst


def update_production_request_status(doc, method=None):
    """
    Hook function triggered when a Work Order is updated.
    Dynamically tracks produced_qty and updates the Production Request status.
    """
    parent_name = doc.get("production_request")
    if not parent_name:
        if doc.description:
            import re
            match = re.search(r"Production Request:\s*([A-Za-z0-9\-\.]+)", doc.description)
            if match:
                parent_name = match.group(1).strip()
                
    if not parent_name or not frappe.db.exists("Production Request", parent_name):
        return

    parent_doc = frappe.get_doc("Production Request", parent_name)
    if parent_doc.status in ["Cancelled", "Draft"]:
        return

    for row in parent_doc.items:
        wos = frappe.get_all("Work Order", 
            filters={
                "description": ["like", f"%Production Request: {parent_name}%"],
                "production_item": row.item,
                "docstatus": ["<", 2]
            }, 
            fields=["produced_qty"]
        )
        item_produced = sum(flt(w.produced_qty) for w in wos)
        frappe.db.set_value("Production Request Item", row.name, "produced_qty", item_produced)
        
    for row in parent_doc.sub_assemblies:
        wos = frappe.get_all("Work Order", 
            filters={
                "description": ["like", f"%Production Request: {parent_name}%"],
                "production_item": row.sub_assembly,
                "docstatus": ["<", 2]
            }, 
            fields=["produced_qty"]
        )
        item_produced = sum(flt(w.produced_qty) for w in wos)
        frappe.db.set_value("Production Request Sub Assembly", row.name, "produced_qty", item_produced)
        
    all_wos = frappe.get_all("Work Order", 
        filters={
            "description": ["like", f"%Production Request: {parent_name}%"],
            "docstatus": ["<", 2]
        }, 
        fields=["name", "status"]
    )
    
    total_wos = len(all_wos)
    if total_wos > 0:
        completed_wos = sum(1 for w in all_wos if w.status == "Completed")
        in_process_wos = sum(1 for w in all_wos if w.status == "In Process")
        
        new_status = parent_doc.status
        if completed_wos == total_wos:
            new_status = "Completed"
        elif completed_wos > 0:
            new_status = "Partially Completed"
        elif in_process_wos == total_wos:
            new_status = "In Process"
        elif in_process_wos > 0:
            new_status = "Partially Started"
        else:
            new_status = "Not Started"
            
        if parent_doc.status != new_status:
            parent_doc.db_set("status", new_status)
            frappe.logger().info(f"Production Request {parent_name} status updated to {new_status}")

def update_pr_status_from_stock_entry(doc, method=None):
    """
    Hook function triggered when a Stock Entry is submitted or cancelled.
    If the Stock Entry is linked to a Work Order, re-evaluate the Production Request status.
    """
    if doc.work_order:
        try:
            wo_doc = frappe.get_doc("Work Order", doc.work_order)
            update_production_request_status(wo_doc)
        except Exception:
            pass


@frappe.whitelist()
def get_items_from_sales_order(sales_order):
    if not frappe.db.exists("Sales Order", sales_order):
        return []
        
    items = frappe.db.get_all(
        "Sales Order Item",
        filters={"parent": sales_order},
        fields=["item_code", "qty", "delivery_date", "item_name", "uom"]
    )
    
    valid_items = []
    for item in items:
        item_group = frappe.db.get_value("Item", item.item_code, "item_group")
        if item_group in ("Product", "Products"):
            has_bom = frappe.db.exists("BOM", {"item": item.item_code, "is_active": 1, "docstatus": 1})
            if has_bom:
                valid_items.append({
                    "item": item.item_code,
                    "item_name": item.item_name,
                    "stock_uom": item.uom,
                    "production_qty": item.qty,
                    "required_date": item.delivery_date or today(),
                    "bom_no": has_bom
                })
            
    return valid_items


@frappe.whitelist()
def get_items_from_material_request(material_request):
    if not frappe.db.exists("Material Request", material_request):
        return []
        
    items = frappe.db.get_all(
        "Material Request Item",
        filters={"parent": material_request},
        fields=["item_code", "qty", "schedule_date", "item_name", "uom"]
    )
    
    valid_items = []
    for item in items:
        item_group = frappe.db.get_value("Item", item.item_code, "item_group")
        if item_group in ("Product", "Products"):
            has_bom = frappe.db.exists("BOM", {"item": item.item_code, "is_active": 1, "docstatus": 1})
            if has_bom:
                valid_items.append({
                    "item": item.item_code,
                    "item_name": item.item_name,
                    "stock_uom": item.uom,
                    "production_qty": item.qty,
                    "required_date": item.schedule_date or today(),
                    "bom_no": has_bom
                })
            
    return valid_items



@frappe.whitelist()
def run_get_sub_assembly_items(doc):
    d = frappe.get_doc(frappe.parse_json(doc))
    d.set("sub_assemblies", [])
    sub_assemblies_map = {}
    sub_assemblies_flat_list = []
    
    for row in d.items:
        if not row.bom_no:
            continue
        row_fg_wh = row.fg_warehouse or d.fg_warehouse
        bom_doc = frappe.get_doc("BOM", row.bom_no)
        bom_qty = flt(bom_doc.quantity) or 1.0
        available_fg_stock = get_available_stock(row.item, row_fg_wh)
        net_fg_needed = flt(row.production_qty)
        
        if net_fg_needed > 0.0:
            for bom_item in bom_doc.items:
                item_qty_needed = (flt(bom_item.qty) / bom_qty) * net_fg_needed
                child_bom = frappe.db.get_value("BOM", {"item": bom_item.item_code, "is_active": 1, "docstatus": 1}, "name")
                if child_bom:
                    get_sub_assemblies_flat(bom_item.item_code, item_qty_needed, d.sub_assembly_warehouse, sub_assemblies_flat_list)

    for item in sub_assemblies_flat_list:
        d.append("sub_assemblies", {
            "sub_assembly": item["sub_assembly"],
            "bom_no": item["bom_no"],
            "required_qty": item["required_qty"],
            "available_qty": item["available_qty"],
            "produce_qty": item["produce_qty"],
            "sub_assembly_warehouse": d.sub_assembly_warehouse
        })
        
    return d.get("sub_assemblies")





@frappe.whitelist()
def run_get_raw_material(doc):
    d = frappe.get_doc(frappe.parse_json(doc))
    d.set("material_requirements", [])
    requirements = {}
    parent_items = [row.item for row in d.items]
    
    for row in d.items:
        if not row.bom_no:
            continue
        row_fg_wh = row.fg_warehouse or d.fg_warehouse
        get_bom_requirements_by_bom(row.bom_no, flt(row.production_qty), d.rm_warehouse, row_fg_wh, d.sub_assembly_warehouse, True, requirements)
        
    for raw_mat, req_qty in requirements.items():
        if raw_mat in parent_items:
            continue
        avail_qty = get_available_stock(raw_mat, d.rm_warehouse)
        shortage = max(0.0, req_qty - avail_qty)
        d.append("material_requirements", {
            "raw_material": raw_mat,
            "item_name": frappe.db.get_value("Item", raw_mat, "item_name"),
            "required_qty": req_qty,
            "available_qty": avail_qty,
            "shortage_qty": shortage,
            "rm_warehouse": d.rm_warehouse
        })
        
    return d.get("material_requirements")




@frappe.whitelist()
def item_query_filter(doctype, txt, searchfield, start, page_len, filters):
    bom = frappe.qb.DocType("BOM")
    item = frappe.qb.DocType("Item")
    
    query = (
        frappe.qb.from_(item)
        .join(bom)
        .on(bom.item == item.name)
        .select(item.name, item.item_name)
        .where(
            (bom.is_active == 1)
            & (bom.docstatus == 1)
            & ((item.item_group == "Product") | (item.item_group == "Products"))
        )
        .distinct()
    )
    
    if txt:
        query = query.where(
            (item.name.like(f"%{txt}%")) | (item.item_name.like(f"%{txt}%"))
        )
        
    query = query.orderby(item.name).limit(page_len).offset(start)
    return query.run()
