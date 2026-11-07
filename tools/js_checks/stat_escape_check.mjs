// Regression check for the Stat Card XSS fix (no Odoo needed):
//   node tools/js_checks/stat_escape_check.mjs woow_snippet_builder/static/src/snippets/s_woow_stat/000.js
// Renders a stat card whose title and group-by label are an HTML payload with
// stubbed Odoo imports and fails (exit 1) when the payload reaches innerHTML
// unescaped.
import fs from 'node:fs';
const src = fs.readFileSync(process.argv[2], 'utf8')
  .replace(/^import .*$/mg, '')
  .replace('export default publicWidget.registry.s_woow_stat;', '');
let captured;
const publicWidget = { registry: {}, Widget: { extend(o) { captured = o; return o; } } };
const rpc = async () => {};
new Function('publicWidget', 'rpc', src)(publicWidget, rpc);
const payload = '<img src=x onerror=alert(1)>';
const el = { innerHTML: '' };
const self = Object.assign(Object.create(captured), {
  el: { dataset: { title: payload, operation: 'count', modelName: 'x' },
        querySelector: () => el },
});
self._renderStat({ value: 3, sub_type: 'default', breakdown: [{ label: payload, value: 1 }] });
const bad = el.innerHTML.includes('<img');
console.log(bad ? 'VULNERABLE: raw <img> in innerHTML' : 'SAFE: payload escaped');
self._renderError({ message: payload });
const badError = el.innerHTML.includes('<img');
console.log(badError ? 'VULNERABLE: error message not escaped' : 'SAFE: error escaped');
process.exit(bad || badError ? 1 : 0);
