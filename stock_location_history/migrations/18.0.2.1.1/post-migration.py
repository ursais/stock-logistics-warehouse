# Part of OCA. See LICENSE file for full copyright and licensing details.
"""Drop the misspelled purchase column once the module no longer defines it."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'stock_production_ticket'
           AND column_name = 'puchase_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute("ALTER TABLE stock_production_ticket DROP COLUMN puchase_id CASCADE")
    _logger.info("stock_location_history: dropped column puchase_id")
