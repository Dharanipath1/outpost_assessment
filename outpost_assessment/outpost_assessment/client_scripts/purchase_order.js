frappe.ui.form.on("Purchase Order", {
    before_workflow_action: function(frm) {
        if (frm.selected_workflow_action === "Reject") {
            frappe.dom.unfreeze();
            
            return new Promise((resolve, reject) => {
                frappe.prompt(
                    [
                        {
                            label: __("Reason for Rejection"),
                            fieldname: "rejection_comment",
                            fieldtype: "Small Text",
                            reqd: 1
                        }
                    ],
                    (values) => {
                        frappe.dom.freeze();
                        
                        frappe.call({
                            method: "frappe.desk.form.utils.add_comment",
                            args: {
                                reference_doctype: frm.doctype,
                                reference_name: frm.docname,
                                content: values.rejection_comment,
                                comment_email: frappe.session.user,
                                comment_by: frappe.session.user_fullname
                            },
                            callback: function(r) {
                                if (!r.exc) {
                                    resolve();
                                } else {
                                    frappe.dom.unfreeze();
                                    reject();
                                }
                            }
                        });
                    },
                    __("Enter Rejection Comment"),
                    __("Confirm Reject")
                );
                
                $(".modal-header .close, .btn-modal-close, button[data-dismiss='modal']").on("click", function() {
                    reject();
                });
            });
        } else {
            return Promise.resolve();
        }
    }
});
