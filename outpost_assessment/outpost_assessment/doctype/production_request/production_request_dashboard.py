from frappe import _

def get_data():
    return {
        "fieldname": "production_request",
        "transactions": [
            {
                "label": _("Manufacturing"),
                "items": ["Work Order"]
            }
        ]
    }
