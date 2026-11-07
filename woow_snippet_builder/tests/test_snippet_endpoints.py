import math
import unittest
from unittest.mock import patch

from odoo.tests import new_test_user, tagged

from odoo.addons.woow_snippet_builder.controllers.main import (
    WoowSnippetController,
)

from .common import WoowSnippetHttpCase

DATA_ROUTES = ('/woow_snippet/stat', '/woow_snippet/chart',
               '/woow_snippet/data_table')


def _has_website_sale(env):
    """Published product templates (``is_published`` + the public/portal
    record rules) come from website_sale; ``website`` alone has no
    product model at all."""
    return 'product.template' in env and 'is_published' in env['product.template']


class WoowSnippetUsersCase(WoowSnippetHttpCase):
    """Users and website pages shared by the endpoint tests.

    ``website.page`` (shipped by ``website`` itself, allow-listed) is used
    for everything that does not need products, so these tests run whether
    or not website_sale is installed: designers may read pages (ACL
    ``access_website_page_designer``), portal and plain internal users may
    not.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal = new_test_user(
            cls.env, login='woowsec_portal', groups='base.group_portal',
            email='woowsec_portal@example.com')
        cls.internal = new_test_user(
            cls.env, login='woowsec_internal', groups='base.group_user',
            email='woowsec_internal@example.com')
        cls.designer = new_test_user(
            cls.env, login='woowsec_designer',
            groups='base.group_user,website.group_website_designer')
        Page = cls.env['website.page']
        cls.page_published = Page.create({
            'name': 'WoowSec Page Published', 'type': 'qweb',
            'arch': '<div>published</div>',
            'key': 'woow_snippet_builder.woowsec_page_published',
            'url': '/woowsec-page-published', 'is_published': True,
        })
        cls.page_hidden = Page.create({
            'name': 'WoowSec Page Hidden', 'type': 'qweb',
            'arch': '<div>hidden</div>',
            'key': 'woow_snippet_builder.woowsec_page_hidden',
            'url': '/woowsec-page-hidden', 'is_published': False,
        })
        cls.page_domain = "[('url', 'like', '/woowsec-page-')]"

    def _login_as(self, user):
        self.authenticate(user.login, user.login)


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestAnonymousRefused(WoowSnippetUsersCase):
    """The data routes are auth='user' (as on well-101): anonymous visitors
    get the session-expired JSON error and never any data."""

    def _calls(self, model, label='url', fields='url'):
        return [
            ('/woow_snippet/stat', dict(model_name=model)),
            ('/woow_snippet/stat', dict(model_name=model, group_by=label)),
            ('/woow_snippet/chart', dict(model_name=model, label_field=label,
                                         value_field='id')),
            ('/woow_snippet/data_table', dict(model_name=model,
                                              field_names=fields)),
        ]

    def test_anonymous_refused(self):
        calls = self._calls('website.page') \
            + self._calls('res.partner', 'email', 'name,email') \
            + self._calls('res.users', 'login', 'login')
        if _has_website_sale(self.env):
            self.env['product.template'].create({
                'name': 'WoowSec Anonymous Product', 'is_published': True})
            calls += self._calls('product.template', 'name', 'name')
        for route, params in calls:
            with self.subTest(route=route, params=params):
                resp = self._rpc(route, **params)
                self.assertLoginRequired(resp)
                self.assertNotIn('woowsec', str(resp).lower())

    def test_anonymous_refused_even_for_public_readable_model(self):
        """website.menu is readable by the public user: the route itself
        still refuses anonymous callers."""
        with patch.object(WoowSnippetController, '_get_allowed_models',
                          lambda self: {'website.menu'}):
            for route, params in (
                ('/woow_snippet/stat', {}),
                ('/woow_snippet/chart', dict(label_field='name',
                                             value_field='id')),
                ('/woow_snippet/data_table', dict(field_names='name,url')),
            ):
                with self.subTest(route=route):
                    self.assertLoginRequired(self._rpc(
                        route, model_name='website.menu', **params))


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestLoggedInAccess(WoowSnippetUsersCase):
    """Logged-in users only get allow-listed models, read with their own
    access rights (ACL + record rules + field groups, never sudo)."""

    # ------------------------------------------------------------------
    # Sensitive models are never readable, whoever is logged in
    # ------------------------------------------------------------------

    def _sensitive_calls(self):
        calls = [
            ('/woow_snippet/data_table',
             dict(model_name='res.users', field_names='name,login,email',
                  limit=100)),
            ('/woow_snippet/stat', dict(model_name='res.users')),
            ('/woow_snippet/chart', dict(model_name='res.users',
                                         label_field='login',
                                         value_field='id')),
            ('/woow_snippet/data_table',
             dict(model_name='res.partner', field_names='name,email,phone')),
            ('/woow_snippet/stat', dict(model_name='res.partner',
                                        group_by='email')),
            ('/woow_snippet/chart', dict(model_name='res.company',
                                         label_field='name',
                                         value_field='id')),
        ]
        if 'hr.employee' in self.env:
            calls.append(('/woow_snippet/data_table',
                          dict(model_name='hr.employee',
                               field_names='name,private_email')))
        return calls

    def test_sensitive_models_refused_for_all_users(self):
        self.env['res.partner'].create({
            'name': 'WoowSec Customer', 'email': 'woowsec_customer@example.com',
            'phone': '+886 2 0000 0000',
        })
        # internal users and designers can read res.partner / res.users
        # through the ORM: the allow-list still keeps them out.
        self.assertTrue(
            self.env['res.partner'].with_user(self.internal).has_access('read'))
        for user in (self.portal, self.internal, self.designer):
            self._login_as(user)
            for route, params in self._sensitive_calls():
                with self.subTest(user=user.login, route=route, params=params):
                    resp = self._rpc(route, **params)
                    self.assertRefused(resp)
                    self.assertNotIn('woowsec_customer@example.com', str(resp))
                    self.assertNotIn('woowsec_internal@example.com', str(resp))

    def test_model_not_allowed(self):
        self._login_as(self.designer)
        for model in ('ir.config_parameter', 'res.users.apikeys',
                      'sale.order', 'account.move', 'nope.model', ['x']):
            with self.subTest(model=model):
                self.assertRefused(self._rpc('/woow_snippet/stat',
                                             model_name=model))

    # ------------------------------------------------------------------
    # Allow-listed models: the user's own ACL decides
    # ------------------------------------------------------------------

    def test_portal_and_internal_refused_by_acl(self):
        """website.page is allow-listed but only designers have an ACL."""
        for user in (self.portal, self.internal):
            self._login_as(user)
            for route, params in (
                ('/woow_snippet/stat', {}),
                ('/woow_snippet/chart', dict(label_field='url',
                                             value_field='id')),
                ('/woow_snippet/data_table', dict(field_names='url')),
            ):
                with self.subTest(user=user.login, route=route):
                    resp = self._rpc(route, model_name='website.page',
                                     domain=self.page_domain, **params)
                    self.assertRefused(resp)
                    self.assertNotIn('woowsec-page', str(resp))

    def test_designer_reads_allowed_model(self):
        self._login_as(self.designer)
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='website.page',
            operation='count', domain=self.page_domain, sub_type='progress',
            target_value=4))
        self.assertEqual(stat['value'], 2)
        self.assertEqual(stat['percent'], 50.0)
        table = self.assertResult(self._rpc(
            '/woow_snippet/data_table', model_name='website.page',
            field_names='url,is_published', domain=self.page_domain,
            sort_field='url', sort_order='desc', search_term='woowsec'))
        self.assertEqual(table['total'], 2)
        self.assertEqual([r['url'] for r in table['rows']],
                         ['/woowsec-page-published', '/woowsec-page-hidden'])
        chart = self.assertResult(self._rpc(
            '/woow_snippet/chart', model_name='website.page',
            label_field='is_published', value_field='id',
            domain=self.page_domain, chart_type='pie'))
        self.assertEqual(sorted(chart['datasets'][0]['data']), [1, 1])
        self.assertEqual(chart['chart_type'], 'pie')

    def test_allow_list_does_not_grant_access(self):
        """Even an allow-listed model is read with the user's rights:
        their ACL decides, sudo is never used."""
        self.env['ir.config_parameter'].set_param('woowsec.secret', 'S3CR3T')
        with patch.object(WoowSnippetController, '_get_allowed_models',
                          lambda self: {'website.menu', 'ir.config_parameter'}):
            for user in (self.portal, self.internal, self.designer):
                self._login_as(user)
                with self.subTest(user=user.login):
                    resp = self._rpc('/woow_snippet/data_table',
                                     model_name='ir.config_parameter',
                                     field_names='key,value',
                                     domain="[('key', '=', 'woowsec.secret')]")
                    self.assertRefused(resp)
                    self.assertNotIn('S3CR3T', str(resp))
                    self.assertRefused(self._rpc(
                        '/woow_snippet/stat', model_name='ir.config_parameter'))
                    # a model the user may read keeps working
                    menus = self.assertResult(self._rpc(
                        '/woow_snippet/data_table', model_name='website.menu',
                        field_names='name,url', limit=5))
                    self.assertTrue(menus['total'])

    # ------------------------------------------------------------------
    # Input validation (designer on website.page: no website_sale needed)
    # ------------------------------------------------------------------

    def test_dotted_and_expression_domains_rejected(self):
        self._login_as(self.designer)
        for domain in (
            "[('create_uid.login', 'like', '%')]",
            "[('website_id.company_id.email', '!=', False)]",
            "[('id', 'in', [1] * 3)]",
            "[('url', '=like', '/w%')]",
            "[('website_id', 'ilike', 'My')]",
            "[('key', '=', 'x')]",       # inherited, not stored on the page
            "__import__('os').system('true')",
        ):
            for route, params in (
                ('/woow_snippet/stat', {}),
                ('/woow_snippet/chart',
                 dict(label_field='url', value_field='id')),
                ('/woow_snippet/data_table', dict(field_names='url')),
            ):
                with self.subTest(domain=domain, route=route):
                    self.assertRefused(self._rpc(
                        route, model_name='website.page',
                        domain=domain, **params))

    def test_offset_limit_garbage(self):
        self._login_as(self.designer)
        table = self.assertResult(self._rpc(
            '/woow_snippet/data_table', model_name='website.page',
            field_names='url', offset='abc', limit='zz'))
        self.assertEqual(table['offset'], 0)
        self.assertEqual(table['limit'], 25)
        table = self.assertResult(self._rpc(
            '/woow_snippet/data_table', model_name='website.page',
            field_names='url', offset=-4, limit=10 ** 6))
        self.assertEqual(table['offset'], 0)
        self.assertEqual(table['limit'], 100)

    def test_nan_numbers(self):
        self._login_as(self.designer)
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='website.page',
            sub_type='threshold', target_value='nan',
            threshold_warning='NaN', threshold_danger='inf'))
        self.assertEqual(stat['target'], 100)
        self.assertFalse(math.isnan(stat['percent']))
        chart = self.assertResult(self._rpc(
            '/woow_snippet/chart', model_name='website.page',
            label_field='url', value_field='id', gauge_max='nan'))
        self.assertEqual(chart['gauge_max'], 100)

    def test_group_count_capped(self):
        self.env['website.page'].create([{
            'name': f'WoowCap {i:02d}', 'type': 'qweb', 'arch': '<div/>',
            'key': f'woow_snippet_builder.woowcap_{i:02d}',
            'url': f'/woowcap-{i:02d}',
        } for i in range(60)])
        self._login_as(self.designer)
        domain = "[('url', 'like', '/woowcap-')]"
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='website.page',
            group_by='url', domain=domain))
        self.assertEqual(stat['value'], 60)
        self.assertEqual(len(stat['breakdown']), 50)
        chart = self.assertResult(self._rpc(
            '/woow_snippet/chart', model_name='website.page',
            label_field='url', value_field='id', domain=domain))
        self.assertEqual(len(chart['labels']), 50)


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestProductEndpoints(WoowSnippetUsersCase):
    """Product checks: these need website_sale (``website`` does not depend
    on ``product``; ``is_published`` on product.template and the
    public/portal "published products only" record rule come from
    website_sale)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _has_website_sale(cls.env):
            raise unittest.SkipTest('website_sale not installed')
        Product = cls.env['product.template']
        cls.published = Product.create({
            'name': 'WoowSec Published', 'list_price': 42.0,
            'standard_price': 7.0, 'is_published': True,
        })
        cls.hidden = Product.create({
            'name': 'WoowSec Hidden', 'list_price': 13.0,
            'standard_price': 3.0, 'is_published': False,
        })
        cls.domain = "[('name', 'ilike', 'WoowSec ')]"

    def test_portal_sees_published_products_only(self):
        self._login_as(self.portal)
        domain = self.domain
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='product.template',
            operation='count', domain=domain))
        # the record rules only show the published product to portal users
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

    def test_internal_user_reads_within_acl(self):
        """Internal users have no "published only" rule on products."""
        self._login_as(self.internal)
        stat = self.assertResult(self._rpc(
            '/woow_snippet/stat', model_name='product.template',
            operation='count', domain=self.domain))
        self.assertEqual(stat['value'], 2)
        table = self.assertResult(self._rpc(
            '/woow_snippet/data_table', model_name='product.template',
            field_names='name', domain=self.domain, sort_field='name'))
        self.assertEqual([r['name'] for r in table['rows']],
                         ['WoowSec Hidden', 'WoowSec Published'])

    def test_group_restricted_fields_rejected(self):
        # standard_price (cost) is restricted to base.group_user: refused
        # for portal users, and for internal users too (the endpoints never
        # expose group-restricted fields).
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
        for user in (self.portal, self.internal):
            self._login_as(user)
            for route, params in calls:
                with self.subTest(user=user.login, route=route, params=params):
                    resp = self._rpc(route, model_name='product.template',
                                     **params)
                    self.assertRefused(resp)
                    self.assertNotIn('7.0', str(resp.get('result')))

    def test_dotted_domains_rejected_on_products(self):
        self._login_as(self.portal)
        for domain in (
            "[('company_id.partner_id.email', '!=', False)]",
            "[('categ_id', 'ilike', 'All')]",
        ):
            with self.subTest(domain=domain):
                self.assertRefused(self._rpc(
                    '/woow_snippet/data_table', model_name='product.template',
                    field_names='name', domain=domain))


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestEditorEndpoints(WoowSnippetHttpCase):
    """/woow_snippet/model_fields and /available_models are editor-only."""

    def test_anonymous_refused(self):
        self.assertLoginRequired(self._rpc('/woow_snippet/available_models'))
        self.assertLoginRequired(self._rpc('/woow_snippet/model_fields',
                                           model_name='website.page'))

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
        new_test_user(self.env, login='woowsec_designer2',
                      groups='base.group_user,website.group_website_designer')
        self.authenticate('woowsec_designer2', 'woowsec_designer2')
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
        """The shipped page still renders for anonymous visitors: the
        widgets show a sign-in notice client side instead of calling the
        auth='user' data routes (static/src/snippets/woow_snippet_access.js,
        checked by tools/js_checks/login_required_check.mjs)."""
        response = self.url_open('/ha-dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn('s_woow_stat', response.text)
        self.assertIn('s_woow_data_table', response.text)
        # the frontend session tells the widgets the visitor is anonymous
        self.assertRegex(response.text,
                         r'is_website_user(&#34;|&quot;|")?\s*:\s*true')
