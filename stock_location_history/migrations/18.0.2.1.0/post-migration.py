# Part of OCA. See LICENSE file for full copyright and licensing details.
"""
Post-migration: sync ticket moves for existing lots.

When ticket_move_ids was changed from computed to stored One2many,
existing lots may not have ticket records. Sync from move lines.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Sync ticket moves for lots with incoming move lines."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    MoveLine = env["stock.move.line"].sudo()
    lots = MoveLine.search(
        [
            ("lot_id", "!=", False),
            ("move_id.picking_id.picking_type_id.code", "=", "incoming"),
            ("move_id.picking_id.state", "=", "done"),
        ]
    ).mapped("lot_id")
    if lots:
        _logger.info(
            "stock_location_history: syncing ticket moves for %d lots",
            len(lots),
        )
        lots._sync_ticket_moves()
