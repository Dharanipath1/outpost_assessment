from erpnext.stock.doctype.stock_entry.stock_entry_dashboard import get_data as get_standard_data

def get_data(data=None):
    if not data:
        data = get_standard_data()

    if "Stock Reservation Entry" not in data.setdefault("internal_links", {}):
        data["internal_links"]["Stock Reservation Entry"] = ["items", "against_stock_reservation_entry"]

    added = False
    for group in data.setdefault("transactions", []):
        if group.get("label") == "Reference" or group.get("label") == "Reference":
            if "Stock Reservation Entry" not in group.setdefault("items", []):
                group["items"].append("Stock Reservation Entry")
            added = True
            break
            
    if not added:
        data["transactions"].append({
            "label": "References",
            "items": ["Stock Reservation Entry"]
        })

    return data
