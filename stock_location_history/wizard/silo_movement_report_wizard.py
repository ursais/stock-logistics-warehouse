from odoo import api, fields, models


class SiloMovementReportWizard(models.TransientModel):
    _name = "silo.movement.report.wizard"
    _description = "Wizard for Silo Movement Report"

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
        string="Silos",
        help="Dejar vacío para incluir todos los silos",
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Productos",
        help="Dejar vacío para incluir todos los productos",
    )
    show_validated_only = fields.Boolean(
        string="Solo movimientos validados",
        default=False,
    )
    show_quarantine = fields.Boolean(
        string="Mostrar cuarentenas",
        default=True,
    )
    group_by_silo = fields.Boolean(
        string="Agrupar por silo",
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

    def _get_domain(self):
        """Build domain for movements."""
        domain = []

        if self.date_from:
            domain.append(("date", ">=", self.date_from))
        if self.date_to:
            domain.append(("date", "<=", self.date_to))
        if self.location_ids:
            domain.append(("location_id", "in", self.location_ids.ids))
        if self.product_ids:
            domain.append(("product_id", "in", self.product_ids.ids))
        if self.show_validated_only:
            domain.append(("is_validated", "=", True))

        return domain

    def _get_report_data(self):
        """Prepare data for the report."""
        self.ensure_one()

        domain = self._get_domain()
        movements = self.env["stock.location.history"].search(
            domain, order="location_id, date desc"
        )

        if self.group_by_silo:
            # Group by location
            data_by_location = {}
            for mov in movements:
                loc_name = mov.location_id.name if mov.location_id else "Sin Silo"
                if loc_name not in data_by_location:
                    data_by_location[loc_name] = {
                        "location": mov.location_id,
                        "movements": [],
                    }
                data_by_location[loc_name]["movements"].append(mov)

            return {
                "grouped": True,
                "data_by_location": data_by_location,
                "movements": movements,
            }
        else:
            return {
                "grouped": False,
                "movements": movements,
            }

    def action_print_report(self):
        """Print the silo movement report."""
        self.ensure_one()
        return self.env.ref(
            "stock_location_history.action_report_silo_movement"
        ).report_action(self)

    def action_view_movements(self):
        """Open movements view with filters applied."""
        self.ensure_one()

        domain = self._get_domain()

        return {
            "name": "Movimientos de Silo",
            "type": "ir.actions.act_window",
            "res_model": "stock.location.history",
            "view_mode": "list,form",
            "domain": domain,
            "context": {},
        }

    def action_export_excel(self):
        """Export to Excel (placeholder - requires xlsxwriter)."""
        self.ensure_one()
        # TODO: Implement Excel export
        return self.action_view_movements()
