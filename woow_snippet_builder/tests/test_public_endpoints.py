import math
from unittest.mock import patch

from odoo.tests import new_test_user, tagged

from odoo.addons.woow_snippet_builder.controllers.main import (
    WoowSnippetController,
)

from .common import WoowSnippetHttpCase


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestPublicSnippetEndpoints(WoowSnippetHttpCase):
    """/woow_snippet/stat, /chart and /data_table run with the visitor's own
    access rights and only accept validated, allow-listed input."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_products = 'product.template' in cls.env \
            and 'is_published' in cls.env['product.template']
        if cls.has_products:
            Product = cls.env['product.template']
            cls.published = Product.create({
                'name': 'WoowSec Published', 'list_price': 42.0,
                'standard_price': 7.0, 'is_published': True,
            })
            cls.hidden = Product.create({
                'name': 'WoowSec Hidden', 'list_price': 13.0,
                'standard_price': 3.0, 'is_published': False,
            })

    # ------------------------------------------------------------------
    # Sensitive models are never readable
    # ------------------------------------------------------------------

    def test_res_users_not_readable(self):
        new_test_user(self.env, login='woowsec_internal',
                      email='woowsec_internal@example.com')
        resp = self._rpc('/woow_snippet/data_table', model_name='res.users',
                         field_names='name,login,email', limit=100)
        self.assertRefused(resp)
        self.assertNotIn('woowsec_internal', str(resp))
        self.assertRefused(self._rpc('/woow_snippet/stat',
                                     model_name='res.users'))
        self.assertRefused(self._rpc('/woow_snippet/chart',
                                     model_name='res.users',
                                     label_field='login', value_field='id'))

    def test_res_partner_not_readable(self):
        self.env['res.partner'].create({
            'name': 'WoowSec Customer', 'email': 'woowsec_customer@example.com',
            'phone': '+886 2 0000 0000',
        })
        resp = self._rpc('/woow_snippet/data_table', model_name='res.partner',
                         field_names='name,email,phone',
                         domain="[('name', '=', 'WoowSec Customer')]")
        self.assertRefused(resp)
        self.assertNotIn('woowsec_customer@example.com', str(resp))
        resp = self._rpc('/woow_snippet/stat', model_name='res.partner',
                         group_by='email')
        self.assertRefused(resp)
        self.assertNotIn('woowsec_customer@example.com', str(resp))
        resp = self._rpc('/woow_snippet/chart', model_name='res.company',
                         label_field='name', value_field='id')
        self.assertRefused(resp)

    def test_hr_employee_not_readable(self):
        if 'hr.employee' not in self.env:
            self.skipTest('hr not installed')
        self.env['hr.employee'].create({
            'name': 'WoowSec Employee',
            'private_email': 'woowsec_private@example.com',
        })
        resp = self._rpc('/woow_snippet/data_table', model_name='hr.employee',
                         field_names='name,private_email')
        self.assertRefused(resp)
        self.assertNotIn('woowsec_private@example.com', str(resp))

    def test_portal_user_cannot_read_partners(self):
        new_test_user(self.env, login='woowsec_portal',
                      groups='base.group_portal')
        self.authenticate('woowsec_portal', 'woowsec_portal')
        resp = self._rpc('/woow_snippet/data_table', model_name='res.partner',
                         field_names='name,email')
        self.assertRefused(resp)

    # ------------------------------------------------------------------
    # Allowed public model: visitor ACL + record rules apply
    # ------------------------------------------------------------------

    def test_published_products_still_work(self):
        if not self.has_products:
            self.skipTest('website_sale not installed')
        domain = "[('name', 'ilike', 'WoowSec ')]"
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='product.template',
            operation='count', domain=domain))
        # only the published product is visible to the public user
        self.assertEqual(stat['value'], 1)
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='product.template',
            operation='sum', field_name='list_price', domain=domain,
            sub_type='progress', target_value=84))
        self.assertEqual(stat['value'], 42.0)
        self.assertEqual(stat['percent'], 50.0)
        table = self.assertResult(self._rpc(
            '/woow_snippet/data_table', model_name='product.template',
            field_names='name,list_price,categ_id', domain=domain,
            sort_field='name', sort_order='desc', search_term='Woow'))
        self.assertEqual(table['total'], 1)
        self.assertEqual([r['name'] for r in table['rows']],
                         ['WoowSec Published'])
        self.assertEqual(table['rows'][0]['list_price'], 42.0)
        chart = self.assertResult(self._rpc(
            '/woow_snippet/chart', model_name='product.template',
            label_field='name', value_field='list_price', domain=domain,
            chart_type='pie'))
        self.assertEqual(chart['labels'], ['WoowSec Published'])
        self.assertEqual(chart['datasets'][0]['data'], [42.0])
        self.assertEqual(chart['chart_type'], 'pie')

    def test_group_restricted_fields_rejected(self):
        if not self.has_products:
            self.skipTest('website_sale not installed')
        # standard_price (cost) is restricted to base.group_user
        self.assertTrue(
            self.env['product.template']._fields['standard_price'].groups)
        calls = [
            ('/woow_snippet/data_table',
             dict(field_names='name,standard_price')),
            ('/woow_snippet/data_table',
             dict(field_names='name',
                  domain="[('standard_price', '>', 0)]")),
            ('/woow_snippet/stat',
             dict(operation='max', field_name='standard_price')),
            ('/woow_snippet/stat', dict(group_by='standard_price')),
            ('/woow_snippet/chart',
             dict(label_field='name', value_field='standard_price')),
        ]
        for route, params in calls:
            with self.subTest(route=route, params=params):
                resp = self._rpc(route, model_name='product.template',
                                 **params)
                self.assertRefused(resp)
                self.assertNotIn('7.0', str(resp.get('result')))

    def test_dotted_and_expression_domains_rejected(self):
        if not self.has_products:
            self.skipTest('website_sale not installed')
        for domain in (
            "[('create_uid.login', 'like', '%')]",
            "[('company_id.partner_id.email', '!=', False)]",
            "[('id', 'in', [1] * 3)]",
            "[('name', '=like', 'W%')]",
            "[('categ_id', 'ilike', 'All')]",
        ):
            for route, params in (
                ('/woow_snippet/stat', {}),
                ('/woow_snippet/chart',
                 dict(label_field='name', value_field='id')),
                ('/woow_snippet/data_table', dict(field_names='name')),
            ):
                with self.subTest(domain=domain, route=route):
                    self.assertRefused(self._rpc(
                        route, model_name='product.template',
                        domain=domain, **params))

    def test_allow_list_does_not_grant_access(self):
        """Even an allow-listed model is read with the visitor's rights:
        public ACL decides, sudo is never used."""
        self.env['ir.config_parameter'].set_param('woowsec.secret', 'S3CR3T')
        with patch.object(WoowSnippetController, '_get_allowed_models',
                          lambda self: {'website.menu', 'ir.config_parameter'}):
            resp = self._rpc('/woow_snippet/data_table',
                             model_name='ir.config_parameter',
                             field_names='key,value',
                             domain="[('key', '=', 'woowsec.secret')]")
            self.assertRefused(resp)
            self.assertNotIn('S3CR3T', str(resp))
            self.assertRefused(self._rpc('/woow_snippet/stat',
                                         model_name='ir.config_parameter'))
            # a model the public user may read keeps working
            menus = self.assertResult(self._rpc(
                '/woow_snippet/data_table', model_name='website.menu',
                field_names='name,url', limit=5))
            self.assertTrue(menus['total'])

    def test_model_not_allowed(self):
        for model in ('ir.config_parameter', 'res.users.apikeys',
                      'sale.order', 'account.move', 'nope.model', ['x']):
            with self.subTest(model=model):
                self.assertRefused(self._rpc('/woow_snippet/stat',
                                             model_name=model))

    # ------------------------------------------------------------------
    # Robustness: no server errors on garbage, bounded results
    # ------------------------------------------------------------------

    def test_offset_limit_garbage(self):
        if not self.has_products:
            self.skipTest('website_sale not installed')
        table = self.assertResult(self._rpc(
            '/woow_snippet/data_table', model_name='product.template',
            field_names='name', offset='abc', limit='zz'))
        self.assertEqual(table['offset'], 0)
        self.assertEqual(table['limit'], 25)
        table = self.assertResult(self._rpc(
            '/woow_snippet/data_table', model_name='product.template',
            field_names='name', offset=-4, limit=10 ** 6))
        self.assertEqual(table['offset'], 0)
        self.assertEqual(table['limit'], 100)

    def test_nan_numbers(self):
        if not self.has_products:
            self.skipTest('website_sale not installed')
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='product.template',
            sub_type='threshold', target_value='nan',
            threshold_warning='NaN', threshold_danger='inf'))
        self.assertEqual(stat['target'], 100)
        self.assertFalse(math.isnan(stat['percent']))
        chart = self.assertResult(self._rpc(
            '/woow_snippet/chart', model_name='product.template',
            label_field='name', value_field='id', gauge_max='nan'))
        self.assertEqual(chart['gauge_max'], 100)

    def test_group_count_capped(self):
        if not self.has_products:
            self.skipTest('website_sale not installed')
        self.env['product.template'].create([
            {'name': f'WoowCap {i:02d}', 'is_published': True}
            for i in range(60)
        ])
        domain = "[('name', 'like', 'WoowCap')]"
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='product.template',
            group_by='name', domain=domain))
        self.assertEqual(stat['value'], 60)
        self.assertEqual(len(stat['breakdown']), 50)
        chart = self.assertResult(self._rpc(
            '/woow_snippet/chart', model_name='product.template',
            label_field='name', value_field='id', domain=domain))
        self.assertEqual(len(chart['labels']), 50)


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestEditorEndpoints(WoowSnippetHttpCase):
    """/woow_snippet/model_fields and /available_models are editor-only."""

    def test_portal_refused(self):
        new_test_user(self.env, login='woowsec_portal2',
                      groups='base.group_portal')
        self.authenticate('woowsec_portal2', 'woowsec_portal2')
        self.assertRefused(self._rpc('/woow_snippet/available_models'))
        self.assertRefused(self._rpc('/woow_snippet/model_fields',
                                     model_name='website.page'))

    def test_internal_non_editor_refused(self):
        new_test_user(self.env, login='woowsec_employee',
                      groups='base.group_user')
        self.authenticate('woowsec_employee', 'woowsec_employee')
        self.assertRefused(self._rpc('/woow_snippet/available_models'))

    def test_designer_allowed(self):
        new_test_user(self.env, login='woowsec_designer',
                      groups='base.group_user,website.group_website_designer')
        self.authenticate('woowsec_designer', 'woowsec_designer')
        models = self.assertResult(self._rpc('/woow_snippet/available_models'))
        names = {m['model'] for m in models}
        self.assertIn('website.page', names)
        self.assertFalse(names & {'res.users', 'res.partner', 'res.company',
                                  'hr.employee', 'account.move'})
        fields = self.assertResult(self._rpc('/woow_snippet/model_fields',
                                             model_name='website.page'))
        self.assertIn('url', {f['name'] for f in fields})
        if 'product.template' in self.env:
            fields = self.assertResult(self._rpc(
                '/woow_snippet/model_fields', model_name='product.template'))
            names = {f['name'] for f in fields}
            self.assertIn('list_price', names)
            self.assertNotIn('standard_price', names)
        self.assertRefused(self._rpc('/woow_snippet/model_fields',
                                     model_name='res.users'))


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestPublicPages(WoowSnippetHttpCase):

    def test_ha_dashboard_page_renders(self):
        """The shipped page still renders for anonymous visitors (its
        widgets load their data client side through the public routes)."""
        response = self.url_open('/ha-dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn('s_woow_stat', response.text)
        self.assertIn('s_woow_data_table', response.text)
