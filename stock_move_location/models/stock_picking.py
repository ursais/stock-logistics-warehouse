# Copyright 2016 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright Iryna Vyshnevska 2020 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_fillwithstock(self):
        # check source location has no children, i.e. we scanned a bin

        self.ensure_one()
        if self.move_ids:
            raise UserError(self.env._("Moves lines already exists"))
        context = {
            "active_ids": self._get_movable_quants().ids,
            "active_model": "stock.quant",
            "planned": True,
        }
        # FIXME: this action should not bypass the call to action_assign !!!
        move_wizard = (
            self.env["wiz.stock.move.location"]
            .with_context(**context)
            .create(
                {
                    "destination_location_id": self.location_dest_id.id,
                    "origin_location_id": self.location_id.id,
                    "picking_type_id": self.picking_type_id.id,
                    "picking_id": self.id,
                    "apply_putaway_strategy": True,
                }
            )
        )
        move_wizard.action_move_location()
        return True

    def _get_movable_quants(self):
        return (
            self.env["stock.quant"]
            .search(
                [
                    ("location_id", "=", self.location_id.id),
                    ("quantity", ">", 0.0),
                ]
            )
            .filtered(lambda quant: quant.quantity - quant.reserved_quantity > 0.0)
        )
