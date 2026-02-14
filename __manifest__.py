{
    "name": "POS Fiscal Auto Print",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "depends": [
        "point_of_sale",
        "account",
    ],
    "data": [
        "data/ir_cron.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [        
	    "lms_pos_fiscal_print/static/src/js/pos_block_odoo_pdf.js",
	    "lms_pos_fiscal_print/static/lib/qz-tray/qz-tray.js",
            "lms_pos_fiscal_print/static/src/js/fiscal_print_qz.js",
            "lms_pos_fiscal_print/static/src/js/pos_auto_print.js",
	    "lms_pos_fiscal_print/static/src/js/ncf_indicator.js",
            "lms_pos_fiscal_print/static/src/xml/ncf_indicator.xml",

        ],
    },
    "installable": True,
}
