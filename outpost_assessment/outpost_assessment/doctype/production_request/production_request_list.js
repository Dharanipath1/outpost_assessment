frappe.listview_settings['Production Request'] = {
    add_fields: ["status"],
    get_indicator: function (doc) {
        if (doc.status === "Draft") {
            return [__("Draft"), "red", "status,=,Draft"];
        } else if (doc.status === "Submitted") {
            return [__("Submitted"), "blue", "status,=,Submitted"];
        } else if (doc.status === "Not Started") {
            return [__("Not Started"), "light-blue", "status,=,Not Started"];
        } else if (doc.status === "Partially Started") {
            return [__("Partially Started"), "orange", "status,=,Partially Started"];
        } else if (doc.status === "In Process") {
            return [__("In Process"), "purple", "status,=,In Process"];
        } else if (doc.status === "Partially Completed") {
            return [__("Partially Completed"), "yellow", "status,=,Partially Completed"];
        } else if (doc.status === "Completed") {
            return [__("Completed"), "green", "status,=,Completed"];
        } else if (doc.status === "Cancelled") {
            return [__("Cancelled"), "red", "status,=,Cancelled"];
        } else {
            // Fallback for docstatus
            if (doc.docstatus === 0) {
                return [__("Draft"), "red", "docstatus,=,0"];
            } else if (doc.docstatus === 1) {
                return [__("Submitted"), "blue", "docstatus,=,1"];
            } else if (doc.docstatus === 2) {
                return [__("Cancelled"), "red", "docstatus,=,2"];
            }
        }
    }
};
