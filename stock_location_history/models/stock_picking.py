# Part of OCA. See LICENSE file for full copyright and licensing details.
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        # Sync ticket moves for lots when incoming picking is validated.
        # This ensures ticket_move_ids (One2many) is populated so that
        # computed quality fields on stock.lot can depend on it (searchable).
        for picking in self:
            if picking.picking_type_code != "incoming" or picking.state != "done":
                continue
            lots = picking.move_line_ids.mapped("lot_id").filtered("id")
            if lots:
                lots._sync_ticket_moves()
        return res
