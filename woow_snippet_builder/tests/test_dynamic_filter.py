import importlib.util
import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from .common import WoowSnippetHttpCase

CARD = 'woow_snippet_builder.dynamic_filter_template_woow_card'


def _make_filter(env, model, domain, field_names, name='WoowSec filter'):
    ir_filter = env['ir.filters'].create({
        'name': name,
        'model_id': model,
        'domain': domain,
        'sort': '[]',
        'context': '{}',
        'user_id': False,
    })
    return env['website.snippet.filter'].create({
        'name': name,
        'filter_id': ir_filter.id,
        'field_names': field_names,
        'limit': 16,
    })


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestDynamicFilterPublic(WoowSnippetHttpCase):
    """/website/snippet/filters with WoOW templates searches with the
    visitor's rights and refuses unsafe visitor search domains."""

    def _render(self, snippet_filter, search_domain=None):
        resp = self._rpc('/website/snippet/filters',
                         filter_id=snippet_filter.id, template_key=CARD,
                         limit=16, search_domain=search_domain or [])
        return self.assertResult(resp)

    def test_partner_filter_does_not_leak(self):
        """A res.partner filter (like the formerly shipped demo filters)
        only shows what the public user may read: nothing."""
        self.env['res.partner'].create({
            'name': 'WoowSec Published Partner',
            'email': 'woowsec_partner@example.com',
            'is_published': True,
        })
        snippet_filter = _make_filter(
            self.env, 'res.partner', "[('email', 'ilike', 'woowsec_partner')]",
            'name,email,city')
        html = ''.join(self._render(snippet_filter))
        self.assertNotIn('woowsec_partner@example.com', html)
        self.assertNotIn('WoowSec Published Partner', html)

    def test_model_without_public_access_renders_nothing(self):
        self.env['ir.config_parameter'].set_param('woowsec.secret', 'S3CR3T')
        snippet_filter = _make_filter(
            self.env, 'ir.config_parameter', "[('key', '=', 'woowsec.secret')]",
            'key,value')
        self.assertEqual(self._render(snippet_filter), [])

    def test_products_and_search_domain(self):
        if 'product.template' not in self.env \
                or 'is_published' not in self.env['product.template']:
            self.skipTest('website_sale not installed')
        Product = self.env['product.template']
        Product.create({'name': 'WoowDyn Published', 'is_published': True})
        Product.create({'name': 'WoowDyn Hidden', 'is_published': False})
        snippet_filter = _make_filter(
            self.env, 'product.template', "[('name', 'ilike', 'WoowDyn')]",
            'name,list_price')

        html = ''.join(self._render(snippet_filter))
        self.assertIn('WoowDyn Published', html)
        self.assertNotIn('WoowDyn Hidden', html)

        # a legitimate visitor filter on a configured field still works
        html = ''.join(self._render(
            snippet_filter, [['name', '=', 'WoowDyn Published']]))
        self.assertIn('WoowDyn Published', html)

        # malicious / out of scope visitor domains render nothing
        for search_domain in (
            [['create_uid.login', 'like', '%']],
            [['company_id.partner_id.email', '!=', False]],
            [['create_uid', '!=', False]],          # not in field_names
            [['name', '=like', 'Woow%']],           # operator not allowed
            [['standard_price', '>=', 0]],          # not in field_names
            'not a domain',
        ):
            with self.subTest(search_domain=search_domain):
                resp = self._rpc('/website/snippet/filters',
                                 filter_id=snippet_filter.id,
                                 template_key=CARD, limit=16,
                                 search_domain=search_domain)
                self.assertEqual(self.assertResult(resp), [])

    def test_archived_ir_filter_not_served(self):
        snippet_filter = _make_filter(
            self.env, 'website.menu', "[]", 'name')
        self.assertTrue(self._render(snippet_filter))
        snippet_filter.filter_id.active = False
        self.assertEqual(self._render(snippet_filter), [])


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestLegacyFilterRetirement(TransactionCase):
    """The res.partner filters formerly shipped as data are retired on
    upgrade (18.0.2.0.1 post-migrate)."""

    def _view_using(self, snippet_filter):
        return self.env['ir.ui.view'].create({
            'name': 'WoowSec page',
            'type': 'qweb',
            'key': f'woow_snippet_builder.woowsec_page_{snippet_filter.id}',
            'arch': '<t t-name="woowsec"><section class="s_woow_dynamic_content"'
                    f' data-filter-id="{snippet_filter.id}"/></t>',
        })

    def test_retire_unreferenced_and_referenced(self):
        unused = _make_filter(self.env, 'res.partner', "[]", 'name', 'Unused')
        used = _make_filter(self.env, 'res.partner', "[]", 'name', 'Used')
        unused_ir_filter = unused.filter_id
        # A view using an id that merely *starts* with unused.id must not
        # count as a reference to it.
        self.env['ir.ui.view'].create({
            'name': 'WoowSec other', 'type': 'qweb',
            'arch': f'<t t-name="o"><div data-filter-id="{unused.id}9"/></t>',
        })
        self._view_using(used)

        deleted, archived = (unused | used)._woow_retire_legacy_filters()
        self.assertEqual(deleted, ['Unused'])
        self.assertEqual(archived, ['Used'])
        self.assertFalse(unused.exists())
        self.assertFalse(unused_ir_filter.exists())
        self.assertTrue(used.exists())
        self.assertFalse(used.filter_id.active)
        self.assertEqual(used._woow_prepare_values(), [])
        # idempotent
        self.assertEqual(used._woow_retire_legacy_filters(), ([], ['Used']))

    def test_post_migrate(self):
        path = os.path.join(get_module_path('woow_snippet_builder'),
                            'migrations', '18.0.2.0.1', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('woow_snip_mig', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        # Recreate the legacy records with their historical xmlids.
        records = {}
        for xmlid in migration.LEGACY_FILTER_XMLIDS:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if not record:
                record = _make_filter(self.env, 'res.partner', "[]",
                                      'name,email,city,image_128', xmlid)
                module, name = xmlid.split('.')
                self.env['ir.model.data'].create({
                    'module': module, 'name': name, 'noupdate': True,
                    'model': record._name, 'res_id': record.id,
                })
            records[xmlid] = record
        self.env.cr.execute(
            "UPDATE ir_module_module SET demo = false "
            "WHERE name = 'woow_snippet_builder'")
        self.env.flush_all()

        migration.migrate(self.env.cr, '18.0.2.0.0')
        self.env.invalidate_all()
        for xmlid, record in records.items():
            self.assertFalse(self.env.ref(xmlid, raise_if_not_found=False))
            self.assertFalse(record.exists())
        # running it again is harmless
        migration.migrate(self.env.cr, '18.0.2.0.0')
