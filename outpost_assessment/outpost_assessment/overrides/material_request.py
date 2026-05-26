from frappe import _
import erpnext.stock.doctype.material_request.material_request_dashboard as standard_dashboard


def get_data(data=None):
    if not data:
        data = standard_dashboard.get_data()

    internal_links = data.setdefault("internal_links", {})
    if "Production Request" not in internal_links:
        internal_links["Production Request"] = ["items", "production_request"]

    transactions = data.setdefault("transactions", [])
    already_added = any(
        "Production Request" in group.get("items", [])
        for group in transactions
    )

    if not already_added:
        manufacturing_group = next(
            (g for g in transactions if g.get("label") in ("Manufacturing", _("Manufacturing"))),
            None,
        )
        if manufacturing_group:
            manufacturing_group.setdefault("items", []).append("Production Request")
        else:
            transactions.append({
                "label": _("Manufacturing"),
                "items": ["Production Request"],
            })

    return data
