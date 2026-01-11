# Copyright (C) 2011 Julius Network Solutions SARL <contact@julius.fr>
# Copyright 2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo.exceptions import ValidationError

from .test_common import TestsCommon


class TestMoveLocation(TestsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_product_amounts()

    def test_move_location_wizard(self):
        """Test a simple move."""
        wizard = self._create_wizard_and_load_lines(
            self.internal_loc_1, self.internal_loc_2
        )
        # Log inventory before wizard move
        self._log_location_inventory(self.internal_loc_1, "BEFORE Wizard Move")
        self._log_location_inventory(self.internal_loc_2, "BEFORE Wizard Move")
        wizard.action_move_location()
        # Log inventory after wizard move
        self._log_location_inventory(self.internal_loc_1, "AFTER Wizard Move")
        self._log_location_inventory(self.internal_loc_2, "AFTER Wizard Move")
        self._assert_all_stock_moved(self.internal_loc_1, self.internal_loc_2)

    def test_move_location_wizard_amount(self):
        """Can't move more than exists."""
        wizard = self._create_wizard(self.internal_loc_1, self.internal_loc_2)
        wizard.onchange_origin_location()
        with self.assertRaises(ValidationError):
            wizard.stock_move_location_line_ids[0].move_quantity += 1

    def test_wizard_clear_lines(self):
        """Test lines getting cleared properly."""
        wizard = self._create_wizard_and_load_lines(
            self.internal_loc_1, self.internal_loc_2
        )
        self.assertEqual(len(wizard.stock_move_location_line_ids), 7)
        dest_location_line = wizard.stock_move_location_line_ids.mapped(
            "destination_location_id"
        )
        self.assertEqual(dest_location_line, wizard.destination_location_id)
        wizard.clear_lines()
        self.assertEqual(len(wizard.stock_move_location_line_ids), 0)

    def test_wizard_onchange_origin_location(self):
        """Test a product that have existing quants with undefined quantity."""
        product_not_available = self.env["product.product"].create(
            {"name": "Mango", "is_storable": True, "tracking": "none"}
        )
        self._create_quant_without_quantity(product_not_available, self.internal_loc_1)
        wizard = self._create_wizard_and_load_lines(
            self.internal_loc_1, self.internal_loc_2
        )
        # we check there is no line for product_not_available
        self.assertEqual(
            len(
                wizard.stock_move_location_line_ids.filtered(
                    lambda x: x.product_id.id == product_not_available.id
                )
            ),
            0,
        )

    def test_planned_transfer(self):
        """Test planned transfer."""
        wizard = self._create_wizard_and_load_lines(
            self.internal_loc_1, self.internal_loc_2
        )
        wizard = wizard.with_context(planned=True)
        wizard.action_move_location()
        picking = wizard.picking_id
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(
            len(wizard.stock_move_location_line_ids), len(picking.move_line_ids)
        )
        wizard_lines = sorted(
            [
                (line.product_id.id, line.lot_id.id, line.move_quantity)
                for line in wizard.stock_move_location_line_ids
            ],
            key=lambda x: (x[0], x[1]),
        )
        picking_lines = sorted(
            [
                (line.product_id.id, line.lot_id.id, line.quantity)
                for line in picking.move_line_ids
            ],
            key=lambda x: (x[0], x[1]),
        )
        self.assertEqual(
            wizard_lines,
            picking_lines,
            "Mismatch between move location lines and move lines",
        )
        self.assertEqual(
            sorted(picking.move_line_ids.mapped("quantity")),
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 123.0],
        )

    def test_planned_transfer_strict(self):
        product = self.env["product.product"].create(
            {"name": "Test", "is_storable": True, "tracking": "lot"}
        )
        lot = self.env["stock.lot"].create(
            {
                "name": "Test lot",
                "product_id": product.id,
            }
        )
        self.set_product_amount(
            product,
            self.internal_loc_1,
            10.0,
        )
        self.set_product_amount(
            product,
            self.internal_loc_1,
            10.0,
            lot_id=lot,
        )
        wizard = self._create_wizard(self.internal_loc_1, self.internal_loc_2)
        wizard.onchange_origin_location()
        wizard = wizard.with_context(planned=True)
        location_lines = wizard.stock_move_location_line_ids.filtered(
            lambda r: r.product_id.id != product.id or r.lot_id.id != lot.id
        )
        location_lines.unlink()
        wizard.action_move_location()
        picking = wizard.picking_id
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(
            len(wizard.stock_move_location_line_ids), len(picking.move_line_ids)
        )
        location_line = wizard.stock_move_location_line_ids
        wizard_lines = [
            location_line.product_id.id,
            location_line.lot_id.id,
            location_line.move_quantity,
        ]
        line = picking.move_line_ids
        picking_lines = [line.product_id.id, line.lot_id.id, line.quantity]
        self.assertEqual(
            wizard_lines,
            picking_lines,
            "Mismatch between move location lines and move lines",
        )
        self.assertEqual(
            picking.move_line_ids.quantity,
            10.0,
        )

        # Create planned transfer for same quant
        wizard = self._create_wizard(self.internal_loc_1, self.internal_loc_2)
        wizard.onchange_origin_location()
        wizard = wizard.with_context(planned=True)
        location_lines = wizard.stock_move_location_line_ids.filtered(
            lambda r: r.product_id.id != product.id or r.lot_id.id != lot.id
        )
        location_lines.unlink()
        wizard.action_move_location()
        picking = wizard.picking_id
        # Planned transfer state is "confirmed"
        # move lines (quantity is zero) are removed
        self.assertEqual(picking.state, "confirmed")
        self.assertFalse(picking.move_line_ids)

    def test_quant_transfer(self):
        """Test quants transfer."""
        quants = self.apple_lots.stock_quant_ids
        wizard = self.wizard_obj.with_context(
            active_model="stock.quant",
            active_ids=quants.ids,
            origin_location_disable=True,
        ).create(
            {
                "origin_location_id": quants[:1].location_id.id,
                "destination_location_id": self.internal_loc_2.id,
            }
        )
        lines = wizard.stock_move_location_line_ids
        self.assertEqual(len(lines), 3)
        wizard.onchange_origin_location()
        self.assertEqual(len(lines), 3)
        wizard.destination_location_id = self.internal_loc_1
        self.assertEqual(lines.mapped("destination_location_id"), self.internal_loc_1)
        wizard.origin_location_id = self.internal_loc_2
        self.assertEqual(len(lines), 3)

    def test_readonly_location_computation(self):
        """Test that origin_location_disable and destination_location_disable
        are computed correctly."""
        wizard = self._create_wizard(self.internal_loc_1, self.internal_loc_2)
        # locations are editable.
        self.assertFalse(wizard.origin_location_disable)
        self.assertFalse(wizard.destination_location_disable)
        # Disable edit mode:
        wizard.edit_locations = False
        self.assertTrue(wizard.origin_location_disable)
        self.assertTrue(wizard.destination_location_disable)

    def test_picking_type_action_dummy(self):
        """Test that no error is raised from actions."""
        pick_type = self.env.ref("stock.picking_type_internal")
        pick_type.action_move_location()

    def test_wizard_with_putaway_strategy(self):
        """Test that Putaway strategies are being applied."""
        self._create_putaway_for_product(
            self.pineapple_no_lots, self.internal_loc_2, self.internal_loc_2_shelf
        )
        wizard = self._create_wizard(self.internal_loc_1, self.internal_loc_2)
        wizard.apply_putaway_strategy = True
        wizard.onchange_origin_location()
        putaway_line = wizard.stock_move_location_line_ids.filtered(
            lambda p: p.product_id == self.pineapple_no_lots
        )[0]
        self.assertEqual(
            putaway_line.destination_location_id, wizard.destination_location_id
        )
        picking_action = wizard.action_move_location()
        picking = self.env["stock.picking"].browse(picking_action["res_id"])
        move_lines = picking.move_line_ids.filtered(
            lambda sml: sml.product_id == self.pineapple_no_lots
        )
        self.assertEqual(move_lines.location_dest_id, self.internal_loc_2_shelf)

    def test_delivery_order_assignation_after_transfer(self):
        """
        Make sure using the wizard doesn't break assignation on delivery orders
        """
        delivery_order_type = self.env.ref("stock.picking_type_out")
        internal_transfer_type = self.env.ref("stock.picking_type_internal")
        stock_location = self.env.ref("stock.stock_location_stock")
        wh_stock_shelf_1 = self.env["stock.location"].create(
            {
                "name": "Shelf 1",
                "usage": "internal",
                "location_id": stock_location.id,
                "company_id": self.env.ref("base.main_company").id,
            }
        )
        wh_stock_shelf_2 = wh_stock_shelf_1.copy({"name": "Shelf 2"})
        wh_stock_shelf_3 = wh_stock_shelf_1.copy({"name": "Shelf 3"})

        # Create some quants
        self.set_product_amount(
            self.apple_lots, wh_stock_shelf_1, 100, lot_id=self.lot1
        )

        # Create and assign a delivery picking to reserve some quantities
        delivery_picking = self.env["stock.picking"].create(
            {
                "picking_type_id": delivery_order_type.id,
                "location_id": wh_stock_shelf_1.id,
            }
        )
        delivery_move = self.env["stock.move"].create(
            {
                "product_id": self.apple_lots.id,
                "product_uom_qty": 20.0,
                "product_uom": self.apple_lots.uom_id.id,
                "location_id": wh_stock_shelf_1.id,
                "location_dest_id": delivery_picking.location_dest_id.id,
                "picking_id": delivery_picking.id,
            }
        )
        delivery_picking.action_confirm()
        self.assertEqual(delivery_picking.state, "assigned")
        self.assertEqual(delivery_move.move_line_ids.location_id, wh_stock_shelf_1)

        # Move all quantities to other location using module's wizard
        wizard = self._create_wizard(wh_stock_shelf_1, wh_stock_shelf_2)
        wizard.onchange_origin_location()
        # Log inventory before wizard move
        self._log_location_inventory(
            wh_stock_shelf_1, "BEFORE Wizard Move (Delivery Order Test)"
        )
        self._log_location_inventory(
            wh_stock_shelf_2, "BEFORE Wizard Move (Delivery Order Test)"
        )
        wizard.action_move_location()
        # Log inventory after wizard move
        self._log_location_inventory(
            wh_stock_shelf_1, "AFTER Wizard Move (Delivery Order Test)"
        )
        self._log_location_inventory(
            wh_stock_shelf_2, "AFTER Wizard Move (Delivery Order Test)"
        )
        self.assertEqual(delivery_picking.state, "assigned")
        self.assertEqual(delivery_move.move_line_ids.location_id, wh_stock_shelf_2)

        # Do a planned transfer to move quantities to other location
        #  without using module's wizard
        internal_picking = self.env["stock.picking"].create(
            {
                "picking_type_id": internal_transfer_type.id,
                "location_id": wh_stock_shelf_2.id,
                "location_dest_id": wh_stock_shelf_3.id,
            }
        )
        self.env["stock.move"].create(
            {
                "product_id": self.apple_lots.id,
                "product_uom_qty": 100.0,
                "product_uom": self.apple_lots.uom_id.id,
                "location_id": internal_picking.location_id.id,
                "location_dest_id": internal_picking.location_dest_id.id,
                "picking_id": internal_picking.id,
            }
        )
        # Unreserve quantity on the delivery to allow moving the quantity
        delivery_picking.do_unreserve()
        self.assertEqual(delivery_picking.state, "confirmed")
        internal_picking.action_confirm()
        internal_picking.action_assign()
        internal_picking.move_line_ids.quantity = (
            internal_picking.move_line_ids.quantity
        )
        internal_picking.button_validate()
        self.assertEqual(internal_picking.state, "done")
        # Assign the delivery must work
        delivery_picking.action_assign()
        self.assertEqual(delivery_picking.state, "assigned")
        # The old reserved quantities must be in new location after confirm wizard
        self.assertEqual(len(delivery_move.move_line_ids), 1)
        self.assertEqual(delivery_move.move_line_ids.quantity, 20.0)
        self.assertEqual(delivery_move.move_line_ids.location_id, wh_stock_shelf_3)
