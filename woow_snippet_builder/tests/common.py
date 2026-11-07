import json

from odoo.tests import HttpCase


class WoowSnippetHttpCase(HttpCase):
    """JSON-RPC helpers shared by the WoOW snippet HTTP tests."""

    def _rpc(self, route, **params):
        response = self.url_open(
            route,
            data=json.dumps({
                'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                'params': params,
            }),
            headers={'Content-Type': 'application/json'},
        )
        return response.json()

    def assertRefused(self, response, msg=None):
        self.assertIn('error', response, msg or response)
        self.assertNotIn('result', response, msg or response)

    def assertResult(self, response):
        self.assertNotIn('error', response, response.get('error'))
        return response['result']

    def assertLoginRequired(self, response, msg=None):
        """The auth='user' data routes answer anonymous calls with the
        regular JSON-RPC session-expired error (code 100), no data."""
        self.assertRefused(response, msg)
        error = response['error']
        self.assertEqual(error.get('code'), 100, msg or error)
        self.assertEqual(error.get('data', {}).get('name'),
                         'odoo.http.SessionExpiredException', msg or error)
