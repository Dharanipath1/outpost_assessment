# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data, None, None, None

def get_columns():
    return [
        {
            "fieldname": "production_request",
            "label": _("Production Request"),
            "fieldtype": "Link",
            "options": "Production Request",
            "width": 180
        },
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150
        },
        {
            "fieldname": "priority",
            "label": _("Priority"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "item_code",
            "label": _("Item"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "required_date",
            "label": _("Required Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "age",
            "label": _("Age (Days)"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "planned_qty",
            "label": _("Planned Qty"),
            "fieldtype": "Float",
            "width": 110
        },
        {
            "fieldname": "completed_qty",
            "label": _("Produced Qty"),
            "fieldtype": "Float",
            "width": 110
        },
        {
            "fieldname": "pending_qty",
            "label": _("Pending Qty"),
            "fieldtype": "Float",
            "width": 110
        },
        {
            "fieldname": "progress",
            "label": _("Progress (%)"),
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "fieldname": "shortages",
            "label": _("Material Shortages"),
            "fieldtype": "Text",
            "width": 250
        }
    ]

def get_data(filters):
    conditions = ["docstatus < 2", "status != 'Cancelled'"] # Include Draft and Submitted documents, exclude Cancelled
    values = {}
    
    if filters and filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters.get("company")

    if filters and filters.get("from_date"):
        conditions.append("posting_date >= %(from_date)s")
        values["from_date"] = filters.get("from_date")
        
    if filters and filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")
        
    if filters and filters.get("customer"):
        conditions.append("customer = %(customer)s")
        values["customer"] = filters.get("customer")
        
    if filters and filters.get("priority"):
        conditions.append("priority = %(priority)s")
        values["priority"] = filters.get("priority")

    if filters and filters.get("production_request"):
        conditions.append("name = %(production_request)s")
        values["production_request"] = filters.get("production_request")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    prod_reqs = frappe.db.sql(f"""
        SELECT name, posting_date, required_date, company, customer, priority
        FROM `tabProduction Request`
        {where_clause}
        ORDER BY creation DESC
    """, values, as_dict=True)
    
    data = []
    today_date = getdate(today())
    
    for pr in prod_reqs:
        # Age Calculation
        posting_date = getdate(pr.posting_date)
        age = date_diff(today_date, posting_date)
        
        # Calculate Material Shortages for the entire Production Request
        materials = frappe.get_all("Production Request Material", filters={"parent": pr.name}, fields=["raw_material", "shortage_qty"])
        shortage_map = {}
        for m in materials:
            if m.shortage_qty > 0:
                shortage_map[m.raw_material] = shortage_map.get(m.raw_material, 0.0) + m.shortage_qty
        
        shortages_str = ", ".join([f"{rm} ({qty:.2f})" for rm, qty in shortage_map.items()]) if shortage_map else _("None")
        
        # Fetch items and sub-assemblies
        items = frappe.get_all("Production Request Item", filters={"parent": pr.name}, fields=["item", "production_qty"])
        if filters and filters.get("item_code"):
            items = [i for i in items if i.item == filters.get("item_code")]

        sub_assemblies = frappe.get_all("Production Request Sub Assembly", filters={"parent": pr.name}, fields=["sub_assembly as item", "produce_qty as production_qty"])
        if filters and filters.get("item_code"):
            sub_assemblies = [sa for sa in sub_assemblies if sa.item == filters.get("item_code")]

        all_items = items + sub_assemblies
        
        for item in all_items:
            # Fetch Work Order Status
            wo_info = frappe.db.sql("""
                SELECT status
                FROM `tabWork Order`
                WHERE production_request = %s AND production_item = %s AND docstatus < 2
                ORDER BY creation DESC LIMIT 1
            """, (pr.name, item.item))
            
            wo_status = wo_info[0][0] if wo_info else "Not Created"
            
            if filters and filters.get("status") and wo_status != filters.get("status"):
                continue

            # Aggregate completed quantity from Work Orders
            completed = frappe.db.sql("""
                SELECT SUM(produced_qty) as completed
                FROM `tabWork Order`
                WHERE production_request = %s AND production_item = %s AND docstatus = 1
            """, (pr.name, item.item))[0][0] or 0.0
            
            planned = item.production_qty or 0.0
            pending = max(0.0, planned - completed)
            progress = (completed / planned * 100) if planned > 0 else 0.0
            
            item_name = frappe.db.get_value("Item", item.item, "item_name") or item.item

            data.append({
                "production_request": pr.name,
                "posting_date": pr.posting_date,
                "customer": pr.customer,
                "priority": pr.priority,
                "status": wo_status,
                "item_code": item.item,
                "item_name": item_name,
                "required_date": pr.required_date,
                "age": age,
                "planned_qty": planned,
                "completed_qty": completed,
                "pending_qty": pending,
                "progress": progress,
                "shortages": shortages_str
            })
            
    return data


