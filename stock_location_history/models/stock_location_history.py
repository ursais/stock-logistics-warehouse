from odoo import api, fields, models


class StockLocationHistory(models.Model):
    _name = "stock.location.history"
    _description = "Stock Location History"
    _order = "date desc"
    _rec_name = "display_name"

    # Core fields
    location_id = fields.Many2one("stock.location", string="Silo", required=True)
    product_id = fields.Many2one(related="lot_id.product_id", store=True)
    lot_id = fields.Many2one("stock.lot", string="Macrolote")
    previous_stage_id = fields.Many2one("stock.location.stage", string="Estado Anterior")
    new_stage_id = fields.Many2one("stock.location.stage", string="Nuevo Estado")
    user_id = fields.Many2one("res.users", string="Usuario")
    date = fields.Datetime(string="Fecha/Hora", default=fields.Datetime.now)
    registry_type = fields.Char()

    # Computed display name
    display_name = fields.Char(compute="_compute_display_name", store=True)

    # General flag (from Excel: "General")
    is_general = fields.Boolean(
        string="General",
        default=False,
        help="Indica si es un movimiento general del silo (sin macrolote específico)",
    )

    # Validation fields (from Excel: Validado, Fecha validación, Hora validación)
    is_validated = fields.Boolean(
        string="Validado",
        default=False,
        help="Indica si el movimiento fue validado",
    )
    validated_date = fields.Datetime(
        string="Fecha/Hora Validación",
        help="Fecha y hora de validación del movimiento",
    )
    validated_user_id = fields.Many2one(
        "res.users",
        string="Validado por",
        help="Usuario que validó el movimiento",
    )

    # Quarantine fields (from Excel: Cuarentena, Fecha inicio/fin cuarentena)
    is_quarantine = fields.Boolean(
        string="Cuarentena",
        default=False,
        help="Indica si el silo/lote está en cuarentena",
    )
    quarantine_start_date = fields.Datetime(
        string="Inicio Cuarentena",
        help="Fecha y hora de inicio de cuarentena",
    )
    quarantine_end_date = fields.Datetime(
        string="Fin Cuarentena",
        help="Fecha y hora de fin de cuarentena",
    )
    quarantine_start_user_id = fields.Many2one(
        "res.users",
        string="Usuario Inicio Cuarentena",
    )
    quarantine_end_user_id = fields.Many2one(
        "res.users",
        string="Usuario Fin Cuarentena",
    )

    # Related macrolot transfer (from Excel: Traspaso ML relacionado)
    related_transfer_id = fields.Many2one(
        "stock.location.history",
        string="Traspaso ML Relacionado",
        help="Movimiento de traspaso de macrolote relacionado",
    )

    # Observations
    notes = fields.Text(
        string="Observaciones",
        help="Notas u observaciones del movimiento",
    )

    @api.depends("location_id", "lot_id", "date")
    def _compute_display_name(self):
        for record in self:
            silo = record.location_id.name or "Sin Silo"
            lote = record.lot_id.name or "Sin Lote"
            fecha = record.date.strftime("%Y-%m-%d %H:%M") if record.date else ""
            record.display_name = f"{silo} - {lote} ({fecha})"

    def action_validate(self):
        """Validate the movement."""
        for record in self:
            record.write({
                "is_validated": True,
                "validated_date": fields.Datetime.now(),
                "validated_user_id": self.env.user.id,
            })
        return True

    def action_start_quarantine(self):
        """Start quarantine for the silo/lot."""
        for record in self:
            record.write({
                "is_quarantine": True,
                "quarantine_start_date": fields.Datetime.now(),
                "quarantine_start_user_id": self.env.user.id,
            })
        return True

    def action_end_quarantine(self):
        """End quarantine for the silo/lot."""
        for record in self:
            record.write({
                "is_quarantine": False,
                "quarantine_end_date": fields.Datetime.now(),
                "quarantine_end_user_id": self.env.user.id,
            })
        return True
