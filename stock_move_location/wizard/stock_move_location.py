# Copyright (C) 2011 Julius Network Solutions SARL <contact@julius.fr>
# Copyright 2018 Camptocamp SA
# Copyright 2019 Sergio Teruel - Tecnativa <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)


import logging

from odoo import Command, api, fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class StockMoveLocationWizard(models.TransientModel):
    _name = "wiz.stock.move.location"
    _description = "Wizard move location"

    origin_location_disable = fields.Boolean(
        compute="_compute_readonly_locations",
        help="technical field to disable the edition of origin location.",
    )
    origin_location_id = fields.Many2one(
        string="Origin Location",
        comodel_name="stock.location",
        required=True,
        domain=lambda self: self._get_locations_domain(),
    )
    destination_location_disable = fields.Boolean(
        compute="_compute_readonly_locations",
        help="technical field to disable the edition of destination location.",
    )
    destination_location_id = fields.Many2one(
        string="Destination Location",
        comodel_name="stock.location",
        required=True,
        domain=lambda self: self._get_locations_domain(),
    )
    stock_move_location_line_ids = fields.One2many(
        "wiz.stock.move.location.line",
        "move_location_wizard_id",
        string="Move Location lines",
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    picking_type_id = fields.Many2one(
        compute="_compute_picking_type_id",
        comodel_name="stock.picking.type",
        readonly=False,
        store=True,
        domain="[('company_id', '=', company_id), ('code', '=', 'internal')]",
    )
    picking_id = fields.Many2one(
        string="Connected Picking", comodel_name="stock.picking"
    )
    edit_locations = fields.Boolean(default=True)
    apply_putaway_strategy = fields.Boolean()
    exclude_reserved_qty = fields.Boolean(default=True)

    @api.depends("edit_locations")
    def _compute_readonly_locations(self):
        for rec in self:
            rec.origin_location_disable = self.env.context.get(
                "origin_location_disable", False
            )
            rec.destination_location_disable = self.env.context.get(
                "destination_location_disable", False
            )
            if not rec.edit_locations:
                rec.origin_location_disable = True
                rec.destination_location_disable = True

    @api.depends_context("company")
    @api.depends("origin_location_id")
    def _compute_picking_type_id(self):
        for rec in self:
            picking_type = self.env["stock.picking.type"]
            base_domain = [
                ("code", "=", "internal"),
                ("warehouse_id.company_id", "=", self.company_id.id),
            ]
            if rec.origin_location_id:
                location_id = rec.origin_location_id
                if (
                    location_id
                    and rec.picking_type_id
                    and rec.picking_type_id.default_location_src_id == location_id
                ):
                    continue
                while location_id and not picking_type:
                    domain = Domain(
                        [("default_location_src_id", "=", location_id.id)]
                    ) & Domain(base_domain)
                    picking_type = picking_type.search(domain, limit=1)
                    # Move up to the parent location if no picking type found
                    location_id = not picking_type and location_id.location_id or False
            if not picking_type:
                picking_type = picking_type.search(base_domain, limit=1)
            rec.picking_type_id = picking_type.id

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get("active_model", False) != "stock.quant":
            return res
        # Load data directly from quants
        quants = self.env["stock.quant"].browse(
            self.env.context.get("active_ids", False)
        )
        res["stock_move_location_line_ids"] = self._prepare_wizard_move_lines(quants)
        res["origin_location_id"] = quants[0].location_id.id if quants else False
        return res

    @api.model
    def _prepare_wizard_move_lines(self, quants):
        res = []
        if not self.exclude_reserved_qty:
            res = [
                (
                    0,
                    0,
                    {
                        "product_id": quant.product_id.id,
                        "move_quantity": quant.quantity,
                        "max_quantity": quant.quantity,
                        "reserved_quantity": quant.reserved_quantity,
                        "total_quantity": quant.quantity,
                        "origin_location_id": quant.location_id.id,
                        "lot_id": quant.lot_id.id,
                        "package_id": quant.package_id.id,
                        "owner_id": quant.owner_id.id,
                        "product_uom_id": quant.product_uom_id.id,
                        "custom": False,
                    },
                )
                for quant in quants
            ]
        else:
            # if need move only available qty per product on location
            for quant in quants:
                qty = quant._get_available_quantity(
                    quant.product_id,
                    quant.location_id,
                    quant.lot_id,
                    quant.package_id,
                    quant.owner_id,
                )
                if qty:
                    res.append(
                        (
                            0,
                            0,
                            {
                                "product_id": quant.product_id.id,
                                "move_quantity": qty,
                                "max_quantity": qty,
                                "reserved_quantity": quant.reserved_quantity,
                                "total_quantity": quant.quantity,
                                "origin_location_id": quant.location_id.id,
                                "lot_id": quant.lot_id.id,
                                "package_id": quant.package_id.id,
                                "owner_id": quant.owner_id.id,
                                "product_uom_id": quant.product_uom_id.id,
                                "custom": False,
                            },
                        )
                    )
        return res

    def _clear_lines(self):
        self.stock_move_location_line_ids = False

    def _get_locations_domain(self):
        return [
            "|",
            ("company_id", "=", self.env.company.id),
            ("company_id", "=", False),
        ]

    def _create_picking(self):
        return self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_id.id,
                "location_id": self.origin_location_id.id,
                "location_dest_id": self.destination_location_id.id,
            }
        )

    def _create_moves(self, picking):
        self.ensure_one()
        groups = self.stock_move_location_line_ids.group_by_product()
        moves = self.env["stock.move"]

        # INSTRUMENTATION: Log what we're processing
        _logger = logging.getLogger(__name__)
        _logger.info("=== INSTRUMENTATION: _create_moves ===")
        _logger.info(f"exclude_reserved_qty: {self.exclude_reserved_qty}")
        _logger.info(f"Number of line groups: {len(groups)}")

        for _product_id, lines in groups.items():
            _logger.info(f"Processing group for product {lines[0].product_id.name}")

            move = self._create_move(picking, lines)
            if move:
                moves |= move
                product_name = lines[0].product_id.name
                _logger.info(f"✅ Created move for {product_name}")
            else:
                product_name = lines[0].product_id.name
                _logger.info(f"❌ Skipped zero quantity move for {product_name}")

        _logger.info(f"Total moves created: {len(moves)}")
        return moves

    def _get_move_values(self, picking, lines):
        # locations are same for the products
        location_from_id = lines[0].origin_location_id.id
        location_to_id = lines[0].destination_location_id.id
        product = lines[0].product_id
        product_uom_id = lines[0].product_uom_id.id

        # Calculate total quantity using line model method
        qty = lines.calculate_total_quantity(self)
        _logger.info(f"Group move quantity: {qty}")

        # Return None for zero quantities to avoid creating moves
        if qty <= 0:
            return None

        return {
            "location_id": location_from_id,
            "location_dest_id": location_to_id,
            "product_id": product.id,
            "product_uom": product_uom_id,
            "product_uom_qty": qty,
            "picking_id": picking.id,
            "location_move": True,
        }

    def _create_move(self, picking, lines):
        self.ensure_one()
        move_values = self._get_move_values(picking, lines)
        if not move_values:
            return None

        move = self.env["stock.move"].create(move_values)
        lines.create_move_lines(picking, move)
        if self.env.context.get("planned"):
            move._action_confirm()
        else:
            # Force the state to be assigned, instead of _action_assign,
            # to avoid discarding the selected move_location_line.
            move.state = "assigned"
            move.move_line_ids.filtered(lambda ml: not ml.quantity).unlink()
            move.move_line_ids.write({"state": "assigned"})
        return move

    def _unreserve_moves(self, picking):
        """
        Unreserve moves from other pickings that have reservations for the same
        products/locations/lots/packages/owners as the items being moved.

        This ensures that when stock is moved from one location to another,
        any existing reservations for that stock are properly released so
        the stock can be reassigned to the new location.

        :param picking: The picking that will receive the moved stock
        :return: Recordset of moves that were unreserved and need reassignment
        """
        lines_to_check = self.stock_move_location_line_ids.filtered(
            lambda line: not line.origin_location_id.should_bypass_reservation()
        )
        if not lines_to_check:
            return self.env["stock.move"]

        base_domain = Domain(
            [
                ("state", "=", "assigned"),
                ("quantity", ">", 0.0),
                ("picking_id", "!=", picking.id),
            ]
        )
        # Add OR conditions for each line's specific combination
        for line in lines_to_check:
            line_domain = Domain(
                [
                    ("product_id", "=", line.product_id.id),
                    ("location_id", "=", line.origin_location_id.id),
                    ("lot_id", "=", line.lot_id.id),
                    ("package_id", "=", line.package_id.id),
                    ("owner_id", "=", line.owner_id.id),
                ]
            )
            base_domain = base_domain | line_domain
        # Find and unreserve conflicting moves
        MoveLine = self.env["stock.move.line"]
        conflicting_moves = MoveLine.search(base_domain).mapped("move_id")
        if conflicting_moves:
            conflicting_moves._do_unreserve()
        return conflicting_moves

    def action_move_location(self):
        self.ensure_one()
        picking = self.picking_id if self.picking_id else self._create_picking()
        moves = self._create_moves(picking)

        # INSTRUMENTATION: Log what we found
        _logger = logging.getLogger(__name__)
        _logger.info("=== INSTRUMENTATION: action_move_location ===")
        _logger.info(f"exclude_reserved_qty: {self.exclude_reserved_qty}")
        _logger.info(f"Total moves created: {len(moves)}")

        for move in moves:
            product_name = move.product_id.name
            qty = move.product_uom_qty
            move_info = f"  Move {move.id}: {product_name} - Qty: {qty}"
            _logger.info(move_info)

            # Log move lines for this move
            for line in move.move_line_ids:
                line_info = f"    Line {line.id}: Qty {line.quantity}"
                _logger.info(line_info)

        # Check if picking has any moves with positive quantities
        positive_moves = moves.filtered(lambda m: m.product_uom_qty > 0)
        _logger.info(f"Positive moves: {len(positive_moves)}")

        # Only proceed if we actually created moves with positive quantities
        if not positive_moves:
            _logger.info("No positive moves - SKIPPING VALIDATION")
            self.picking_id = picking
            return self._get_picking_action(picking.id)

        _logger.info("Proceeding with validation")
        if not self.env.context.get("planned"):
            moves_to_reassign = self._unreserve_moves(picking)
            picking.button_validate()
            moves_to_reassign._action_assign()
        self.picking_id = picking
        return self._get_picking_action(picking.id)

    def _get_picking_action(self, picking_id):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        form_view = self.env.ref("stock.view_picking_form").id
        action.update(
            {"view_mode": "form", "views": [(form_view, "form")], "res_id": picking_id}
        )
        return action

    def _get_quants_domain(self):
        return [("location_id", "=", self.origin_location_id.id)]

    def _get_group_quants(self):
        domain = self._get_quants_domain()
        result = self.env["stock.quant"]._read_group(
            domain=domain,
            groupby=["product_id", "lot_id", "package_id", "owner_id"],
            aggregates=["quantity:sum", "reserved_quantity:sum"],
        )
        return result

    def _get_stock_quantities(self, product, lot, package, owner):
        """Get the appropriate quantity based on exclude_reserved_qty flag.

        Returns:
            float: The quantity to use (on-hand or available)
        """
        if not product:
            return 0.0

        # Use Odoo core method for available quantity
        available_qty = self.env["stock.quant"]._get_available_quantity(
            product_id=product,
            location_id=self.origin_location_id,
            lot_id=lot,
            package_id=package,
            owner_id=owner,
            strict=False,
        )

        # Use Odoo core method for on-hand quantity (sum of quant quantities)
        quants = self.env["stock.quant"]._gather(
            product_id=product,
            location_id=self.origin_location_id,
            lot_id=lot,
            package_id=package,
            owner_id=owner,
            strict=False,
        )
        on_hand_qty = sum(quant.quantity for quant in quants)

        # Apply exclude_reserved_qty logic
        if self.exclude_reserved_qty:
            return available_qty
        else:
            return on_hand_qty

    def _get_stock_move_location_lines_values(self):
        product_data = []
        for group in self._get_group_quants():
            product, lot, package, owner, total_qty, res_qty = group

            # Apply the putaway strategy
            location_dest_id = (
                product
                and self.apply_putaway_strategy
                and self.destination_location_id._get_putaway_strategy(product).id
                or self.destination_location_id.id
            )

            # Get the appropriate quantity based on exclude_reserved_qty flag
            max_qty = self._get_stock_quantities(product, lot, package, owner)

            product_data.append(
                {
                    "product_id": product.id,
                    "product_uom_qty": max_qty,
                    "max_quantity": max_qty,
                    "reserved_quantity": res_qty,
                    "total_quantity": total_qty,
                    "origin_location_id": self.origin_location_id.id,
                    "destination_location_id": location_dest_id,
                    # Extract IDs from record objects
                    "lot_id": lot.id,
                    "package_id": package.id,
                    "owner_id": owner.id,
                    "product_uom_id": product.uom_id.id,
                    "custom": False,
                }
            )
        return product_data

    @api.onchange("origin_location_id", "exclude_reserved_qty")
    def onchange_origin_location(self):
        # Get origin_location_disable context key to prevent load all origin
        # location products when user opens the wizard from stock quants to
        # move it to other location.
        if (
            not self.env.context.get("origin_location_disable")
            and self.origin_location_id
        ):
            lines = [Command.clear()] + [
                Command.create(line_vals)
                for line_vals in self._get_stock_move_location_lines_values()
                if line_vals.get("max_quantity", 0.0) > 0.0
            ]
            self.update({"stock_move_location_line_ids": lines})

    def clear_lines(self):
        self._clear_lines()
        return {"type": "ir.action.do_nothing"}
