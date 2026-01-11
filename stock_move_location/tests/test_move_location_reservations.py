# Copyright 2024 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from .test_common import TestsCommon


class TestMoveLocationReservations(TestsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_product_amounts()

    def test_move_location_wizard_ignore_reserved(self):
        """Can't move more than exists."""
        wizard = self._create_wizard_and_load_lines(
            self.internal_loc_1, self.internal_loc_2
        )
        # Set exclude_reserved_qty to False to move everything including reservations
        wizard.exclude_reserved_qty = False
        # reserve some quants
        self.quant_obj._update_reserved_quantity(
            self.pineapple_no_lots, self.internal_loc_1, 50
        )
        self.quant_obj._update_reserved_quantity(
            self.apple_lots, self.internal_loc_1, 1, lot_id=self.lot1
        )
        # Log inventory before wizard move
        self._log_location_inventory(
            self.internal_loc_1, "BEFORE Wizard Move (Ignore Reserved)"
        )
        self._log_location_inventory(
            self.internal_loc_2, "BEFORE Wizard Move (Ignore Reserved)"
        )
        # doesn't care about reservations, everything is moved
        wizard.action_move_location()
        # Log inventory after wizard move
        self._log_location_inventory(
            self.internal_loc_1, "AFTER Wizard Move (Ignore Reserved)"
        )
        self._log_location_inventory(
            self.internal_loc_2, "AFTER Wizard Move (Ignore Reserved)"
        )
        self.check_product_amount(self.pineapple_no_lots, self.internal_loc_1, 0)
        self.check_product_amount(self.pineapple_no_lots, self.internal_loc_2, 123)
        self.check_product_amount(self.apple_lots, self.internal_loc_2, 1, self.lot1)
