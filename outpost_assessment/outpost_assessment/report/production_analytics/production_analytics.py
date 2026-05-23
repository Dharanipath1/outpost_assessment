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
    conditions = ["docstatus < 2", "status != 'Cancelled'"] 
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
    
    if not prod_reqs:
        return []

    pr_names = [pr.name for pr in prod_reqs]
    
    all_materials = frappe.get_all(
        "Production Request Material",
        filters={"parent": ["in", pr_names]},
        fields=["parent", "raw_material", "shortage_qty"]
    )
    materials_by_pr = {}
    for m in all_materials:
        materials_by_pr.setdefault(m.parent, []).append(m)

    all_items = frappe.get_all(
        "Production Request Item",
        filters={"parent": ["in", pr_names]},
        fields=["parent", "item", "production_qty"]
    )
    if filters and filters.get("item_code"):
        all_items = [i for i in all_items if i.item == filters.get("item_code")]

    items_by_pr = {}
    for i in all_items:
        items_by_pr.setdefault(i.parent, []).append(i)

    all_sub_assemblies = frappe.get_all(
        "Production Request Sub Assembly",
        filters={"parent": ["in", pr_names]},
        fields=["parent", "sub_assembly as item", "produce_qty as production_qty"]
    )
    if filters and filters.get("item_code"):
        all_sub_assemblies = [sa for sa in all_sub_assemblies if sa.item == filters.get("item_code")]

    sub_assemblies_by_pr = {}
    for sa in all_sub_assemblies:
        sub_assemblies_by_pr.setdefault(sa.parent, []).append(sa)

    work_orders = frappe.db.sql("""
        SELECT production_request, production_item, status, produced_qty, docstatus
        FROM `tabWork Order`
        WHERE production_request IN %s AND docstatus < 2
        ORDER BY creation DESC
    """, (pr_names,), as_dict=True)

    wo_status_map = {}
    wo_completed_map = {}
    for wo in work_orders:
        key = (wo.production_request, wo.production_item)
        if key not in wo_status_map:
            wo_status_map[key] = wo.status
        if wo.docstatus == 1:
            wo_completed_map[key] = wo_completed_map.get(key, 0.0) + (wo.produced_qty or 0.0)

    unique_items = list(set([item.item for item in all_items] + [sa.item for sa in all_sub_assemblies]))
    item_name_map = {}
    if unique_items:
        item_names = frappe.get_all("Item", filters={"name": ["in", unique_items]}, fields=["name", "item_name"])
        item_name_map = {d.name: d.item_name for d in item_names}

    data = []
    today_date = getdate(today())
    
    for pr in prod_reqs:
        posting_date = getdate(pr.posting_date)
        age = date_diff(today_date, posting_date)
        
        materials = materials_by_pr.get(pr.name, [])
        shortage_map = {}
        for m in materials:
            if m.shortage_qty > 0:
                shortage_map[m.raw_material] = shortage_map.get(m.raw_material, 0.0) + m.shortage_qty
        
        shortages_str = ", ".join([f"{rm} ({qty:.2f})" for rm, qty in shortage_map.items()]) if shortage_map else _("None")
        
        pr_items = items_by_pr.get(pr.name, []) + sub_assemblies_by_pr.get(pr.name, [])
        
        for item in pr_items:
            wo_status = wo_status_map.get((pr.name, item.item), "Not Created")
            
            if filters and filters.get("status") and wo_status != filters.get("status"):
                continue

            completed = wo_completed_map.get((pr.name, item.item), 0.0)
            planned = item.production_qty or 0.0
            pending = max(0.0, planned - completed)
            progress = (completed / planned * 100) if planned > 0 else 0.0
            
            item_name = item_name_map.get(item.item, item.item)

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