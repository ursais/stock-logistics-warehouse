from odoo import api, models


class ReportSiloMovement(models.AbstractModel):
    _name = "report.stock_location_history.report_silo_movement"
    _description = "Silo Movement Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare values for the report template."""
        wizards = self.env["silo.movement.report.wizard"].browse(docids)

        if not wizards:
            return {
                "doc_ids": docids,
                "doc_model": "silo.movement.report.wizard",
                "docs": wizards,
                "movements": self.env["stock.location.history"],
                "grouped": False,
                "data_by_location": {},
                "company": self.env.company,
            }

        wizard = wizards[0]

        # Build domain
        domain = []
        if wizard.date_from:
            domain.append(("date", ">=", wizard.date_from))
        if wizard.date_to:
            domain.append(("date", "<=", wizard.date_to))
        if wizard.location_ids:
            domain.append(("location_id", "in", wizard.location_ids.ids))
        if wizard.product_ids:
            domain.append(("product_id", "in", wizard.product_ids.ids))
        if wizard.show_validated_only:
            domain.append(("is_validated", "=", True))

        movements = self.env["stock.location.history"].search(
            domain, order="location_id, date desc"
        )

        # Group by location if requested
        data_by_location = {}
        if wizard.group_by_silo:
            for mov in movements:
                loc_name = mov.location_id.name if mov.location_id else "Sin Silo"
                if loc_name not in data_by_location:
                    data_by_location[loc_name] = {
                        "location": mov.location_id,
                        "movements": [],
                    }
                data_by_location[loc_name]["movements"].append(mov)

        return {
            "doc_ids": docids,
            "doc_model": "silo.movement.report.wizard",
            "docs": wizards,
            "movements": movements,
            "grouped": wizard.group_by_silo,
            "data_by_location": data_by_location,
            "company": self.env.company,
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
        }
