# -*- coding: utf-8 -*-
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as frappe_create_custom_fields

CUSTOM_FIELDS = {
    "Work Order": [
        {
            "fieldname": "production_request",
            "label": "Production Request",
            "fieldtype": "Link",
            "options": "Production Request",
            "insert_after": "production_plan_sub_assembly_item"
        },
        {
            "fieldname": "production_request_item",
            "label": "Production Request Item",
            "fieldtype": "Link",
            "options": "Production Request Item",
            "insert_after": "production_request"
        },
        {
            "fieldname": "production_request_sub_assembly",
            "label": "Production Request Sub-assembly Item",
            "fieldtype": "Link",
            "options": "Production Request Sub Assembly",
            "insert_after": "production_request_item"
        }
    ],
    "Production Request Sub Assembly": [
        {
            "fieldname": "produced_qty",
            "label": "Produced Qty",
            "fieldtype": "Float",
            "read_only": 1,
            "insert_after": "produce_qty"
        }
    ],
    "Work Order Item": [
        {
            "fieldname": "reserve_stock",
            "label": "Reserve Stock",
            "fieldtype": "Check",
            "default": "1",
            "insert_after": "item_name"
        },
        {
            "fieldname": "stock_reserved_qty",
            "label": "Stock Reserved Qty",
            "fieldtype": "Float",
            "read_only": 1,
            "insert_after": "reserve_stock"
        }
    ],
    "Stock Entry Detail": [
        {
            "fieldname": "against_stock_reservation_entry",
            "label": "Against Stock Reservation Entry",
            "fieldtype": "Link",
            "options": "Stock Reservation Entry",
            "read_only": 1,
            "insert_after": "against_sales_order"
        }
    ]
}

def create_custom_fields(force=False):
    frappe_create_custom_fields(CUSTOM_FIELDS)
