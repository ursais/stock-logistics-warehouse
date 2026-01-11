# Copyright (C) 2011 Julius Network Solutions SARL <contact@julius.fr>
# Copyright 2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)


from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class StockMoveLocationWizardLine(models.TransientModel):
    _name = "wiz.stock.move.location.line"
    _description = "Wizard move location line"

    move_location_wizard_id = fields.Many2one(
        string="Move location Wizard",
        comodel_name="wiz.stock.move.location",
    )
    product_id = fields.Many2one(
        string="Product", comodel_name="product.product", required=True
    )
    origin_location_id = fields.Many2one(
        string="Origin Location", comodel_name="stock.location"
    )
    destination_location_id = fields.Many2one(
        string="Destination Location",
        comodel_name="stock.location",
        compute="_compute_destination_location_id",
    )
    product_uom_id = fields.Many2one(
        string="Product Unit of Measure", comodel_name="uom.uom"
    )
    lot_id = fields.Many2one(
        string="Lot/Serial Number",
        comodel_name="stock.lot",
        domain="[('product_id','=',product_id)]",
    )
    package_id = fields.Many2one(
        string="Package Number",
        comodel_name="stock.package",
        domain="[('location_id', '=', origin_location_id)]",
    )
    owner_id = fields.Many2one(comodel_name="res.partner", string="From Owner")
    product_uom_qty = fields.Float(string="Quantity", digits="Product Unit of Measure")
    max_quantity = fields.Float(
        string="Maximum available quantity", digits="Product Unit of Measure"
    )
    total_quantity = fields.Float(
        string="Total existence quantity", digits="Product Unit of Measure"
    )
    reserved_quantity = fields.Float(digits="Product Unit of Measure")
    custom = fields.Boolean(string="Custom line", default=True)

    @api.depends("move_location_wizard_id.destination_location_id")
    def _compute_destination_location_id(self):
        for record in self:
            record.destination_location_id = (
                record.move_location_wizard_id.destination_location_id
            )

    @api.constrains("max_quantity", "product_uom_qty")
    def _constraint_max_move_quantity(self):
        for record in self:
            rounding = record.product_uom_id.rounding
            move_qty_gt_max_qty = (
                float_compare(record.product_uom_qty, record.max_quantity, rounding)
                == 1
            )
            move_qty_lt_0 = float_compare(record.product_uom_qty, 0.0, rounding) == -1
            if move_qty_gt_max_qty or move_qty_lt_0:
                raise ValidationError(
                    self.env._(
                        "Move quantity can not exceed max quantity or be negative"
                    )
                )

    def group_by_product(self):
        """Group lines by product_id."""
        lines_grouped = {}
        for line in self:
            lines_grouped.setdefault(line.product_id.id, self.browse())
            lines_grouped[line.product_id.id] |= line
        return lines_grouped

    def calculate_total_quantity(self, wizard):
        """Calculate total quantity for this group of lines."""
        qty = 0
        for line in self:
            if wizard.env.context.get("planned"):
                line_qty = line.product_uom_qty
            else:
                available_qty = wizard._get_stock_quantities(
                    line.product_id, line.lot_id, line.package_id, line.owner_id
                )
                line_qty = (
                    min(available_qty, line.product_uom_qty) if available_qty else 0
                )
            qty += line_qty
        return qty

    def create_move_lines(self, picking, move):
        for line in self:
            values = line._get_move_line_values(picking, move)
            if values.get("quantity") <= 0:
                continue
            self.env["stock.move.line"].create(values)
        return True

    def _get_move_line_values(self, picking, move):
        self.ensure_one()
        location_dest_id = (
            self.move_location_wizard_id.apply_putaway_strategy
            and self.destination_location_id._get_putaway_strategy(self.product_id).id
            or self.destination_location_id.id
        )
        # Use the move's quantity to ensure consistency between move and move line
        qty_done = move.product_uom_qty
        return {
            "product_id": self.product_id.id,
            "lot_id": self.lot_id.id,
            "package_id": self.package_id.id,
            "result_package_id": self.package_id.id,
            "owner_id": self.owner_id.id,
            "location_id": self.origin_location_id.id,
            "location_dest_id": location_dest_id,
            "quantity": qty_done,
        }
