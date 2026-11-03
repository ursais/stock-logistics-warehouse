# Part of OCA. See LICENSE file for full copyright and licensing details.
"""Fill purchase_id from the misspelled column before that column is removed.

The ticket form and the original sync already stored the order on
``purchase_id``. ``puchase_id`` is copied only where ``purchase_id`` is empty.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'stock_production_ticket'
           AND column_name IN ('puchase_id', 'purchase_id')
        """
    )
    columns = {row[0] for row in cr.fetchall()}
    if "puchase_id" not in columns or "purchase_id" not in columns:
        return

    cr.execute(
        """
        SELECT ticket.id, other.id
          FROM stock_production_ticket AS ticket
          JOIN stock_production_ticket AS other
            ON other.id <> ticket.id
           AND other.lot_id IS NOT DISTINCT FROM ticket.lot_id
           AND other.move_id IS NOT DISTINCT FROM ticket.move_id
           AND other.purchase_id = ticket.puchase_id
         WHERE ticket.purchase_id IS NULL
           AND ticket.puchase_id IS NOT NULL
        """
    )
    collisions = cr.fetchall()
    if collisions:
        raise RuntimeError(
            "stock_production_ticket rows would share lot, purchase and "
            f"picking after renaming puchase_id: {collisions}"
        )

    cr.execute(
        """
        UPDATE stock_production_ticket
           SET purchase_id = puchase_id
         WHERE purchase_id IS NULL
           AND puchase_id IS NOT NULL
        """
    )
    _logger.info(
        "stock_location_history: copied puchase_id onto purchase_id for %s tickets",
        cr.rowcount,
    )
