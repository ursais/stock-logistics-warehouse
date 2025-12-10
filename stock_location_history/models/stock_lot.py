from odoo import api, fields, models


class StockLotMacrolot(models.Model):
    _inherit = "stock.lot"

    quantity_in = fields.Float(help="Everything that has entered")
    first_ticket = fields.Char(
        compute="_compute_ticket_data", store=True, help="First ticket name"
    )

    date_first_ticket = fields.Date(
        compute="_compute_ticket_data", store=True, help="First ticket date"
    )

    last_ticket = fields.Char(
        compute="_compute_ticket_data", store=True, help="Last ticket name"
    )

    date_last_ticket = fields.Date(
        compute="_compute_ticket_data", store=True, help="Last ticket date"
    )

    quantity_difference = fields.Float(help="Quantity on hand")
    total_consumption = fields.Float(
        compute="_compute_total_consumption",
        store=True,
        help="Total consumed from this lot (sum of all batch line weights)",
    )

    initial_mix = fields.Char(
        compute="_compute_mix_data", store=True, help="Initial mix code"
    )

    initial_mix_date = fields.Date(
        compute="_compute_mix_data", store=True, help="First mix date"
    )

    final_mix = fields.Char(compute="_compute_mix_data", store=True, help="Final Mix")

    final_mix_date = fields.Date(
        compute="_compute_mix_data", store=True, help="Last mix date"
    )

    kg_consumed_mi = fields.Float(
        compute="_compute_mix_data",
        store=True,
        help="Kilograms consumed from the Initial Mix",
    )

    kg_consumed_mf = fields.Float(
        compute="_compute_mix_data",
        store=True,
        help="Kilograms consumed from the Final Mix",
    )

    batch_line_ids = fields.One2many(
        comodel_name="mrp.batch.lines", inverse_name="lot_id", string="Batch Lines"
    )

    # Quality fields - Data from quality check (Excel books)
    location_id = fields.Many2one(
        "stock.location",
        string="Silo/Location",
        help="Location (silo) where this macrolot is stored",
    )
    is_macrolot = fields.Boolean(
        string="Is Macrolot",
        default=False,
        help="Mark if this lot is a macrolot for silo tracking",
    )
    humedad = fields.Float(
        string="Humedad %",
        digits=(5, 2),
        help="Porcentaje de humedad del grano",
    )
    grano_danado = fields.Float(
        string="Grano Dañado %",
        digits=(5, 2),
        help="Porcentaje de grano dañado",
    )
    peso_especifico = fields.Float(
        string="Peso Específico (g/l)",
        digits=(6, 2),
        help="Peso específico del grano (g/l)",
    )
    pct_finos = fields.Float(
        string="% Finos",
        digits=(5, 2),
        help="Porcentaje de finos",
    )
    pct_quebrados = fields.Float(
        string="% Quebrados",
        digits=(5, 2),
        help="Porcentaje de granos quebrados",
    )
    quality_notes = fields.Text(
        string="Notas de Calidad",
        help="Observaciones adicionales del check de calidad",
    )

    # Additional quality fields from Excel "datos de unidades"
    temperatura = fields.Float(
        string="Temperatura °C",
        digits=(5, 2),
        help="Temperatura del grano al momento de recepción",
    )
    suma_impurezas = fields.Float(
        string="Suma Impurezas (F+Q) %",
        digits=(5, 2),
        compute="_compute_suma_impurezas",
        store=True,
        help="Suma de finos y quebrados (impurezas totales)",
    )
    analista = fields.Char(
        string="Analista",
        help="Nombre del analista de calidad",
    )
    proveedor_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        help="Proveedor del grano/material",
    )

    # Computed fields for reports
    @api.depends("pct_finos", "pct_quebrados")
    def _compute_suma_impurezas(self):
        for lot in self:
            lot.suma_impurezas = (lot.pct_finos or 0) + (lot.pct_quebrados or 0)

    @api.depends("batch_line_ids", "batch_line_ids.weight")
    def _compute_total_consumption(self):
        """Calculate total consumption from all batch lines linked to this lot."""
        for lot in self:
            lot.total_consumption = sum(lot.batch_line_ids.mapped("weight") or [0])

    @api.depends("product_qty")
    def _compute_ticket_data(self):
        for lot in self:
            # In Odoo 18, we query stock.move.line directly to find moves for this lot
            move_lines = self.env["stock.move.line"].search(
                [
                    ("lot_id", "=", lot.id),
                    ("move_id.picking_id.picking_type_id.code", "=", "incoming"),
                    ("move_id.picking_id.state", "=", "done"),
                ]
            )
            move_lines = move_lines.sorted(
                key=lambda ml: (ml.move_id.picking_id.date_done or ml.move_id.date)
            )

            if not move_lines:
                lot.first_ticket = False
                lot.last_ticket = False
                lot.date_first_ticket = False
                lot.date_last_ticket = False
                continue

            # Get first and last tickets
            first_line = move_lines[0]
            last_line = move_lines[-1]

            lot.first_ticket = first_line.move_id.picking_id.name
            lot.last_ticket = last_line.move_id.picking_id.name
            lot.date_first_ticket = (
                first_line.move_id.picking_id.date_done or first_line.move_id.date
            )
            lot.date_last_ticket = (
                last_line.move_id.picking_id.date_done or last_line.move_id.date
            )

    @api.depends("batch_line_ids.batch_id")
    def _compute_mix_data(self):
        for lot in self:
            lines = lot.batch_line_ids
            if not lines:
                lot.initial_mix = False
                lot.final_mix = False
                lot.initial_mix_date = False
                lot.final_mix_date = False
                lot.kg_consumed_mi = 0.0
                lot.kg_consumed_mf = 0.0
                continue

            batches = lines.mapped("batch_id")
            batches = batches.sorted(key=lambda b: b.date_start or b.create_date)

            first = batches[0]
            last = batches[-1]

            lot.initial_mix = first.num_mez
            lot.final_mix = last.num_mez
            lot.initial_mix_date = first.date_start or first.create_date
            lot.final_mix_date = last.date_start or last.create_date

            # Calcular kg_consumed_mi (kilogramos consumidos de la mezcla inicial)
            first_num_mez = first.num_mez
            initial_mix_lines = lines.filtered(
                lambda line, first_num_mez=first_num_mez: (
                    line.batch_id.num_mez == first_num_mez
                )
            )
            lot.kg_consumed_mi = sum(initial_mix_lines.mapped("weight"))

            # Calcular kg_consumed_mf (kilogramos consumidos de la mezcla final)
            last_num_mez = last.num_mez
            final_mix_lines = lines.filtered(
                lambda line, last_num_mez=last_num_mez: (
                    line.batch_id.num_mez == last_num_mez
                )
            )
            lot.kg_consumed_mf = sum(final_mix_lines.mapped("weight"))
