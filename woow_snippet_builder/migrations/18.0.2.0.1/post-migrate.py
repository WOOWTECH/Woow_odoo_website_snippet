"""Retire the res.partner Dynamic Content filters shipped as data.

Up to 18.0.2.0.0 ``woow_snippet_filter_partners`` / ``_companies`` were
loaded as regular (noupdate) data on every database, which gave every
website a publicly callable contact filter.  They are demo data now; on
databases without demo data this migration removes them when no page uses
them, otherwise it archives their ``ir.filters`` so the website stops
serving them (an administrator can review and re-activate it).

Idempotent: once removed the xmlids no longer resolve; archived filters
stay archived.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

LEGACY_FILTER_XMLIDS = (
    'woow_snippet_builder.woow_snippet_filter_partners',
    'woow_snippet_builder.woow_snippet_filter_companies',
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "SELECT demo FROM ir_module_module WHERE name = 'woow_snippet_builder'"
    )
    row = cr.fetchone()
    if row and row[0]:
        _logger.info('woow_snippet_builder: demo database, keeping the demo '
                     'contact filters')
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    filters = env['website.snippet.filter']
    for xmlid in LEGACY_FILTER_XMLIDS:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record and record._name == 'website.snippet.filter':
            filters |= record
    if not filters:
        return
    deleted, archived = filters._woow_retire_legacy_filters()
    if deleted:
        _logger.info('woow_snippet_builder: removed legacy contact snippet '
                     'filters %s', deleted)
    if archived:
        _logger.warning('woow_snippet_builder: legacy contact snippet filters '
                        '%s are still used on website pages; their ir.filters '
                        'were archived so they are no longer served publicly',
                        archived)
