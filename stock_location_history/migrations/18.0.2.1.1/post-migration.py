# Part of OCA. See LICENSE file for full copyright and licensing details.
"""Recompute macrolot receipt and initial-mix summaries.

Entrada total and the first/last ticket now follow the incoming transfer.
The initial mix now follows the smallest NumMez.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_RECOMPUTE_FIELDS = (
    "quantity_in",
    "quantity_difference",
    "first_ticket",
    "date_first_ticket",
    "last_ticket",
    "date_last_ticket",
    "quantity_first_ticket",
    "quantity_last_ticket",
    "initial_mix",
    "initial_mix_date",
    "kg_consumed_mi",
)


def migrate(cr, version):
    """Refresh stored summaries for lots that already have receipts or mixes."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {"skip_location_lot_snapshot": True})
    cr.execute(
        """
        SELECT DISTINCT sml.lot_id
          FROM stock_move_line sml
          JOIN stock_move sm ON sm.id = sml.move_id
          JOIN stock_picking sp ON sp.id = sm.picking_id
          JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
         WHERE sml.lot_id IS NOT NULL
           AND spt.code = 'incoming'
           AND sp.state = 'done'
        """
    )
    lot_ids = {row[0] for row in cr.fetchall()}
    cr.execute(
        """
        SELECT DISTINCT lot_id
          FROM mrp_batch_lines
         WHERE lot_id IS NOT NULL
        """
    )
    lot_ids.update(row[0] for row in cr.fetchall())
    if not lot_ids:
        return

    _logger.info(
        "stock_location_history: recomputing receipt and mix data for %s lots",
        len(lot_ids),
    )
    Lot = env["stock.lot"].sudo().with_context(skip_location_lot_snapshot=True)
    fields_to_compute = [Lot._fields[name] for name in _RECOMPUTE_FIELDS]
    ordered_ids = sorted(lot_ids)
    for offset in range(0, len(ordered_ids), 100):
        lots = Lot.browse(ordered_ids[offset : offset + 100])
        for field in fields_to_compute:
            env.add_to_compute(field, lots)
        env.flush_all()
        lots.invalidate_recordset()
