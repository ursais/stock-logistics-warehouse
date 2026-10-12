from odoo import api, models


class ReportStockInventory(models.AbstractModel):
    _name = "report.stock_location_history.report_stock_inventory"
    _description = "Stock Inventory Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare values for the report template."""
        wizards = self.env["stock.inventory.report.wizard"].browse(docids).exists()
        wizard = wizards[:1]

        domain = [("is_macrolot", "=", True)]
        #domain = ["|", ("is_macrolot", "=", True), ("product_qty", ">", 0.0)]

        ProductCategory = self.env["product.category"].sudo()

        macros_categories = ProductCategory.search([("name", "=", "MACROS")])
        if not macros_categories:
            # fallback por si el nombre tiene variaciones o hay varias rutas
            macros_categories = ProductCategory.search([("complete_name", "ilike", "MACROS")])

        if macros_categories:
            domain.append(("product_id.categ_id", "child_of", macros_categories.ids))

        if wizard:
            if wizard.location_ids:
                domain.append(("location_id", "in", wizard.location_ids.ids))
            if wizard.product_ids:
                domain.append(("product_id", "in", wizard.product_ids.ids))

        macrolots = self.env["stock.lot"].search(domain, order="location_id, product_id, name")

        locations = macrolots.mapped("location_id")
        lots_by_location = {
            loc.id: macrolots.filtered(lambda l, loc=loc: l.location_id.id == loc.id)
            for loc in locations
        }

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
