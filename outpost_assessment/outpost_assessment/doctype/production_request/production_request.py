import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, today
from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict


class ProductionRequest(Document):
    def validate(self):
        if not self.company:
            self.company = frappe.db.get_single_value("Global Defaults", "default_company") or "Test"
            
        if self.combine_items:
            self.combine_production_items()

        for row in self.items:
            if not row.required_date:
                row.required_date = self.required_date
            if flt(row.production_qty) <= 0:
                frappe.throw(_("Quantity for Item {0} must be greater than zero.").format(row.item))
                    
            if not row.fg_warehouse:
                row.fg_warehouse = self.fg_warehouse

            if not row.bom_no:
                row.bom_no = frappe.db.get_value("BOM", {"item": row.item, "is_active": 1, "docstatus": 1}, "name")

            if not row.bom_no:
                frappe.throw(_("No active and submitted BOM exists for Item: {0}").format(row.item))
            else:
                bom_meta = frappe.db.get_value("BOM", row.bom_no, ["is_active", "docstatus", "item"], as_dict=True)
                if not bom_meta or not bom_meta.is_active or bom_meta.docstatus != 1 or bom_meta.item != row.item:
                    frappe.throw(_("BOM {0} is not active, not submitted, or does not match Item {1}.").format(row.bom_no, row.item))

            row.available_qty = get_available_stock(row.item, row.fg_warehouse)

        self.calculate_material_requirements()

    def combine_production_items(self):
        items_map = {}
        for row in self.items:
            key = (row.item, row.bom_no, row.fg_warehouse)
            if key not in items_map:
                items_map[key] = {
                    "item": row.item,
                    "bom_no": row.bom_no,
                    "fg_warehouse": row.fg_warehouse,
                    "production_qty": 0.0,
                    "required_date": row.required_date
                }
            items_map[key]["production_qty"] += flt(row.production_qty)
            if row.required_date and (not items_map[key]["required_date"] or row.required_date < items_map[key]["required_date"]):
                items_map[key]["required_date"] = row.required_date

        self.set("items", [])
        for key, data in items_map.items():
            self.append("items", data)

    def get_cached_bom(self, item_code):
        if not hasattr(self, "_bom_cache"):
            self._bom_cache = {}
        if item_code not in self._bom_cache:
            bom_no = frappe.db.get_value("BOM", {"item": item_code, "is_active": 1, "docstatus": 1}, "name")
            self._bom_cache[item_code] = bom_no
        return self._bom_cache[item_code]

    def get_cached_stock(self, item_code, warehouse):
        if not hasattr(self, "_stock_cache"):
            self._stock_cache = {}
        key = (item_code, warehouse)
        if key not in self._stock_cache:
            self._stock_cache[key] = get_available_stock(item_code, warehouse)
        return self._stock_cache[key]

    def resolve_requirements(self, item_code, bom_no, qty, use_existing_sub_stock, rm_warehouse, sub_assembly_warehouse, raw_materials, sub_assemblies):
        if not bom_no:
            return

        bom_doc = frappe.get_doc("BOM", bom_no)
        bom_qty = flt(bom_doc.quantity) or 1.0

        for bom_item in bom_doc.items:
            if not bom_item.item_code:
                continue

            item_qty_needed = (flt(bom_item.qty) / bom_qty) * qty
            child_bom = self.get_cached_bom(bom_item.item_code)

            if child_bom:
                # It is a sub-assembly
                available_stock = self.get_cached_stock(bom_item.item_code, sub_assembly_warehouse)
                
                produce_qty = item_qty_needed
                if use_existing_sub_stock:
                    consumed_stock = min(item_qty_needed, available_stock)
                    produce_qty = max(0.0, item_qty_needed - consumed_stock)
                    self._stock_cache[(bom_item.item_code, sub_assembly_warehouse)] -= consumed_stock

                key = (bom_item.item_code, child_bom)
                if key not in sub_assemblies:
                    sub_assemblies[key] = {
                        "sub_assembly": bom_item.item_code,
                        "bom_no": child_bom,
                        "required_qty": 0.0,
                        "available_qty": available_stock,
                        "produce_qty": 0.0,
                        "sub_assembly_warehouse": sub_assembly_warehouse
                    }
                sub_assemblies[key]["required_qty"] += item_qty_needed
                sub_assemblies[key]["produce_qty"] = max(0.0, sub_assemblies[key]["required_qty"] - available_stock) if use_existing_sub_stock else sub_assemblies[key]["required_qty"]

                if produce_qty > 0.0:
                    self.resolve_requirements(
                        bom_item.item_code,
                        child_bom,
                        produce_qty,
                        use_existing_sub_stock,
                        rm_warehouse,
                        sub_assembly_warehouse,
                        raw_materials,
                        sub_assemblies
                    )
            else:
                # It is a raw material
                if bom_item.item_code not in raw_materials:
                    available_stock = self.get_cached_stock(bom_item.item_code, rm_warehouse)
                    raw_materials[bom_item.item_code] = {
                        "raw_material": bom_item.item_code,
                        "item_name": bom_item.item_name,
                        "required_qty": 0.0,
                        "available_qty": available_stock,
                        "shortage_qty": 0.0,
                        "rm_warehouse": rm_warehouse
                    }
                raw_materials[bom_item.item_code]["required_qty"] += item_qty_needed
                raw_materials[bom_item.item_code]["shortage_qty"] = max(0.0, raw_materials[bom_item.item_code]["required_qty"] - raw_materials[bom_item.item_code]["available_qty"])

    def calculate_material_requirements(self):
        self.set("material_requirements", [])
        self.set("sub_assemblies", [])
        
        self._bom_cache = {}
        self._stock_cache = {}
        
        raw_materials = {}
        sub_assemblies = {}
        
        for row in self.items:
            if not row.bom_no:
                continue
            
            self.resolve_requirements(
                row.item,
                row.bom_no,
                flt(row.production_qty),
                self.use_existing_sub_assembly_stock,
                self.rm_warehouse,
                self.sub_assembly_warehouse,
                raw_materials,
                sub_assemblies
            )
            
        for key, details in raw_materials.items():
            self.append("material_requirements", details)
            
        for key, details in sub_assemblies.items():
            self.append("sub_assemblies", details)

    def on_submit(self):
        self.calculate_material_requirements()

        shortages = []
        if self.material_requirements:
            rm_items = [row.raw_material for row in self.material_requirements if flt(row.shortage_qty) > 0]
            bom_ids = [pr_item.bom_no for pr_item in self.items if pr_item.bom_no]
            
            bom_items_exists = []
            if rm_items and bom_ids:
                bom_items_exists = frappe.get_all(
                    "BOM Item",
                    filters={"parent": ["in", bom_ids], "item_code": ["in", rm_items]},
                    fields=["parent", "item_code"]
                )
            
            for row in self.material_requirements:
                if flt(row.shortage_qty) > 0:
                    needed_for = []
                    for pr_item in self.items:
                        if pr_item.bom_no and any(x.parent == pr_item.bom_no and x.item_code == row.raw_material for x in bom_items_exists):
                            needed_for.append(pr_item.item)
                            
                    shortages.append({
                        "item_code": row.raw_material,
                        "item_name": row.item_name,
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
                _("<b>Submission blocked:</b> Raw material stock is insufficient for this Production Request. Please procure the missing quantities:<br><br>{0}").format(shortage_html),
                title=_("Stock Shortages Blocked Submission")
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
                
                wo.wip_warehouse = self.wip_warehouse
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
                
                wo.wip_warehouse = self.wip_warehouse
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

        if created_wos or created_sub_wos:
            msg_html = f"<div style='margin-bottom: 15px;'>{_('The following Work Orders have been successfully created and submitted:')}</div>"
            msg_html += "<table class='table table-bordered' style='width: 100%; border-collapse: collapse; border: 1px solid #d1d8e0;'>"
            msg_html += f"<tr style='background-color: #f5f6fa;'><th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Type')}</th><th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Work Order')}</th><th style='padding: 10px; border: 1px solid #d1d8e0; text-align: left;'>{_('Item')}</th></tr>"
            
            for wo in created_wos:
                msg_html += f"<tr><td style='padding: 10px; border: 1px solid #d1d8e0;'>{_('Finished Good')}</td><td style='padding: 10px; border: 1px solid #d1d8e0;'><b><a href='/app/work-order/{wo['wo']}'>{wo['wo']}</a></b></td><td style='padding: 10px; border: 1px solid #d1d8e0;'>{wo['item']}</td></tr>"
            for wo in created_sub_wos:
                msg_html += f"<tr><td style='padding: 10px; border: 1px solid #d1d8e0;'>{_('Sub Assembly')}</td><td style='padding: 10px; border: 1px solid #d1d8e0;'><b><a href='/app/work-order/{wo['wo']}'>{wo['wo']}</a></b></td><td style='padding: 10px; border: 1px solid #d1d8e0;'>{wo['item']}</td></tr>"
            
            msg_html += "</table>"
            msg_html += f"<div class='text-success' style='margin-top: 15px; font-weight: bold; color: #2ecc71;'><i class='fa fa-check'></i> {_('Raw materials reserved successfully for linked Work Orders in Stores warehouse.')}</div>"
            
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


def update_production_request_status(doc, method=None):
    parent_name = doc.get("production_request")
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
    item_codes = list(set(item.item_code for item in items if item.item_code))
    
    if item_codes:
        item_groups = dict(frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=["name", "item_group"], as_list=1))
        boms = frappe.get_all("BOM", filters={"item": ["in", item_codes], "is_active": 1, "docstatus": 1}, fields=["name", "item"])
        bom_map = {b.item: b.name for b in boms}
        
        for item in items:
            group = item_groups.get(item.item_code)
            if group in ("Product", "Products"):
                has_bom = bom_map.get(item.item_code)
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
    item_codes = list(set(item.item_code for item in items if item.item_code))
    
    if item_codes:
        item_groups = dict(frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=["name", "item_group"], as_list=1))
        boms = frappe.get_all("BOM", filters={"item": ["in", item_codes], "is_active": 1, "docstatus": 1}, fields=["name", "item"])
        bom_map = {b.item: b.name for b in boms}
        
        for item in items:
            group = item_groups.get(item.item_code)
            if group in ("Product", "Products"):
                has_bom = bom_map.get(item.item_code)
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
    d.calculate_material_requirements()
    return d.get("sub_assemblies")


@frappe.whitelist()
def run_get_raw_material(doc):
    d = frappe.get_doc(frappe.parse_json(doc))
    d.calculate_material_requirements()
    return d.get("material_requirements")



@frappe.whitelist()
def create_material_request_for_shortages(docname):
    pr = frappe.get_doc("Production Request", docname)
    if not pr.material_requirements:
        frappe.throw(_("No raw material requirements calculated for this Production Request."))

    shortages = [row for row in pr.material_requirements if flt(row.shortage_qty) > 0.0]
    if not shortages:
        frappe.msgprint(_("No material shortages exist. Sufficient stock is available for all required raw materials."))
        return None

    existing_mr = frappe.db.get_value(
        "Material Request Item",
        {"production_request": docname, "docstatus": ["!=", 2]},
        "parent"
    )
    if existing_mr:
        frappe.throw(
            _("A Material Request <b><a href='/app/material-request/{0}'>{0}</a></b> already exists for this Production Request. Cancel it first before creating a new one.").format(existing_mr),
            title=_("Duplicate Material Request")
        )

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = pr.company
    mr.transaction_date = today()
    mr.schedule_date = pr.required_date or today()

    for item in shortages:
        mr.append("items", {
            "item_code": item.raw_material,
            "qty": item.shortage_qty,
            "uom": frappe.db.get_value("Item", item.raw_material, "stock_uom"),
            "schedule_date": pr.required_date,
            "warehouse": item.rm_warehouse,
            "production_request": pr.name
        })

    mr.remarks = _("Created automatically for shortage in Production Request: {0}").format(pr.name)
    mr.insert()
    mr.submit()

    return mr.name