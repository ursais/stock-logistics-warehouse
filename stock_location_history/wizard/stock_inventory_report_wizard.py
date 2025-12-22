from odoo import api, fields, models


class StockInventoryReportWizard(models.TransientModel):
    _name = "stock.inventory.report.wizard"
    _description = "Wizard for Stock Inventory Report"

    date_from = fields.Date(
        string="Desde",
        required=True,
    )
    date_to = fields.Date(
        string="Hasta",
        required=True,
    )
    location_ids = fields.Many2many(
        "stock.location",
        string="Silos/Ubicaciones",
        help="Dejar vacío para incluir todas las ubicaciones",
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Productos",
        help="Dejar vacío para incluir todos los productos",
    )
    show_quality_data = fields.Boolean(
        string="Mostrar datos de calidad",
        default=True,
    )
    show_consumption_data = fields.Boolean(
        string="Mostrar datos de consumo",
        default=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        if "date_from" in fields_list:
            res["date_from"] = today.replace(day=1)
        if "date_to" in fields_list:
            res["date_to"] = today
        return res

    def _get_report_data(self):
        """Prepare data for the report."""
        self.ensure_one()

        # Simple domain - just get macrolots
        domain = [("is_macrolot", "=", True)]

        if self.location_ids:
            domain.append(("location_id", "in", self.location_ids.ids))

        if self.product_ids:
            domain.append(("product_id", "in", self.product_ids.ids))

        lots = self.env["stock.lot"].search(domain, order="location_id, product_id, name")

        # Group by location
        data_by_location = {}
        for lot in lots:
            loc_name = lot.location_id.name if lot.location_id else "Sin Ubicación"
            if loc_name not in data_by_location:
                data_by_location[loc_name] = {
                    "location": lot.location_id,
                    "lots": [],
                    "totals": {
                        "quantity_in": 0,
                        "total_consumption": 0,
                        "quantity_on_hand": 0,
                    },
                }

            lot_data = {
                "lot": lot,
                "name": lot.name,
                "product": lot.product_id.display_name,
                "quantity_in": lot.quantity_in or 0,
                "quantity_on_hand": lot.product_qty or 0,
                "total_consumption": lot.total_consumption or 0,
                "first_ticket": lot.first_ticket or "",
                "date_first_ticket": str(lot.date_first_ticket) if lot.date_first_ticket else "",
                "last_ticket": lot.last_ticket or "",
                "date_last_ticket": str(lot.date_last_ticket) if lot.date_last_ticket else "",
                "initial_mix": lot.initial_mix or "",
                "initial_mix_date": str(lot.initial_mix_date) if lot.initial_mix_date else "",
                "final_mix": lot.final_mix or "",
                "final_mix_date": str(lot.final_mix_date) if lot.final_mix_date else "",
                "kg_consumed_mi": lot.kg_consumed_mi or 0,
                "kg_consumed_mf": lot.kg_consumed_mf or 0,
                "humedad": lot.humedad or 0,
                "grano_danado": lot.grano_danado or 0,
                "peso_especifico": lot.peso_especifico or 0,
                "pct_finos": lot.pct_finos or 0,
                "pct_quebrados": lot.pct_quebrados or 0,
                "quality_notes": lot.quality_notes or "",
            }

            data_by_location[loc_name]["lots"].append(lot_data)
            data_by_location[loc_name]["totals"]["quantity_in"] += lot_data["quantity_in"]
            data_by_location[loc_name]["totals"]["total_consumption"] += lot_data["total_consumption"]
            data_by_location[loc_name]["totals"]["quantity_on_hand"] += lot_data["quantity_on_hand"]

        return {
            "data_by_location": data_by_location,
            "show_quality_data": self.show_quality_data,
            "show_consumption_data": self.show_consumption_data,
            "date_from": str(self.date_from),
            "date_to": str(self.date_to),
            "company_name": self.env.company.name,
        }

    def action_print_report(self):
        """Print the inventory report."""
        self.ensure_one()
        return self.env.ref(
            "stock_location_history.action_report_stock_inventory"
        ).report_action(self)

    def action_view_lots(self):
        """Open lots view with filters applied."""
        self.ensure_one()

        domain = [("is_macrolot", "=", True)]

        if self.location_ids:
            domain.append(("location_id", "in", self.location_ids.ids))

        if self.product_ids:
            domain.append(("product_id", "in", self.product_ids.ids))

        return {
            "name": "Macrolotes - Existencias",
            "type": "ir.actions.act_window",
            "res_model": "stock.lot",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_is_macrolot": True},
        }
