# Copyright (c) 2026, Dharanipathi and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, now_datetime


class TestProductionRequest(FrappeTestCase):
    def setUp(self):
        super().setUp()
        self.company = frappe.db.get_single_value("Global Defaults", "default_company") or "Test Company"
        
        # Ensure test warehouses exist
        for wh_name in ["Finished Goods - T", "Stores - T", "Work In Progress - T"]:
            if not frappe.db.exists("Warehouse", wh_name):
                wh = frappe.new_doc("Warehouse")
                wh.warehouse_name = wh_name
                wh.company = self.company
                wh.insert(ignore_permissions=True)
                
        # Create test raw material item
        if not frappe.db.exists("Item", "Test RM Item"):
            rm = frappe.new_doc("Item")
            rm.item_code = "Test RM Item"
            rm.item_group = "Raw Material"
            rm.stock_uom = "Nos"
            rm.is_stock_item = 1
            rm.insert(ignore_permissions=True)

        # Create test finished good item
        if not frappe.db.exists("Item", "Test FG Item"):
            fg = frappe.new_doc("Item")
            fg.item_code = "Test FG Item"
            fg.item_group = "Products"
            fg.stock_uom = "Nos"
            fg.is_stock_item = 1
            fg.include_item_in_manufacturing = 1
            fg.insert(ignore_permissions=True)

        # Create a BOM for the Finished Good
        self.bom_name = frappe.db.get_value("BOM", {"item": "Test FG Item", "is_active": 1, "docstatus": 1}, "name")
        if not self.bom_name:
            bom = frappe.new_doc("BOM")
            bom.item = "Test FG Item"
            bom.quantity = 1.0
            bom.company = self.company
            bom.is_active = 1
            
            bom.append("items", {
                "item_code": "Test RM Item",
                "qty": 2.0,
                "uom": "Nos",
                "stock_uom": "Nos"
            })
            bom.insert(ignore_permissions=True)
            bom.submit()
            self.bom_name = bom.name

    def test_calculate_material_requirements(self):
        pr = frappe.new_doc("Production Request")
        pr.company = self.company
        pr.posting_date = today()
        pr.posting_time = now_datetime().strftime("%H:%M:%S")
        pr.required_date = today()
        pr.priority = "Medium"
        pr.fg_warehouse = "Finished Goods - T"
        pr.rm_warehouse = "Stores - T"
        pr.wip_warehouse = "Work In Progress - T"
        pr.sub_assembly_warehouse = "Work In Progress - T"
        pr.customer = frappe.get_all("Customer", limit=1, fields=["name"])[0].name if frappe.get_all("Customer", limit=1) else "Test Customer"
        
        # Ensure customer exists for the test if not found
        if not frappe.db.exists("Customer", pr.customer):
            cust = frappe.new_doc("Customer")
            cust.customer_name = pr.customer
            cust.insert(ignore_permissions=True)

        pr.append("items", {
            "item": "Test FG Item",
            "production_qty": 5.0,
            "bom_no": self.bom_name,
            "fg_warehouse": "Finished Goods - T",
            "required_date": today()
        })
        
        pr.validate()
        
        # Requirements should be correctly resolved: 5 FG * 2 RM = 10 RM
        rm_req = [row for row in pr.material_requirements if row.raw_material == "Test RM Item"]
        self.assertEqual(len(rm_req), 1)
        self.assertEqual(rm_req[0].required_qty, 10.0)

    def test_stock_shortage_blocks_submission(self):
        pr = frappe.new_doc("Production Request")
        pr.company = self.company
        pr.posting_date = today()
        pr.posting_time = now_datetime().strftime("%H:%M:%S")
        pr.required_date = today()
        pr.priority = "Medium"
        pr.fg_warehouse = "Finished Goods - T"
        pr.rm_warehouse = "Stores - T"
        pr.wip_warehouse = "Work In Progress - T"
        pr.sub_assembly_warehouse = "Work In Progress - T"
        pr.customer = frappe.get_all("Customer", limit=1, fields=["name"])[0].name if frappe.get_all("Customer", limit=1) else "Test Customer"
        
        pr.append("items", {
            "item": "Test FG Item",
            "production_qty": 5.0,
            "bom_no": self.bom_name,
            "fg_warehouse": "Finished Goods - T",
            "required_date": today()
        })
        
        pr.insert(ignore_permissions=True)
        
        # Since stock of "Test RM Item" is 0, submitting must raise frappe.ValidationError due to shortage
        self.assertRaises(frappe.ValidationError, pr.submit)
