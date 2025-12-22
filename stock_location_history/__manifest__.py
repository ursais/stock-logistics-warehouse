{
    "name": "Stock Location History",
    "version": "18.0.2.0.0",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/stock-logistics-warehouse",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "depends": ["stock", "mrp", "purchase_stock", "gaqsa_plc"],
    "category": "Stock",
    "summary": "Silo management with stages, macrolots, quality data, validation, quarantine and PLC integration",
    "data": [
        "security/ir.model.access.csv",
        "data/stock_location_stage_data.xml",
        # Wizards first (actions needed by menus)
        "wizard/stock_inventory_report_wizard_views.xml",
        "wizard/silo_movement_report_wizard_views.xml",
        # Reports
        "report/stock_inventory_report.xml",
        "report/silo_movement_report.xml",
        # Views (menus reference wizard actions)
        "views/stock_location_views.xml",
        "views/stock_location_stage_views.xml",
        "views/stock_location_history_views.xml",
        "views/stock_lot_views.xml",
        "views/stock_production_lot_views.xml",
    ],
    "development_status": "Beta",
    "maintainers": ["jasiel-OSI"],
}
