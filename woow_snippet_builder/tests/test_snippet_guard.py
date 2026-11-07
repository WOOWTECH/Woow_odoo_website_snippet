from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.woow_snippet_builder.tools.snippet_guard import (
    parse_domain, to_float, to_int,
)


@tagged('post_install', '-at_install', 'woow_snippet_builder')
class TestSnippetGuard(TransactionCase):
    """Unit tests of the visitor input validation helpers."""

    def setUp(self):
        super().setUp()
        self.Model = self.env['res.country']

    def test_plain_domain_accepted(self):
        self.assertEqual(parse_domain('[]', self.Model), [])
        self.assertEqual(parse_domain('', self.Model), [])
        self.assertEqual(
            parse_domain("[('code', '=', 'TW')]", self.Model),
            [('code', '=', 'TW')],
        )
        self.assertEqual(
            parse_domain("['|', ('code', 'in', ['TW', 'JP']), "
                         "('name', 'ilike', 'land')]", self.Model),
            ['|', ('code', 'in', ['TW', 'JP']), ('name', 'ilike', 'land')],
        )
        # implicit '&' is normalised; JSON style lists accepted
        self.assertEqual(
            parse_domain([['code', '=', 'TW'], ['name', '!=', False]],
                         self.Model),
            ['&', ('code', '=', 'TW'), ('name', '!=', False)],
        )

    def test_rejected_domains(self):
        bad = [
            # expressions: safe_eval used to accept them
            "[('id', 'in', [1] * 3)]",
            "[('id', '=', __import__('os'))]",
            "[(x, '=', 1) for x in 'ab']",
            # dotted paths
            "[('currency_id.name', '=', 'EUR')]",
            # operators outside the whitelist
            "[('code', '=like', 'T%')]",
            "[('id', 'child_of', 1)]",
            "[('code', '=', 'TW'), 'x']",
            # unknown / private / non stored fields
            "[('nope', '=', 1)]",
            "[('_unknown', '=', 1)]",
            "[('image_url', '=', 'x')]",
            # leaves that are not 3-tuples / not a list
            "[('code', '=')]",
            "('code', '=', 'TW')",
            "{'a': 1}",
            # arity
            "['|', ('code', '=', 'TW')]",
            # relational fields compare ids only
            "[('currency_id', 'ilike', 'eur')]",
            "[('currency_id', '=', 'EUR')]",
            # like needs text values
            "[('code', 'like', 1)]",
            # oversized
            "[" + ",".join(["('code', '=', 'TW')"] * 100) + "]",
            "[('code', 'in', [%s])]" % ",".join(["'x'"] * 600),
            "x" * 5000,
        ]
        for domain in bad:
            with self.subTest(domain=domain[:60]), self.assertRaises(UserError):
                parse_domain(domain, self.Model)

    def test_allowed_fields_restriction(self):
        self.assertEqual(
            parse_domain([['code', '=', 'TW']], self.Model,
                         allowed_fields={'code'}),
            [('code', '=', 'TW')],
        )
        with self.assertRaises(UserError):
            parse_domain([['name', '=', 'Taiwan']], self.Model,
                         allowed_fields={'code'})

    def test_group_restricted_field_rejected(self):
        found = None
        for model_name in sorted(self.env.registry):
            Model = self.env[model_name]
            for fname, field in Model._fields.items():
                if field.groups and field.store and field.type in (
                        'char', 'integer', 'float', 'boolean', 'selection'):
                    found = (Model, fname)
                    break
            if found:
                break
        self.assertTrue(found)
        Model, fname = found
        with self.assertRaises(UserError):
            parse_domain([[fname, '!=', False]], Model)

    def test_numbers(self):
        self.assertEqual(to_int('abc', 25, 1, 100), 25)
        self.assertEqual(to_int('7', 25, 1, 100), 7)
        self.assertEqual(to_int(10 ** 9, 25, 1, 100), 100)
        self.assertEqual(to_int(-5, 0, 0), 0)
        self.assertEqual(to_int(None, 3), 3)
        self.assertEqual(to_float('nan', 100), 100)
        self.assertEqual(to_float('NaN', 100), 100)
        self.assertEqual(to_float('inf', 100), 100)
        self.assertEqual(to_float('1e999', 100), 100)
        self.assertEqual(to_float('2.5', 100), 2.5)
        self.assertEqual(to_float(None, 0), 0)
