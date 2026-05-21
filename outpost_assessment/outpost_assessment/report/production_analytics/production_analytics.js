frappe.query_reports["Production Analytics"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "priority",
            "label": __("Priority"),
            "fieldtype": "Select",
            "options": "\nLow\nMedium\nHigh"
        },
        {
            "fieldname": "production_request",
            "label": __("Production Request"),
            "fieldtype": "Link",
            "options": "Production Request"
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nDraft\nSubmitted\nNot Started\nIn Process\nCompleted\nStopped\nCancelled"
        },
        {
            "fieldname": "item_code",
            "label": __("Item"),
            "fieldtype": "Link",
            "options": "Item"
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname == "completed_qty" && data && data.completed_qty > 0) {
            value = "<span style='color: green; font-weight: bold;'>" + value + "</span>";
        }
        if (column.fieldname == "pending_qty" && data && data.pending_qty > 0) {
            value = "<span style='color: red; font-weight: bold;'>" + value + "</span>";
        }
        return value;
    }
};
