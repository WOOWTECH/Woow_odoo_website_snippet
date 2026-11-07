from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from .common import WoowSnippetHttpCase

MODULE = 'woow_snippet_builder'


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestSnippetFilterAccessRights(TransactionCase):
    """security/ir.model.access.csv (loaded since 18.0.2.0.2): website
    designers manage Dynamic Content filters (website.snippet.filter); the
    public read row of 18.0.2.0.0 must not exist (core renders filters with
    sudo, the public user needs no ACL)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = new_test_user(
            cls.env, login='woowacl_designer',
            groups='base.group_user,website.group_website_designer')
        cls.portal = new_test_user(cls.env, login='woowacl_portal',
                                   groups='base.group_portal')
        cls.public = cls.env.ref('base.public_user')
        cls.ir_filter = cls.env['ir.filters'].create({
            'name': 'WoowACL filter', 'model_id': 'website.menu',
            'domain': '[]', 'sort': '[]', 'context': '{}', 'user_id': False,
        })

    def test_acl_rows(self):
        editor = self.env.ref(
            f'{MODULE}.access_website_snippet_filter_woow_editor',
            raise_if_not_found=False)
        self.assertTrue(editor)
        self.assertEqual(editor.group_id,
                         self.env.ref('website.group_website_designer'))
        self.assertEqual(editor.model_id.model, 'website.snippet.filter')
        self.assertTrue(editor.perm_read and editor.perm_write
                        and editor.perm_create and editor.perm_unlink)
        self.assertFalse(self.env.ref(
            f'{MODULE}.access_website_snippet_filter_woow_public',
            raise_if_not_found=False))
        public_rows = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'website.snippet.filter'),
            ('group_id', 'in', [self.env.ref('base.group_public').id,
                                self.env.ref('base.group_portal').id]),
        ])
        self.assertFalse(public_rows)

    def test_designer_manages_snippet_filters(self):
        self.assertFalse(self.designer.has_group('base.group_system'))
        Filter = self.env['website.snippet.filter'].with_user(self.designer)
        snippet_filter = Filter.create({
            'name': 'WoowACL designer filter',
            'filter_id': self.ir_filter.id,
            'field_names': 'name,url',
            'limit': 6,
        })
        self.assertEqual(snippet_filter.read(['name'])[0]['name'],
                         'WoowACL designer filter')
        snippet_filter.write({'name': 'WoowACL renamed', 'limit': 8})
        self.assertEqual(snippet_filter.name, 'WoowACL renamed')
        self.assertIn(snippet_filter, Filter.search(
            [('name', '=', 'WoowACL renamed')]))
        snippet_filter.unlink()
        self.assertFalse(snippet_filter.exists())

    def test_public_and_portal_cannot_read_filters(self):
        snippet_filter = self.env['website.snippet.filter'].create({
            'name': 'WoowACL secret filter', 'filter_id': self.ir_filter.id,
            'field_names': 'name', 'limit': 6,
        })
        for user in (self.public, self.portal):
            with self.subTest(user=user.login):
                Filter = self.env['website.snippet.filter'].with_user(user)
                self.assertFalse(Filter.has_access('read'))
                with self.assertRaises(AccessError):
                    Filter.search([('id', '=', snippet_filter.id)])
                with self.assertRaises(AccessError):
                    snippet_filter.with_user(user).read(['name'])
                with self.assertRaises(AccessError):
                    Filter.create({'name': 'nope',
                                   'filter_id': self.ir_filter.id})

    def test_plain_internal_user_cannot_manage_filters(self):
        employee = new_test_user(self.env, login='woowacl_employee',
                                 groups='base.group_user')
        Filter = self.env['website.snippet.filter'].with_user(employee)
        self.assertFalse(Filter.has_access('create'))
        self.assertFalse(Filter.has_access('write'))


def _code_action(env, name, param_key):
    """A Python code server action that returns a system parameter (only
    readable by administrators) as snippet "records".  The data route is
    readonly=True, so reading as superuser is what an attacker gets."""
    return env['ir.actions.server'].create({
        'name': name,
        'model_id': env.ref('base.model_ir_config_parameter').id,
        'state': 'code',
        'code': "action = [{'secret': env['ir.config_parameter'].sudo()"
                ".get_param(%r)}]" % param_key,
    })


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestSnippetFilterActionServerGuard(TransactionCase):
    """Designers manage website.snippet.filter (csv row) but may not bind a
    filter to a new ir.actions.server: core runs it with sudo() for any
    anonymous visitor of /website/snippet/filters."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.designer = new_test_user(
            cls.env, login='woowact_designer',
            groups='base.group_user,website.group_website_designer')
        cls.admin = new_test_user(
            cls.env, login='woowact_admin',
            groups='base.group_user,base.group_system')
        cls.action = _code_action(cls.env, 'WoowAct evil', 'woowact.evil')
        cls.approved = _code_action(cls.env, 'WoowAct approved',
                                    'woowact.approved')
        cls.ir_filter = cls.env['ir.filters'].create({
            'name': 'WoowAct filter', 'model_id': 'website.menu',
            'domain': '[]', 'sort': '[]', 'context': '{}', 'user_id': False,
        })

    def test_designer_cannot_create_with_action_server(self):
        self.assertFalse(self.designer.has_group('base.group_system'))
        Filter = self.env['website.snippet.filter'].with_user(self.designer)
        with self.assertRaises(AccessError):
            Filter.create({'name': 'WoowAct bad', 'field_names': 'name',
                           'limit': 4, 'action_server_id': self.action.id})
        self.assertFalse(self.env['website.snippet.filter'].search(
            [('action_server_id', '=', self.action.id)]))

    def test_designer_cannot_write_action_server(self):
        snippet_filter = self.env['website.snippet.filter'].with_user(
            self.designer).create({
                'name': 'WoowAct designer', 'filter_id': self.ir_filter.id,
                'field_names': 'name', 'limit': 4,
            })
        with self.assertRaises(AccessError):
            snippet_filter.write({'filter_id': False,
                                  'action_server_id': self.action.id})
        self.assertFalse(snippet_filter.action_server_id)
        self.assertEqual(snippet_filter.filter_id, self.ir_filter)

    def test_system_user_can_bind_action_server(self):
        Filter = self.env['website.snippet.filter'].with_user(self.admin)
        snippet_filter = Filter.create({
            'name': 'WoowAct admin', 'field_names': 'name', 'limit': 4,
            'action_server_id': self.action.id,
        })
        self.assertEqual(snippet_filter.action_server_id, self.action)
        snippet_filter.write({'action_server_id': self.approved.id})
        self.assertEqual(snippet_filter.action_server_id, self.approved)

    def test_designer_may_reuse_approved_actions_only(self):
        """Server actions already bound by an administrator (or shipped by
        core / website_sale) stay usable: no new exposure."""
        bound = self.env['website.snippet.filter'].with_user(self.admin).create({
            'name': 'WoowAct bound', 'field_names': 'name', 'limit': 4,
            'action_server_id': self.approved.id,
        })
        bound_as_designer = bound.with_user(self.designer)
        bound_as_designer.write({'name': 'WoowAct bound renamed', 'limit': 6})
        bound_as_designer.write({'action_server_id': self.approved.id})
        self.assertEqual(bound.name, 'WoowAct bound renamed')
        copy = bound_as_designer.copy()
        self.assertEqual(copy.action_server_id, self.approved)
        other = self.env['website.snippet.filter'].with_user(
            self.designer).create({
                'name': 'WoowAct reuse', 'field_names': 'name', 'limit': 4,
                'action_server_id': self.approved.id,
            })
        self.assertEqual(other.action_server_id, self.approved)
        with self.assertRaises(AccessError):
            other.write({'action_server_id': self.action.id})
        self.assertEqual(other.action_server_id, self.approved)


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestSnippetFilterActionServerAnonymous(WoowSnippetHttpCase):
    """Regression for the designer -> anonymous superuser escalation via
    /website/snippet/filters (auth='public', filter loaded with sudo)."""

    TEMPLATE = 'woow_snippet_builder.dynamic_filter_template_ir_config_parameter_probe'

    def setUp(self):
        super().setUp()
        self.designer = new_test_user(
            self.env, login='woowanon_designer',
            groups='base.group_user,website.group_website_designer')
        self.env['ir.ui.view'].create({
            'name': 'WoowAct probe', 'type': 'qweb', 'key': self.TEMPLATE,
            'arch': '<t t-name="%s"><div class="woowact-probe">'
                    '<t t-foreach="records" t-as="r">'
                    '<span t-out="r.get(\'secret\')"/></t></div></t>'
                    % self.TEMPLATE,
        })
        self.env['ir.config_parameter'].set_param('woowanon.secret',
                                                  'W00W-S3CR3T')

    def _render_anonymously(self, snippet_filter):
        return ''.join(self.assertResult(self._rpc(
            '/website/snippet/filters', filter_id=snippet_filter.id,
            template_key=self.TEMPLATE, limit=1, search_domain=[])))

    def test_designer_binding_attempt_does_not_run_action(self):
        action = _code_action(self.env, 'WoowAnon evil', 'woowanon.secret')
        ir_filter = self.env['ir.filters'].create({
            'name': 'WoowAnon filter', 'model_id': 'website.menu',
            'domain': '[]', 'sort': '[]', 'context': '{}', 'user_id': False,
        })
        Filter = self.env['website.snippet.filter'].with_user(self.designer)
        snippet_filter = Filter.create({
            'name': 'WoowAnon designer', 'filter_id': ir_filter.id,
            'field_names': 'name', 'limit': 4,
        })
        with self.assertRaises(AccessError):
            snippet_filter.write({'filter_id': False,
                                  'action_server_id': action.id})
        with self.assertRaises(AccessError):
            Filter.create({'name': 'WoowAnon direct', 'field_names': 'name',
                           'limit': 4, 'action_server_id': action.id})
        self.assertFalse(self.env['website.snippet.filter'].search(
            [('action_server_id', '=', action.id)]))
        self.assertNotIn('W00W-S3CR3T', self._render_anonymously(snippet_filter))

    def test_probe_detects_execution(self):
        """Positive control: the same anonymous request does run a server
        action an administrator bound (core behaviour), so the regression
        test above would catch the escalation."""
        action = _code_action(self.env, 'WoowAnon admin', 'woowanon.secret')
        snippet_filter = self.env['website.snippet.filter'].create({
            'name': 'WoowAnon admin filter', 'field_names': 'name',
            'limit': 4, 'action_server_id': action.id,
        })
        self.assertIn('W00W-S3CR3T', self._render_anonymously(snippet_filter))
