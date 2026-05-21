# Copyright (c) 2026, Dharanipathi and contributors
# For license information, please see license.txt

from frappe import _

def get_data():
    return {
        "fieldname": "name",
        "non_standard_fieldnames": {
            "Sales Invoice": "name",
            "Payment Entry": "name"
        },
        "internal_links": {
            "Sales Invoice": "invoice_id",
            "Payment Entry": "payment_entry"
        },
        "transactions": [
            {
                "label": _("Linked Documents"),
                "items": ["Sales Invoice", "Payment Entry"]
            }
        ]
    }