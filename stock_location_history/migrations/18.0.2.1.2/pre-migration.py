# Part of OCA. See LICENSE file for full copyright and licensing details.
"""Copy the misspelled purchase column before the field is removed.

``puchase_id`` is the value the unique key and the ticket sync used.
``purchase_id`` is the field that remains.
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
         WHERE ticket.puchase_id IS NOT NULL
           AND ticket.purchase_id IS DISTINCT FROM ticket.puchase_id
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
         WHERE puchase_id IS NOT NULL
           AND purchase_id IS DISTINCT FROM puchase_id
        """
    )
    _logger.info(
        "stock_location_history: copied puchase_id onto purchase_id for %s tickets",
        cr.rowcount,
    )
