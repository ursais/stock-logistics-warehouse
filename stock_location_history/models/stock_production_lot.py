# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockProductionLot(models.Model):
    _inherit = "stock.lot"

    consumption_move_line_ids = fields.One2many(
        comodel_name="stock.production.lot.line",
        inverse_name="lot_id",
        string="Consumption Move Lines",
        compute="_compute_consumption_move_line_ids",
        readonly=True,
        help="Lines of PLC batch consumptions where this lot was used as raw material.",
    )

    ticket_move_ids = fields.One2many(
        comodel_name="stock.production.ticket",
        inverse_name="lot_id",
        string="Ticket Lines",
        compute="_compute_ticket_move_ids",
        readonly=True,
        help="Lines of tickets and stock moves where this lot was received.",
    )

    def _compute_consumption_move_line_ids(self):
        # Ensure the table is always up to date when opening the lot form.
        self._sync_consumption_move_lines()
        LotLine = self.env["stock.production.lot.line"].sudo()
        for lot in self:
            lot.consumption_move_line_ids = LotLine.search(
                [("lot_id", "=", lot.id)],
                order="date desc, id desc",
            )

    def _sync_consumption_move_lines(self):
        lots = self.filtered(lambda l: l.id)
        if not lots:
            return

        BatchLine = self.env["mrp.batch.lines"].sudo()
        LotLine = self.env["stock.production.lot.line"].sudo()

        domain = [("lot_id", "in", lots.ids)]
        batch_lines = BatchLine.search(domain)

        # Build a lookup to avoid duplicates and to update existing lines.
        existing = LotLine.search([("lot_id", "in", lots.ids)])
        existing_map = {
            (l.lot_id.id, l.mrp_batch_id.id, l.batch_line or "", l.product_id.id): l
            for l in existing
        }

        for bl in batch_lines:
            lot = bl.lot_id
            if not lot:
                continue

            # Safety: ensure the raw material matches the lot product, if present.
            if lot.product_id and bl.product_id and bl.product_id.id != lot.product_id.id:
                continue

            batch = bl.batch_id
            if not batch:
                continue

            product_tmpl = bl.product_id.product_tmpl_id if bl.product_id else False
            if not product_tmpl:
                continue

            key = (lot.id, batch.id, bl.number or "", product_tmpl.id)

            vals = {
                "lot_id": lot.id,
                "mo_id": batch.mrp_id.id if batch.mrp_id else False,
                "product_id": product_tmpl.id,
                "mrp_batch_id": batch.id,
                "num_mez": batch.num_mez,
                "batch_line": bl.number,
                "weight": bl.weight,
                "product_uom_id": bl.product_id.uom_id.id if bl.product_id else False,
                "date": batch.date_start or batch.create_date,
                "lote_prod": batch.lote_prod,
            }

            rec = existing_map.get(key)
            if rec:
                changed = False
                for k in vals.keys():
                    if k not in rec._fields:
                        continue
                    field = rec._fields[k]
                    rec_value = rec[k]
                    val_value = vals[k]
                    # For Many2one fields, compare IDs instead of recordsets
                    if field.type == 'many2one':
                        rec_id = rec_value.id if rec_value else False
                        if rec_id != val_value:
                            changed = True
                            break
                    else:
                        if rec_value != val_value:
                            changed = True
                            break
                if changed:
                    rec.write(vals)
            else:
                rec = LotLine.create(vals)
                existing_map[key] = rec

    def _compute_ticket_move_ids(self):
        self._sync_ticket_moves()
        Ticket = self.env["stock.production.ticket"].sudo()
        for lot in self:
            lot.ticket_move_ids = Ticket.search(
                [("lot_id", "=", lot.id)],
                order="date desc, id desc",
            )

    def _sync_ticket_moves(self):
        lots = self.filtered(lambda l: l.id)
        if not lots:
            return

        MoveLine = self.env["stock.move.line"].sudo()
        Ticket = self.env["stock.production.ticket"].sudo()

        move_lines = MoveLine.search([
            ("lot_id", "in", lots.ids),
            ("move_id.picking_id.picking_type_id.code", "=", "incoming"),
            ("move_id.picking_id.state", "=", "done"),
        ])

        # Build desired keys: (lot, purchase_order, picking)
        desired = {}
        desired_date = {}

        for ml in move_lines:
            picking = ml.move_id.picking_id
            if not picking:
                continue

            po = picking.purchase_id or ml.move_id.purchase_line_id.order_id
            if not po:
                continue

            key = (ml.lot_id.id, po.id, picking.id)

            desired[key] = desired.get(key, 0.0) + (ml.qty_done or 0.0)
            desired_date[key] = picking.date_done or picking.scheduled_date or picking.create_date

        # Existing lines
        existing = Ticket.search([("lot_id", "in", lots.ids)])
        existing_map = {(t.lot_id.id, t.puchase_id.id, t.move_id.id): t for t in existing}

        desired_keys = set(desired.keys())

        # Remove stale lines (optional but keeps table clean)
        for key, rec in existing_map.items():
            if key not in desired_keys:
                rec.unlink()

        # Upsert desired lines
        for key, qty in desired.items():
            lot_id, po_id, picking_id = key
            vals = {
                "lot_id": lot_id,
                "purchase_id": po_id,
                "move_id": picking_id,
                "qty_received": qty,
                "date": desired_date.get(key),
            }
            rec = existing_map.get(key)
            if rec:
                rec.write(vals)
            else:
                Ticket.create(vals)

class StockProductionLotLine(models.Model):
    _name = "stock.production.lot.line"
    _description = "Stock Production Lot Line"
    _order = "lot_id, date desc, id desc"

    _sql_constraints = [
        (
            "uniq_lot_batch_line_product",
            "unique(lot_id, mrp_batch_id, batch_line, product_id)",
            "This consumption line already exists for this macrolot.",
        )
    ]

    lot_id = fields.Many2one("stock.lot", string="Lot", index=True, required=True)
    mo_id = fields.Many2one(comodel_name="mrp.production", string="MO", readonly=True, store=True)
    product_id = fields.Many2one("product.template", string="Product", readonly=True)
    mrp_batch_id = fields.Many2one(comodel_name="mrp.batch.plc", string="Batch", readonly=True, index=True)
    num_mez = fields.Char(string="MZ Number", readonly=True)
    #number = fields.Char(string="MZ Number", readonly=True)
    #mix_number = fields.Char(string="Mixed Number", readonly=True)
    lote_prod = fields.Char(string="Lote Prod", readonly=True)
    batch_line = fields.Char(string="Batch Line", readonly=True)
    weight = fields.Float(string="Weight", readonly=True, digits="Product Unit of Measure")
    product_uom_id = fields.Many2one(comodel_name="uom.uom", string="UOM", readonly=True)
    date = fields.Datetime(string="Date", readonly=True)

class StockProductionTicket(models.Model):
    _name = "stock.production.ticket"
    _description = "Stock Production Ticket"
    _order = "lot_id, id desc"

    _sql_constraints = [
        ("uniq_lot_po_picking", "unique(lot_id, puchase_id, move_id)", "This ticket line already exists."),
    ]

    lot_id = fields.Many2one("stock.lot", string="Lot", index=True, required=True)
    purchase_id = fields.Many2one("purchase.order", string="Purchase", readonly=True)
    puchase_id = fields.Many2one("purchase.order", string="Purchase", readonly=True)
    move_id = fields.Many2one("stock.picking", string="Move", index=True, required=True)
    qty_received = fields.Float(string="Qty Received", store=True)
    peso_especifico = fields.Float(string="Peso Específico (g/l)", digits=(6, 2),
                                   help="Peso específico del grano (g/l)")
    humedad = fields.Float(string="Humedad %", digits=(5, 2), help="Porcentaje de humedad del grano")
    temperatura = fields.Float(string="Temperatura °C", digits=(5, 2),
                               help="Temperatura del grano al momento de recepción")
    pct_finos = fields.Float(string="% Finos", digits=(5, 2), help="Porcentaje de finos")
    pct_quebrados = fields.Float(string="% Quebrados", digits=(5, 2), help="Porcentaje de granos quebrados")
    impurezas = fields.Float(string="Impurezas (F+Q) %", digits=(5, 2), compute="_compute_suma_impurezas",
                                  store=True, help="Suma de finos y quebrados (impurezas totales)")
    date = fields.Datetime(string="Date", readonly=True)

    # Computed fields for reports
    @api.depends("pct_finos", "pct_quebrados")
    def _compute_suma_impurezas(self):
        for lot in self:
            lot.impurezas = (lot.pct_finos or 0) + (lot.pct_quebrados or 0)
