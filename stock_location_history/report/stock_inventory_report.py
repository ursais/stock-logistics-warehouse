from odoo import api, models


class ReportStockInventory(models.AbstractModel):
    _name = "report.stock_location_history.report_stock_inventory"
    _description = "Stock Inventory Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare values for the report template."""
        wizards = self.env["stock.inventory.report.wizard"].browse(docids)
        
        # Get macrolots
        domain = [("is_macrolot", "=", True)]
        
        # Apply filters from wizard if available
        if wizards and len(wizards) == 1:
            wizard = wizards[0]
            if wizard.location_ids:
                domain.append(("location_id", "in", wizard.location_ids.ids))
            if wizard.product_ids:
                domain.append(("product_id", "in", wizard.product_ids.ids))
        
        macrolots = self.env["stock.lot"].search(domain, order="location_id, name")
        
        # Group by location
        locations = macrolots.mapped("location_id")
        lots_by_location = {}
        for loc in locations:
            lots_by_location[loc.id] = macrolots.filtered(lambda l: l.location_id == loc)
        
        # Lots without location
        no_location_lots = macrolots.filtered(lambda l: not l.location_id)
        
        return {
            "doc_ids": docids,
            "doc_model": "stock.inventory.report.wizard",
            "docs": wizards,
            "macrolots": macrolots,
            "locations": locations,
            "lots_by_location": lots_by_location,
            "no_location_lots": no_location_lots,
            "company": self.env.company,
        }
