"""Input validation shared by the public WoOW snippet endpoints and the
Dynamic Content filter rendering.

Everything in here works on values that come straight from an anonymous
website visitor, so the rules are deliberately strict:

* fields must exist on the model, must not start with ``_``, must not be
  restricted by ``groups`` and (when used in a domain, a group-by, an
  aggregate or an ORDER BY) must be stored;
* domains are parsed with :func:`ast.literal_eval` (never ``safe_eval``),
  may only contain ``'&'``, ``'|'``, ``'!'`` and ``(field, operator, value)``
  leaves, never dotted paths, and only whitelisted operators;
* numbers coming from the request are converted without raising (and
  without accepting ``nan`` / ``inf``).

All rejections raise :class:`odoo.exceptions.UserError`, which the JSON-RPC
layer turns into a regular error response (logged as a warning, not as a
server error).
"""
import ast
import math

from odoo import fields as odoo_fields
from odoo.exceptions import UserError
from odoo.osv import expression

# Operators accepted in visitor supplied domains.
DOMAIN_OPERATORS = frozenset({
    '=', '!=', '>', '>=', '<', '<=', 'in', 'not in', 'ilike', 'like',
})
LOGIC_OPERATORS = frozenset({'&', '|', '!'})
_RELATIONAL_OPERATORS = frozenset({'=', '!=', 'in', 'not in'})
_LIKE_OPERATORS = frozenset({'like', 'ilike'})
_LIST_OPERATORS = frozenset({'in', 'not in'})

MAX_DOMAIN_CHARS = 4000
MAX_DOMAIN_ITEMS = 64
MAX_IN_VALUES = 500

NUMERIC_TYPES = frozenset({'integer', 'float', 'monetary'})
MINMAX_TYPES = NUMERIC_TYPES | {'date', 'datetime'}
GROUPABLE_TYPES = frozenset({
    'char', 'selection', 'boolean', 'integer', 'many2one', 'many2many',
    'date', 'datetime',
})
RELATIONAL_TYPES = frozenset({'many2one', 'one2many', 'many2many'})
TEXT_TYPES = frozenset({'char', 'text', 'html', 'selection'})
# Types that can never be searched / displayed through the snippets.
BLOCKED_TYPES = frozenset({
    'binary', 'image', 'serialized', 'properties', 'properties_definition',
    'json', 'reference', 'many2one_reference',
})


def _reject(message):
    raise UserError(message)


def check_field(model, fname, *, stored=True, types=None, purpose='field'):
    """Return the field object of ``model`` named ``fname`` or raise.

    :param stored: require a stored (database) column
    :param types: optional set of accepted field types
    """
    if not isinstance(fname, str) or not fname or fname.startswith('_') \
            or '.' in fname:
        _reject(f'Invalid {purpose}: {fname!r}')
    field = model._fields.get(fname)
    if field is None:
        _reject(f'Unknown {purpose} {fname!r} on {model._name}')
    if field.groups:
        _reject(f'Field {fname!r} is restricted and cannot be used')
    if field.type in BLOCKED_TYPES:
        _reject(f'Field {fname!r} cannot be used')
    if stored and not field.store:
        _reject(f'Field {fname!r} is not stored and cannot be used as {purpose}')
    if types is not None and field.type not in types:
        _reject(f'Field {fname!r} ({field.type}) cannot be used as {purpose}')
    return field


def _is_scalar(value):
    if value is None or isinstance(value, (bool, int, str)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _check_value(field, operator, value):
    """Check that ``value`` is a plain literal that fits the field type."""
    if operator in _LIST_OPERATORS:
        if not isinstance(value, (list, tuple)):
            value = [value]
        if len(value) > MAX_IN_VALUES:
            _reject('Too many values in domain')
        values = list(value)
    else:
        if isinstance(value, (list, tuple)):
            _reject(f'Operator {operator!r} does not accept a list')
        values = [value]

    for val in values:
        if not _is_scalar(val):
            _reject('Unsupported value in domain')
        if field.type in RELATIONAL_TYPES:
            # Only compare record ids: string values would trigger a
            # name_search on the comodel (possibly through auto_join).
            if operator not in _RELATIONAL_OPERATORS:
                _reject(f'Operator {operator!r} not allowed on relational field')
            if isinstance(val, str) or isinstance(val, float):
                _reject('Relational fields can only be compared to ids')
        elif operator in _LIKE_OPERATORS:
            if field.type not in TEXT_TYPES or not isinstance(val, str):
                _reject(f'Operator {operator!r} needs a text field and value')
        elif field.type in ('date', 'datetime'):
            if val in (None, False):
                continue
            if not isinstance(val, str):
                _reject('Date values must be strings')
            try:
                if field.type == 'date':
                    odoo_fields.Date.to_date(val)
                else:
                    odoo_fields.Datetime.to_datetime(val)
            except (ValueError, TypeError):
                _reject('Invalid date value in domain')
        elif field.type in NUMERIC_TYPES:
            if isinstance(val, str):
                _reject('Numeric fields need numeric values')
        elif field.type == 'boolean':
            if not isinstance(val, bool) and val is not None:
                _reject('Boolean fields need boolean values')
        else:  # char / text / html / selection
            if not isinstance(val, (str, bool)) and val is not None:
                _reject('Text fields need text values')
    return value


def parse_domain(domain, model, allowed_fields=None):
    """Parse and validate a visitor supplied domain.

    :param domain: a string (``"[('name', '=', 'x')]"``) or a list
    :param model: the (non-sudo) model the domain applies to
    :param allowed_fields: optional collection restricting the leaf fields
    :return: a normalized domain list (``[]`` when empty)
    """
    if domain in (None, False, '', '[]'):
        return []
    if isinstance(domain, str):
        if len(domain) > MAX_DOMAIN_CHARS:
            _reject('Domain is too long')
        try:
            domain = ast.literal_eval(domain.strip())
        except (ValueError, SyntaxError, TypeError, MemoryError,
                RecursionError):
            _reject('Invalid domain')
    if not isinstance(domain, (list, tuple)):
        _reject('Invalid domain')
    if not domain:
        return []
    if len(domain) > MAX_DOMAIN_ITEMS:
        _reject('Domain is too long')

    result = []
    for item in domain:
        if isinstance(item, str):
            if item not in LOGIC_OPERATORS:
                _reject(f'Invalid domain operator {item!r}')
            result.append(item)
            continue
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            _reject('Invalid domain leaf')
        fname, operator, value = item
        if not isinstance(operator, str) or operator not in DOMAIN_OPERATORS:
            _reject(f'Operator {operator!r} is not allowed')
        if not isinstance(fname, str) or '.' in fname:
            _reject('Related (dotted) paths are not allowed in domains')
        if allowed_fields is not None and fname not in allowed_fields:
            _reject(f'Field {fname!r} is not allowed in this domain')
        field = check_field(model, fname, stored=True, purpose='domain field')
        value = _check_value(field, operator, value)
        result.append((fname, operator, value))

    try:
        return expression.normalize_domain(result)
    except (ValueError, AssertionError):
        _reject('Invalid domain')


def to_int(value, default, minimum=None, maximum=None):
    """Convert a request value into a bounded int without raising."""
    if isinstance(value, bool):
        number = default
    elif isinstance(value, int):
        number = value
    elif isinstance(value, float) and math.isfinite(value):
        number = int(value)
    elif isinstance(value, str) and value.strip().lstrip('-').isdigit() \
            and len(value.strip()) <= 12:
        number = int(value.strip())
    else:
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def to_float(value, default):
    """Convert a request value into a finite float (``nan``/``inf`` and
    garbage fall back to ``default``)."""
    if isinstance(value, bool) or value in (None, ''):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return number
