// Check that the Stat Card / Chart / Data Table widgets fail gracefully for
// anonymous visitors now that their data routes are auth='user' (no Odoo
// needed):
//   node tools/js_checks/login_required_check.mjs woow_snippet_builder/static/src/snippets
// For each widget: (1) an anonymous visitor (session.is_website_user) gets the
// sign-in notice and no RPC is sent; (2) a session-expired RPC error also
// renders the notice instead of the red error; (3) other errors still render
// the regular error.  Exit 1 on any failure.
import fs from 'node:fs';
import path from 'node:path';

const dir = process.argv[2];
const strip = (src) => src
  .replace(/^import .*$/mg, '')
  .replace(/^export default .*$/mg, '')
  .replace(/^export /mg, '');

// Minimal DOM stub
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.className = ''; this.textContent = ''; this._html = ''; }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this.children = c; this._html = ''; }
  set innerHTML(v) { this._html = v; this.children = []; }
  get innerHTML() { return this._html; }
  get text() { return this.textContent + this.children.map((c) => c.text).join(' '); }
  get classes() { return [this.className, ...this.children.map((c) => c.classes)].join(' '); }
}
globalThis.document = { createElement: (t) => new El(t) };
globalThis.window = { location: { pathname: '/ha-dashboard', search: '?a=1' } };

const session = { is_website_user: true };
const accessSrc = strip(fs.readFileSync(path.join(dir, 'woow_snippet_access.js'), 'utf8'));
const access = new Function('session', '_t',
  `${accessSrc}; return { isAnonymousVisitor, isLoginRequiredError, renderLoginRequired };`,
)(session, (s) => s);

const widgets = {
  s_woow_stat: { content: '.woow_stat_content', ds: { modelName: 'website.page' } },
  s_woow_chart: { content: '.woow_chart_content', ds: { modelName: 'website.page', labelField: 'url', valueField: 'id' } },
  s_woow_data_table: { content: '.woow_data_table_content', ds: { modelName: 'website.page', fieldNames: 'url' } },
};

let failures = 0;
const check = (ok, msg) => { console.log(`${ok ? 'OK  ' : 'FAIL'} ${msg}`); if (!ok) failures++; };

for (const [name, conf] of Object.entries(widgets)) {
  const src = strip(fs.readFileSync(path.join(dir, name, '000.js'), 'utf8'));
  let captured;
  const publicWidget = { registry: {}, Widget: { extend(o) { captured = o; return o; } } };
  let calls = 0;
  let rpcImpl = async () => { calls++; return {}; };
  const rpc = (...a) => rpcImpl(...a);
  new Function('publicWidget', 'rpc', 'loadJS', 'isAnonymousVisitor', 'isLoginRequiredError', 'renderLoginRequired', src)(
    publicWidget, rpc, async () => {}, access.isAnonymousVisitor, access.isLoginRequiredError, access.renderLoginRequired);

  const make = () => {
    const content = new El('div');
    const self = Object.assign(Object.create(captured), {
      el: { dataset: { ...conf.ds }, querySelector: (s) => (s === conf.content ? content : null) },
      _currentOffset: 0, _sortField: '', _sortOrder: 'asc', _searchTerm: '',
    });
    return { self, content };
  };

  // (1) anonymous visitor: notice, no RPC
  session.is_website_user = true;
  calls = 0;
  let { self, content } = make();
  await self._loadAndRender();
  check(calls === 0, `${name}: no RPC for anonymous visitor`);
  check(content.classes.includes('woow_login_required') && content.text.includes('Sign in'),
    `${name}: sign-in notice for anonymous visitor`);

  // (2) logged in but the session expired meanwhile
  session.is_website_user = false;
  rpcImpl = async () => { calls++; const e = new Error('Odoo Session Expired'); e.code = 100; e.data = { name: 'odoo.http.SessionExpiredException' }; throw e; };
  ({ self, content } = make());
  await self._loadAndRender();
  check(content.classes.includes('woow_login_required') && !content.innerHTML.includes('text-danger'),
    `${name}: session-expired error renders the sign-in notice`);

  // (3) other errors keep the regular error rendering
  rpcImpl = async () => { const e = new Error('Model not allowed'); e.code = 200; e.data = { name: 'odoo.exceptions.UserError' }; throw e; };
  ({ self, content } = make());
  await self._loadAndRender();
  check(!content.classes.includes('woow_login_required')
    && (content.innerHTML.includes('Model not allowed') || content.text.includes('Model not allowed')),
    `${name}: other errors still shown as errors`);
}
process.exit(failures ? 1 : 0);
