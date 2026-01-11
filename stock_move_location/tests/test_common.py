# Copyright (C) 2011 Julius Network Solutions SARL <contact@julius.fr>
# Copyright 2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import logging

from odoo.addons.base.tests.common import BaseCommon


class TestsCommon(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disable tracking for tests as recommended in Odoo 19.0 migration guide
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.location_obj = cls.env["stock.location"]
        cls.product_obj = cls.env["product.product"]
        cls.wizard_obj = cls.env["wiz.stock.move.location"]
        cls.quant_obj = cls.env["stock.quant"]
        cls.company = cls.env.ref("base.main_company")
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

        # Use all default Odoo data
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")

        # Create test locations under default warehouse structure
        cls.internal_loc_1 = cls.env["stock.location"].create(
            {
                "name": "Test Location 1",
                "usage": "internal",
                "location_id": cls.env.ref("stock.stock_location_stock").id,
                "company_id": cls.company.id,
            }
        )
        cls.internal_loc_2 = cls.env["stock.location"].create(
            {
                "name": "Test Location 2",
                "usage": "internal",
                "location_id": cls.env.ref("stock.stock_location_stock").id,
                "company_id": cls.company.id,
            }
        )
        cls.internal_loc_2_shelf = cls.env["stock.location"].create(
            {
                "name": "Shelf",
                "usage": "internal",
                "location_id": cls.internal_loc_2.id,
                "company_id": cls.company.id,
            }
        )

        # Create products with default category
        cls.pineapple_no_lots = cls.product_obj.create(
            {"name": "Pineapple", "is_storable": True, "tracking": "none"}
        )
        cls.apple_lots = cls.product_obj.create(
            {"name": "Apple", "is_storable": True, "tracking": "lot"}
        )
        cls.orange_package = cls.product_obj.create(
            {"name": "Orange", "is_storable": True, "tracking": "lot"}
        )

        # Create lots
        cls.lot1 = cls.env["stock.lot"].create(
            {
                "name": "lot1",
                "product_id": cls.apple_lots.id,
                "company_id": cls.company.id,
            }
        )
        cls.lot2 = cls.env["stock.lot"].create(
            {
                "name": "lot2",
                "product_id": cls.apple_lots.id,
                "company_id": cls.company.id,
            }
        )
        cls.lot3 = cls.env["stock.lot"].create(
            {
                "name": "lot3",
                "product_id": cls.apple_lots.id,
                "company_id": cls.company.id,
            }
        )
        cls.lot4 = cls.env["stock.lot"].create(
            {
                "name": "lot4",
                "product_id": cls.orange_package.id,
                "company_id": cls.company.id,
            }
        )
        cls.lot5 = cls.env["stock.lot"].create(
            {
                "name": "lot5",
                "product_id": cls.orange_package.id,
                "company_id": cls.company.id,
            }
        )

        # Create packages
        cls.package = cls.env["stock.package"].create({})
        cls.package1 = cls.env["stock.package"].create({})
        cls.package2 = cls.env["stock.package"].create({})

    def _log_location_inventory(self, location, message_prefix=""):
        """Helper to log inventory quantities in a location."""
        _logger = logging.getLogger(__name__)
        _logger.info(f"=== {message_prefix} Location: {location.name} ===")

        quants = self.env["stock.quant"].search([("location_id", "=", location.id)])
        if quants:
            for quant in quants:
                lot_info = f"Lot: {quant.lot_id.name}" if quant.lot_id else "No lot"
                package_info = (
                    f"Package: {quant.package_id.name}"
                    if quant.package_id
                    else "No package"
                )
                owner_info = (
                    f"Owner: {quant.owner_id.name}" if quant.owner_id else "No owner"
                )
                _logger.info(
                    f"  - {quant.product_id.display_name}: "
                    f"On-hand: {quant.quantity}, Available: {quant.available_quantity} "
                    f"({lot_info}, {package_info}, {owner_info})"
                )
        else:
            _logger.info("Location is empty")
        _logger.info("=" * 40)

    def _assert_all_stock_moved(self, from_location, to_location):
        """Helper to assert all test stock moved from one location to another."""
        # Check all products moved from source location
        self.check_product_amount(self.pineapple_no_lots, from_location, 0)
        self.check_product_amount(self.apple_lots, from_location, 0, self.lot1)
        self.check_product_amount(self.apple_lots, from_location, 0, self.lot2)
        self.check_product_amount(self.apple_lots, from_location, 0, self.lot3)
        self.check_product_amount(
            self.orange_package, from_location, 0, self.lot4, self.package
        )
        self.check_product_amount(
            self.orange_package, from_location, 0, self.lot4, self.package1
        )
        self.check_product_amount(
            self.orange_package,
            from_location,
            0,
            self.lot5,
            self.package2,
            self.partner,
        )

        # Check all products moved to destination location
        self.check_product_amount(self.pineapple_no_lots, to_location, 123)
        self.check_product_amount(self.apple_lots, to_location, 1, self.lot1)
        self.check_product_amount(self.apple_lots, to_location, 1, self.lot2)
        self.check_product_amount(self.apple_lots, to_location, 1, self.lot3)
        self.check_product_amount(
            self.orange_package, to_location, 1, self.lot4, self.package
        )
        self.check_product_amount(
            self.orange_package, to_location, 1, self.lot4, self.package1
        )
        self.check_product_amount(
            self.orange_package,
            to_location,
            1,
            self.lot5,
            self.package2,
            self.partner,
        )

    def _create_wizard_and_load_lines(self, origin_location, destination_location):
        """Helper to create wizard and load lines."""
        wizard = self._create_wizard(origin_location, destination_location)
        wizard.onchange_origin_location()
        return wizard

    def _create_quant_without_quantity(self, product, location):
        """Helper to create a quant without available quantity (for testing)."""
        self.quant_obj.create(
            {
                "product_id": product.id,
                "location_id": location.id,
            }
        )

    @classmethod
    def setup_product_amounts(cls):
        cls.set_product_amount(cls.pineapple_no_lots, cls.internal_loc_1, 123)
        cls.set_product_amount(cls.apple_lots, cls.internal_loc_1, 1.0, lot_id=cls.lot1)
        cls.set_product_amount(cls.apple_lots, cls.internal_loc_1, 1.0, lot_id=cls.lot2)
        cls.set_product_amount(cls.apple_lots, cls.internal_loc_1, 1.0, lot_id=cls.lot3)
        cls.set_product_amount(
            cls.orange_package,
            cls.internal_loc_1,
            1.0,
            lot_id=cls.lot4,
            package_id=cls.package,
        )
        cls.set_product_amount(
            cls.orange_package,
            cls.internal_loc_1,
            1.0,
            lot_id=cls.lot4,
            package_id=cls.package1,
        )
        cls.set_product_amount(
            cls.orange_package,
            cls.internal_loc_1,
            1.0,
            lot_id=cls.lot5,
            package_id=cls.package2,
            owner_id=cls.partner,
        )

    @classmethod
    def set_product_amount(
        cls, product, location, amount, lot_id=None, package_id=None, owner_id=None
    ):
        cls.env["stock.quant"]._update_available_quantity(
            product,
            location,
            amount,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
        )

    def check_product_amount(
        self, product, location, amount, lot_id=None, package_id=None, owner_id=None
    ):
        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                product,
                location,
                lot_id=lot_id,
                package_id=package_id,
                owner_id=owner_id,
            ),
            amount,
        )

    def _create_wizard(
        self, origin_location, destination_location, exclude_reserved_qty=False
    ):
        move_location_wizard = self.env["wiz.stock.move.location"]
        return move_location_wizard.create(
            {
                "origin_location_id": origin_location.id,
                "destination_location_id": destination_location.id,
                "exclude_reserved_qty": exclude_reserved_qty,
            }
        )

    def _create_putaway_for_product(self, product, loc_in, loc_out):
        putaway = self.env["stock.putaway.rule"].create(
            {
                "product_id": product.id,
                "location_in_id": loc_in.id,
                "location_out_id": loc_out.id,
            }
        )
        loc_in.write({"putaway_rule_ids": [(4, putaway.id, 0)]})
