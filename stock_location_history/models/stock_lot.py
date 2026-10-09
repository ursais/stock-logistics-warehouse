from collections import defaultdict

from odoo import api, fields, models


class StockLotMacrolot(models.Model):
    _inherit = "stock.lot"

    quantity_in = fields.Float(
        compute="_compute_ticket_data",
        store=True,
        help="Suma de las cantidades recibidas en los traslados de entrada de este lote",
    )

    first_ticket = fields.Char(
        compute="_compute_ticket_data",
        store=True,
        help="Nombre del primer traslado de entrada recibido",
    )

    date_first_ticket = fields.Date(
        compute="_compute_ticket_data", store=True, help="First ticket date"
    )

    last_ticket = fields.Char(
        compute="_compute_ticket_data",
        store=True,
        help="Nombre del último traslado de entrada recibido",
    )

    date_last_ticket = fields.Date(
        compute="_compute_ticket_data", store=True, help="Last ticket date"
    )

    quantity_difference = fields.Float(
        compute="_compute_ticket_data",
        store=True,
        help="Quantity on hand = quantity_in - total_consumption",
    )

    total_consumption = fields.Float(
        compute="_compute_total_consumption",
        store=True,
        help="Total consumed from this lot (sum of all batch line weights)",
    )

    initial_mix = fields.Char(
        compute="_compute_mix_data",
        store=True,
        help="NumMez más pequeño de las mezclas que consumieron este lote",
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

    # Quality fields - computed from tickets (weighted average by qty_received)
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Silo/Location",
        help="Current internal location where this lot is stored (assigned silo has priority).",
    )

    location_lot = fields.Char(
        string="Ubicación Lote", readonly=True, copy=False, index=True
    )

    is_macrolot = fields.Boolean(
        string="Is Macrolot",
        default=False,
        help="Mark if this lot is a macrolot for silo tracking",
    )

    humedad = fields.Float(
        string="Humedad %",
        digits=(5, 2),
        compute="_compute_quality_from_tickets",
        store=True,
    )
    grano_danado = fields.Float(
        string="Grano Dañado %",
        digits=(5, 2),
        compute="_compute_quality_from_tickets",
        store=True,
    )
    peso_especifico = fields.Float(
        string="Peso Específico (g/l)",
        digits=(6, 2),
        compute="_compute_quality_from_tickets",
        store=True, 
    )
    pct_finos = fields.Float(
        string="% Finos",
        digits=(5, 2),
        compute="_compute_quality_from_tickets",
        store=True,
    )
    pct_quebrados = fields.Float(
        string="% Quebrados",
        digits=(5, 2),
        compute="_compute_quality_from_tickets",
        store=True,
    )
    temperatura = fields.Float(
        string="Temperatura °C",
        digits=(5, 2),
        compute="_compute_quality_from_tickets",
        store=True,
    )

    quality_notes = fields.Text(
        string="Notas de Calidad", help="Observaciones adicionales del check de calidad"
    )

    assigned_location_ids = fields.One2many(
        comodel_name="stock.location",
        inverse_name="lot_id",
        string="Assigned Silos",
        readonly=True,
    )

    quant_ids = fields.One2many(
        comodel_name="stock.quant",
        inverse_name="lot_id",
        string="Quants",
        readonly=True,
    )

    suma_impurezas = fields.Float(
        string="Suma Impurezas (F+Q) %",
        digits=(5, 2),
        compute="_compute_suma_impurezas",
        store=True,
        help="Suma de finos y quebrados (impurezas totales)",
    )

    analista = fields.Char(string="Analista", help="Nombre del analista de calidad")

    proveedor_id = fields.Many2one(
        "res.partner", string="Proveedor", help="Proveedor del grano/material"
    )

    quantity_first_ticket = fields.Float(
        string="Entrada primer ticket",
        compute="_compute_ticket_data",
        store=True,
        help="Cantidad del primer traslado de entrada recibido",
    )

    quantity_last_ticket = fields.Float(
        string="Entrada último ticket",
        compute="_compute_ticket_data",
        store=True,
        help="Cantidad del último traslado de entrada recibido",
    )

    # Computed fields for reports
    @api.depends(
        "ticket_move_ids.humedad",
        "ticket_move_ids.peso_especifico",
        "ticket_move_ids.temperatura",
        "ticket_move_ids.pct_finos",
        "ticket_move_ids.pct_quebrados",
        "ticket_move_ids.grano_danado",
        "ticket_move_ids.qty_received",
    )
    def _compute_quality_from_tickets(self):
        quality_fields = [
            "humedad",
            "peso_especifico",
            "temperatura",
            "pct_finos",
            "pct_quebrados",
            "grano_danado",
        ]
        for lot in self:
            tickets = lot.ticket_move_ids.filtered(lambda t: t.qty_received > 0)
            total_qty = sum(tickets.mapped("qty_received"))
            if not total_qty:
                for fname in quality_fields:
                    lot[fname] = 0.0
                continue
            for fname in quality_fields:
                lot[fname] = sum(t[fname] * t.qty_received for t in tickets) / total_qty

    @api.depends("pct_finos", "pct_quebrados")
    def _compute_suma_impurezas(self):
        for lot in self:
            lot.suma_impurezas = (lot.pct_finos or 0) + (lot.pct_quebrados or 0)

    @api.depends("batch_line_ids", "batch_line_ids.weight")
    def _compute_total_consumption(self):
        """Calculate total consumption from all batch lines linked to this lot."""
        for lot in self:
            lot.total_consumption = sum(lot.batch_line_ids.mapped("weight") or [0])

    @staticmethod
    def _incoming_receipt_moment(picking):
        """Moment the transfer was received. Falls back if date_done is empty."""
        return picking.date_done or picking.scheduled_date or picking.create_date

    @staticmethod
    def _num_mez_sort_key(batch):
        """Order mixes by numeric NumMez. Non-numeric values sort after."""
        number = (batch.num_mez or "").strip()
        if number.isdigit():
            return (0, int(number), batch.id)
        return (1, number, batch.id)

    @api.depends(
        "total_consumption",
        "ticket_move_ids.qty_received",
        "ticket_move_ids.date",
        "ticket_move_ids.move_id",
    )
    def _compute_ticket_data(self):
        """Summarize done incoming transfers of this lot.

        First and last ticket are the IN documents, ordered by reception date.
        Entrada total is the sum of the quantities received on this lot.
        """
        MoveLine = self.env["stock.move.line"].sudo()

        for lot in self:
            lot.first_ticket = False
            lot.last_ticket = False
            lot.date_first_ticket = False
            lot.date_last_ticket = False
            lot.quantity_in = 0.0
            lot.quantity_difference = 0.0
            lot.product_qty = 0.0
            lot.quantity_first_ticket = 0.0
            lot.quantity_last_ticket = 0.0

            if not lot.id:
                continue

            move_lines = MoveLine.search(
                [
                    ("lot_id", "=", lot.id),
                    ("move_id.picking_id.picking_type_id.code", "=", "incoming"),
                    ("move_id.picking_id.state", "=", "done"),
                ]
            )

            qty_by_picking = {}
            pickings = self.env["stock.picking"]
            for move_line in move_lines:
                picking = move_line.move_id.picking_id
                if not picking:
                    continue
                qty_by_picking[picking.id] = qty_by_picking.get(picking.id, 0.0) + (
                    move_line.quantity or 0.0
                )
                pickings |= picking

            if pickings:
                undated = fields.Datetime.to_datetime("1970-01-01 00:00:00")
                ordered = pickings.sorted(
                    key=lambda picking: (
                        lot._incoming_receipt_moment(picking) or undated,
                        picking.id,
                    )
                )
                first_picking = ordered[0]
                last_picking = ordered[-1]
                lot.first_ticket = first_picking.name
                lot.last_ticket = last_picking.name
                first_moment = lot._incoming_receipt_moment(first_picking)
                last_moment = lot._incoming_receipt_moment(last_picking)
                lot.date_first_ticket = (
                    fields.Date.to_date(first_moment) if first_moment else False
                )
                lot.date_last_ticket = (
                    fields.Date.to_date(last_moment) if last_moment else False
                )
                lot.quantity_first_ticket = qty_by_picking.get(first_picking.id, 0.0)
                lot.quantity_last_ticket = qty_by_picking.get(last_picking.id, 0.0)

            lot.quantity_in = sum(qty_by_picking.values()) if qty_by_picking else 0.0
            if lot.quantity_in:
                lot.quantity_difference = lot.quantity_in - (
                    lot.total_consumption or 0.0
                )
            else:
                lot.quantity_difference = 0.0
            lot.product_qty = lot.quantity_in - (lot.total_consumption or 0.0)

    @api.depends(
        "batch_line_ids.batch_id.num_mez",
        "batch_line_ids.batch_id.date_start",
        "batch_line_ids.weight",
    )
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
            if not batches:
                lot.initial_mix = False
                lot.final_mix = False
                lot.initial_mix_date = False
                lot.final_mix_date = False
                lot.kg_consumed_mi = 0.0
                lot.kg_consumed_mf = 0.0
                continue

            initial = min(batches, key=lot._num_mez_sort_key)
            same_number = batches.filtered(
                lambda batch, number=initial.num_mez: batch.num_mez == number
            )
            initial_for_date = same_number.sorted(
                key=lambda batch: batch.date_start or batch.create_date
            )[0]
            final = batches.sorted(key=lambda batch: batch.date_start or batch.create_date)[
                -1
            ]

            lot.initial_mix = initial.num_mez
            lot.final_mix = final.num_mez
            initial_moment = initial_for_date.date_start or initial_for_date.create_date
            final_moment = final.date_start or final.create_date
            lot.initial_mix_date = (
                fields.Date.to_date(initial_moment) if initial_moment else False
            )
            lot.final_mix_date = (
                fields.Date.to_date(final_moment) if final_moment else False
            )

            initial_num = initial.num_mez
            initial_mix_lines = lines.filtered(
                lambda line, initial_num=initial_num: (
                    line.batch_id.num_mez == initial_num
                )
            )
            lot.kg_consumed_mi = sum(initial_mix_lines.mapped("weight") or [0.0])

            final_num = final.num_mez
            final_mix_lines = lines.filtered(
                lambda line, final_num=final_num: line.batch_id.num_mez == final_num
            )
            lot.kg_consumed_mf = sum(final_mix_lines.mapped("weight") or [0.0])

    def action_recompute_purchase_tickets(self):
        for lot in self:
            lot._compute_ticket_data()
            lot._compute_mix_data()
            lot._compute_location_id()
            lot.write(
                {
                    "quantity_in": lot.quantity_in,
                    "quantity_difference": lot.quantity_difference,
                    "first_ticket": lot.first_ticket,
                    "date_first_ticket": lot.date_first_ticket,
                    "last_ticket": lot.last_ticket,
                    "date_last_ticket": lot.date_last_ticket,
                    "product_qty": lot.product_qty,
                    "quantity_first_ticket": lot.quantity_first_ticket,
                    "quantity_last_ticket": lot.quantity_last_ticket,
                    "initial_mix": lot.initial_mix,
                    "initial_mix_date": lot.initial_mix_date,
                    "kg_consumed_mi": lot.kg_consumed_mi,
                }
            )

    @api.depends(
        "assigned_location_ids",
        "assigned_location_ids.usage",
        "quant_ids",
        "quant_ids.quantity",
        "quant_ids.location_id",
        "quant_ids.location_id.usage",
        "location_id",
    )
    def _compute_location_id(self):
        StockLocation = self.env["stock.location"].sudo()
        StockQuant = self.env["stock.quant"].sudo()

        # 1) Map lot -> assigned silo (stock.location.lot_id)
        assigned_map = {}
        assigned_locations = StockLocation.search(
            [
                ("lot_id", "in", self.ids),
                ("usage", "=", "internal"),
            ],
            order="id asc",
        )

        for loc in assigned_locations:
            # si hay varias, nos quedamos con la primera por simplicidad
            assigned_map.setdefault(loc.lot_id.id, loc)

        # 2) Map lot -> location with max qty (from quants)
        qty_by_lot_loc = defaultdict(float)
        groups = StockQuant.read_group(
            domain=[
                ("lot_id", "in", self.ids),
                ("quantity", ">", 0),
                ("location_id.usage", "=", "internal"),
            ],
            fields=["quantity:sum", "lot_id", "location_id"],
            groupby=["lot_id", "location_id"],
            lazy=False,
        )

        for g in groups:
            lot_id = g["lot_id"][0] if g.get("lot_id") else False
            loc_id = g["location_id"][0] if g.get("location_id") else False
            qty = g.get("quantity_sum") or 0.0
            if lot_id and loc_id:
                qty_by_lot_loc[(lot_id, loc_id)] += qty

        best_quant_loc_by_lot = {}
        for (lot_id, loc_id), qty in qty_by_lot_loc.items():
            current = best_quant_loc_by_lot.get(lot_id)
            if not current or qty > current["qty"]:
                best_quant_loc_by_lot[lot_id] = {"loc_id": loc_id, "qty": qty}

        for lot in self:
            # Prioridad 1: silo asignado
            if assigned_map.get(lot.id):
                lot.location_id = assigned_map[lot.id]
                continue

            # Prioridad 2: ubicación por quants (existencia real)
            best = best_quant_loc_by_lot.get(lot.id)
            lot.location_id = best["loc_id"] if best else False

    def _ensure_location_lot_snapshot(self):
        """Freeze the first internal location full name into location_lot (one-time)."""
        for lot in self:
            if lot.location_lot:
                continue
            if lot.location_id:
                full_name = (
                    lot.location_id.complete_name
                    or lot.location_id.display_name
                    or lot.location_id.name
                )
                lot.sudo().with_context(skip_location_lot_snapshot=True).write(
                    {"location_lot": full_name}
                )

    @api.model_create_multi
    def create(self, vals_list):
        lots = super().create(vals_list)
        # Try to snapshot on create (may be empty if location_id isn't computed yet)
        lots._ensure_location_lot_snapshot()
        return lots

    def read(self, fields=None, load="_classic_read"):
        res = super().read(fields=fields, load=load)
        # Snapshot on first open/read (only for missing ones)
        if not self.env.context.get("skip_location_lot_snapshot"):
            self._ensure_location_lot_snapshot()
        return res
