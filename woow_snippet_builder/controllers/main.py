import logging

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.osv import expression

from ..tools.snippet_guard import (
    GROUPABLE_TYPES, MINMAX_TYPES, NUMERIC_TYPES, BLOCKED_TYPES,
    check_field, parse_domain, to_float, to_int,
)

_logger = logging.getLogger(__name__)

# Models that the public snippet endpoints may query.  The endpoints never
# use sudo: the visitor's own access rights (ACL + record rules + field
# groups) always apply, this list is only an additional allow-list so that
# the endpoints cannot be pointed at arbitrary models.  Keep it to models
# that are meant to be shown on a website.  Extend it via
# ``_get_allowed_models`` on a custom controller if you really need more.
_DEFAULT_ALLOWED_MODELS = frozenset({
    'product.template',
    'product.product',
    'product.public.category',
    'event.event',
    'event.type',
    'website.page',
    'blog.post',
    'slide.channel',
    # Home Assistant models (odoo_ha_addon).  They have no public ACL: the
    # HA dashboard only shows data to logged-in users of the HA groups,
    # filtered by the HA record rules.
    'ha.instance',
    'ha.area',
    'ha.device',
    'ha.entity',
    'ha.entity.history',
    'ha.entity.group',
    'ha.label',
})

_VALID_SORT_ORDERS = {'asc', 'desc'}
_VALID_OPERATIONS = {'count', 'sum', 'avg', 'min', 'max', 'count_distinct'}
_VALID_SUB_TYPES = {'default', 'progress', 'trend', 'threshold'}
_VALID_CHART_TYPES = {
    'bar', 'line', 'pie', 'doughnut', 'radar', 'polarArea',
    'bar_horizontal', 'bar_stacked', 'gauge', 'funnel',
}
# Hard limits on what one request may return / ask for.
_MAX_GROUPS = 50
_MAX_SERIES_GROUPS = 500
_MAX_TABLE_FIELDS = 30
_MAX_TABLE_LIMIT = 100
_MAX_OFFSET = 1000000
_MAX_SEARCH_TERM = 200


def _group_label(value):
    if isinstance(value, (list, tuple)):
        value = value[1] if len(value) > 1 else value[0]
    return value


class WoowSnippetController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_allowed_models(self):
        """Return the set of model technical names that may be queried by
        the public snippet endpoints.  Override to extend (the returned
        set may be modified by overrides)."""
        return set(_DEFAULT_ALLOWED_MODELS)

    def _validate_model(self, model_name):
        """Raise if the model is not in the allow-list or doesn't exist."""
        if not isinstance(model_name, str) \
                or model_name not in self._get_allowed_models():
            raise UserError(f'Model {model_name!r} is not allowed')
        if model_name not in request.env:
            raise UserError(f'Model {model_name!r} does not exist')

    def _get_model(self, model_name):
        """Validated model in the *visitor's* environment (never sudo).

        Raises :class:`AccessError` when the visitor may not read it.
        """
        self._validate_model(model_name)
        Model = request.env[model_name]
        Model.check_access('read')
        return Model

    def _check_designer(self):
        if not request.env.user.has_group(
                'website.group_website_restricted_editor'):
            raise NotFound()

    # ------------------------------------------------------------------
    # Editor-only RPC (website designers / restricted editors)
    # ------------------------------------------------------------------

    @http.route('/woow_snippet/available_models', type='json', auth='user',
                website=True)
    def get_available_models(self):
        """Return a list of models available for snippet configuration.

        Each entry is ``{'model': 'product.template', 'name': 'Product'}``.
        """
        self._check_designer()
        result = []
        for model_name in sorted(self._get_allowed_models()):
            model = request.env.get(model_name)
            if model is not None:
                result.append({
                    'model': model_name,
                    'name': model._description or model_name,
                })
        return result

    @http.route('/woow_snippet/model_fields', type='json', auth='user',
                website=True)
    def get_model_fields(self, model_name):
        """Return the fields of *model_name* the public endpoints accept.

        Each entry is ``{'name': 'field_name', 'string': 'Field Label',
        'type': 'char'}``.
        """
        self._check_designer()
        self._validate_model(model_name)
        Model = request.env[model_name]
        result = []
        for fname, field in sorted(Model._fields.items()):
            if fname.startswith('_') or not field.store or field.groups:
                continue
            # Skip relational / binary blobs that are not useful for
            # stat / chart / table display.
            if field.type == 'one2many' or field.type in BLOCKED_TYPES:
                continue
            result.append({
                'name': fname,
                'string': field.string or fname,
                'type': field.type,
            })
        return result

    # ------------------------------------------------------------------
    # Public data endpoints (auth='public', visitor environment)
    # ------------------------------------------------------------------

    @http.route('/woow_snippet/stat', type='json', auth='public',
                website=True, readonly=True)
    def get_stat(self, model_name, operation='count', field_name='',
                 group_by='', domain='[]', sub_type='default',
                 target_value=100, threshold_warning=50,
                 threshold_danger=25, previous_value=0):
        """Return aggregated stat data for the Stat Card snippet."""
        Model = self._get_model(model_name)
        if operation not in _VALID_OPERATIONS:
            raise UserError(f'Invalid operation: {operation!r}')
        if sub_type not in _VALID_SUB_TYPES:
            sub_type = 'default'
        parsed_domain = parse_domain(domain, Model)

        if operation == 'count' or not field_name:
            value = Model.search_count(parsed_domain)
        elif operation == 'count_distinct':
            check_field(Model, field_name, purpose='stat field',
                        types=GROUPABLE_TYPES | NUMERIC_TYPES)
            [(value,)] = Model._read_group(
                parsed_domain, aggregates=[f'{field_name}:count_distinct'])
        else:
            types = MINMAX_TYPES if operation in ('min', 'max') \
                else NUMERIC_TYPES
            check_field(Model, field_name, purpose='stat field', types=types)
            [(value,)] = Model._read_group(
                parsed_domain, aggregates=[f'{field_name}:{operation}'])
        if value is None or value is False:
            value = 0

        # Group-by breakdown (bounded number of groups)
        breakdown = []
        if group_by:
            check_field(Model, group_by, purpose='group by',
                        types=GROUPABLE_TYPES)
            groups = Model.read_group(parsed_domain, [], [group_by],
                                      limit=_MAX_GROUPS)
            for g in groups:
                count = g.get(f'{group_by}_count', g.get('__count', 0))
                breakdown.append({
                    'label': str(_group_label(g.get(group_by))),
                    'value': count,
                })

        target_value = to_float(target_value, 100) or 100
        previous_value = to_float(previous_value, 0)
        numeric_value = value if isinstance(value, (int, float)) else 0

        result = {
            'value': value,
            'sub_type': sub_type,
            'breakdown': breakdown,
        }
        if sub_type == 'progress':
            result['target'] = target_value
            result['percent'] = round(numeric_value / target_value * 100, 1)
        elif sub_type == 'trend':
            delta = numeric_value - previous_value
            result['delta'] = delta
            result['delta_percent'] = (
                round(delta / previous_value * 100, 1) if previous_value else 0
            )
        elif sub_type == 'threshold':
            result['target'] = target_value
            threshold_warning = to_float(threshold_warning, 50) or 50
            threshold_danger = to_float(threshold_danger, 25) or 25
            pct = round(numeric_value / target_value * 100, 1)
            result['percent'] = pct
            if pct >= threshold_warning:
                result['status'] = 'success'
            elif pct >= threshold_danger:
                result['status'] = 'warning'
            else:
                result['status'] = 'danger'

        return result

    @http.route('/woow_snippet/chart', type='json', auth='public',
                website=True, readonly=True)
    def get_chart(self, model_name, chart_type='bar', label_field='',
                  value_field='', domain='[]', gauge_max=100,
                  series_field=''):
        """Return aggregated chart data for the Chart snippet."""
        Model = self._get_model(model_name)
        parsed_domain = parse_domain(domain, Model)
        if chart_type not in _VALID_CHART_TYPES:
            chart_type = 'bar'
        gauge_max = to_float(gauge_max, 100) or 100

        if not label_field or not value_field:
            return {'labels': [], 'datasets': []}

        check_field(Model, label_field, purpose='label field',
                    types=GROUPABLE_TYPES)
        # Use the record count when value_field is 'id' / '__count'.
        use_count = value_field in ('id', '__count')
        if not use_count:
            check_field(Model, value_field, purpose='value field',
                        types=NUMERIC_TYPES)
        agg_fields = [] if use_count else [value_field]

        def _extract_value(group, groupby_field):
            """Get the numeric value from a read_group result dict."""
            if use_count:
                count_key = f'{groupby_field}_count'
                return group.get(count_key, group.get('__count', 0)) or 0
            return group.get(value_field, 0) or 0

        if series_field:
            check_field(Model, series_field, purpose='series field',
                        types=GROUPABLE_TYPES)
            groups = Model.read_group(
                parsed_domain, agg_fields, [label_field, series_field],
                lazy=False, limit=_MAX_SERIES_GROUPS,
            )

            label_set = []
            series_map = {}
            for g in groups:
                lbl = _group_label(g.get(label_field))
                lbl = str(lbl) if lbl else ''
                ser = _group_label(g.get(series_field))
                ser = str(ser) if ser else ''

                if lbl not in label_set:
                    if len(label_set) >= _MAX_GROUPS:
                        continue
                    label_set.append(lbl)
                if ser not in series_map and len(series_map) >= _MAX_GROUPS:
                    continue
                series_map.setdefault(ser, {})[lbl] = _extract_value(
                    g, label_field)

            datasets = []
            for series_name, data_map in series_map.items():
                datasets.append({
                    'label': series_name,
                    'data': [data_map.get(l, 0) for l in label_set],
                })

            return {
                'labels': label_set,
                'datasets': datasets,
                'chart_type': chart_type,
                'gauge_max': gauge_max,
            }

        # Single series
        groups = Model.read_group(parsed_domain, agg_fields, [label_field],
                                  limit=_MAX_GROUPS)
        labels = []
        data = []
        for g in groups:
            lbl = _group_label(g.get(label_field))
            labels.append(str(lbl) if lbl else '')
            data.append(_extract_value(g, label_field))

        return {
            'labels': labels,
            'datasets': [{'label': value_field, 'data': data}],
            'chart_type': chart_type,
            'gauge_max': gauge_max,
        }

    @http.route('/woow_snippet/data_table', type='json', auth='public',
                website=True, readonly=True)
    def get_data_table(self, model_name, field_names='', domain='[]',
                       offset=0, limit=25, sort_field='', sort_order='asc',
                       search_term=''):
        """Return paginated table data for the Data Table snippet."""
        Model = self._get_model(model_name)
        parsed_domain = parse_domain(domain, Model)

        if not isinstance(field_names, str):
            raise UserError('Invalid field list')
        fields = [f.strip() for f in field_names.split(',') if f.strip()]
        if not fields:
            return {'columns': [], 'rows': [], 'total': 0}
        if len(fields) > _MAX_TABLE_FIELDS:
            raise UserError('Too many fields')

        # Build column metadata: every requested field must be readable by
        # the visitor (no ``groups``); display may use non-stored fields.
        columns = []
        valid_fields = []
        for fname in dict.fromkeys(fields):
            field = check_field(Model, fname, stored=False,
                                purpose='column')
            columns.append({
                'name': fname,
                'string': field.string or fname,
                'type': field.type,
            })
            valid_fields.append(fname)

        # Free-text search across stored char/text/html fields
        if search_term:
            if not isinstance(search_term, str):
                raise UserError('Invalid search term')
            search_term = search_term[:_MAX_SEARCH_TERM]
            search_domains = []
            for fname in valid_fields:
                field = Model._fields[fname]
                if field.store and field.type in ('char', 'text', 'html'):
                    search_domains.append([(fname, 'ilike', search_term)])
            if search_domains:
                parsed_domain = expression.AND([
                    parsed_domain, expression.OR(search_domains),
                ])

        # Sorting (stored, displayed fields only)
        order = None
        if sort_field and sort_field in valid_fields \
                and Model._fields[sort_field].store:
            so = sort_order if sort_order in _VALID_SORT_ORDERS else 'asc'
            order = f'{sort_field} {so}'

        offset = to_int(offset, 0, 0, _MAX_OFFSET)
        limit = to_int(limit, 25, 1, _MAX_TABLE_LIMIT)

        total = Model.search_count(parsed_domain)
        records = Model.search(parsed_domain, offset=offset, limit=limit,
                               order=order)

        rows = []
        for rec in records:
            row = {'id': rec.id}
            for fname in valid_fields:
                row[fname] = self._display_value(rec, fname)
            rows.append(row)

        return {
            'columns': columns,
            'rows': rows,
            'total': total,
            'offset': offset,
            'limit': limit,
        }

    def _display_value(self, record, fname):
        """Serialise one field value the way ``read`` would: many2one
        values show the display name (like core ``convert_to_read``),
        x2many values only when the visitor may read the comodel."""
        field = record._fields[fname]
        val = record[fname]
        if field.type == 'many2one':
            return val.sudo().display_name if val else False
        if field.type in ('one2many', 'many2many'):
            try:
                return ', '.join(val.mapped('display_name'))
            except AccessError:
                return ''
        return val
