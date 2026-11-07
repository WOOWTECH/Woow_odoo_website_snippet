from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

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
