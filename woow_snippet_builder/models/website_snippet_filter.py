import logging
from ast import literal_eval

from lxml import etree, html as lxml_html

from odoo import _, api, models
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.osv import expression

from ..tools.snippet_guard import parse_domain, to_int

_logger = logging.getLogger(__name__)


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    # ------------------------------------------------------------------
    # Server action binding guard
    # ------------------------------------------------------------------

    def _woow_check_action_server_binding(self, action_server_id):
        """Only system administrators may bind a snippet filter to a new
        server action.

        Website designers have full access on this model (our
        ``ir.model.access.csv``) so they can manage ``ir.filters`` based
        Dynamic Content filters.  ``action_server_id`` however is run by
        core ``_prepare_values`` with ``sudo()`` for any anonymous visitor
        of ``/website/snippet/filters``: letting a designer point it at an
        arbitrary ``ir.actions.server`` (e.g. a Python code action) would
        let anyone execute that action as superuser.

        Non-system users may therefore only use server actions that are
        already bound to an existing snippet filter (i.e. approved by an
        administrator or shipped by core / website_sale), which adds no
        new exposure; anything else raises ``AccessError``.
        """
        if not action_server_id or self.env.su \
                or self.env.user.has_group('base.group_system'):
            return
        if isinstance(action_server_id, models.BaseModel):
            action_server_id = action_server_id.id
        if self.sudo().search_count(
                [('action_server_id', '=', action_server_id)], limit=1):
            return
        raise AccessError(_(
            "Only administrators can bind a dynamic snippet filter to a "
            "server action."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._woow_check_action_server_binding(vals.get('action_server_id'))
        return super().create(vals_list)

    def write(self, vals):
        if 'action_server_id' in vals:
            new_action = vals['action_server_id']
            if isinstance(new_action, models.BaseModel):
                new_action = new_action.id
            if any(rec.action_server_id.id != (new_action or False)
                   for rec in self.sudo()):
                self._woow_check_action_server_binding(new_action)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Render override
    # ------------------------------------------------------------------

    def _render(self, template_key, limit, search_domain=None,
                with_sample=False, **custom_template_data):
        """Override to handle WoOW generic templates.

        The native implementation rejects template keys that don't embed
        the model technical name (e.g. ``res_partner``).  WoOW templates
        use model-agnostic names like ``dynamic_filter_template_woow_card``
        so they can render records from *any* model.

        When we detect a WoOW template key we skip the model-name guard
        and make sure the ``woow_generic_mapping`` context flag is active
        so that ``_filter_records_to_values`` maps fields generically.
        """
        if '.dynamic_filter_template_woow_' not in template_key:
            return super()._render(
                template_key, limit, search_domain,
                with_sample=with_sample, **custom_template_data,
            )

        # -- WoOW generic path --
        self.ensure_one()
        if search_domain is None:
            search_domain = []

        if (self.website_id
                and self.env['website'].get_current_website() != self.website_id):
            return ''

        records = self.with_context(
            woow_generic_mapping=True,
        )._woow_prepare_values(limit=limit, search_domain=search_domain)
        is_sample = with_sample and not records
        if is_sample:
            records = self._prepare_sample(limit)

        content = self.env['ir.qweb'].with_context(
            inherit_branding=False,
        )._render(template_key, dict(
            records=records,
            is_sample=is_sample,
            **custom_template_data,
        ))
        return [
            etree.tostring(el, encoding='unicode', method='html')
            for el in lxml_html.fromstring(
                '<root>%s</root>' % str(content)
            ).getchildren()
        ]

    # ------------------------------------------------------------------
    # WoOW-specific record loading (visitor environment, like core)
    # ------------------------------------------------------------------

    def _woow_allowed_search_fields(self):
        """Field names a visitor may filter on through ``search_domain``:
        the fields configured on the filter (``field_names``)."""
        return {
            spec.split(':')[0].strip()
            for spec in (self.field_names or '').split(',')
            if spec.strip()
        }

    def _woow_prepare_values(self, limit=None, search_domain=None):
        """Like core ``_prepare_values``: records are searched with the
        visitor's own access rights (``sudo(False)``, so ACL and record
        rules apply) restricted to the current website / company and to
        published records; only the configured ``field_names`` of the
        records found are then rendered with sudo.

        The visitor supplied ``search_domain`` may only contain plain
        (non-dotted) leaves on the filter's ``field_names`` with a
        whitelisted operator; anything else renders nothing.
        """
        self.ensure_one()
        max_limit = max(self.limit, 16)
        limit = to_int(limit, 0, 0, max_limit) or max_limit

        if not self.filter_id:
            return []

        filter_sudo = self.filter_id.sudo()
        if not filter_sudo.active:
            # Archived ir.filters (e.g. retired legacy demo filters) are
            # not served on the website.
            return []
        model_name = filter_sudo.model_id
        if model_name not in self.env:
            return []
        Model = self.env[model_name].sudo(False)
        if not Model.has_access('read'):
            return []

        try:
            visitor_domain = parse_domain(
                search_domain or [], Model,
                allowed_fields=self._woow_allowed_search_fields(),
            )
        except UserError as e:
            _logger.warning(
                'Rejected search_domain for snippet filter %s: %s',
                self.id, e.args[0] if e.args else e,
            )
            return []

        website = self.env['website'].get_current_website()
        domain = filter_sudo._get_eval_domain()
        if 'website_id' in Model:
            domain = expression.AND([domain, website.website_domain()])
        if 'company_id' in Model:
            domain = expression.AND([
                domain, [('company_id', 'in', [False, website.company_id.id])],
            ])
        if 'is_published' in Model:
            domain = expression.AND([domain, [('is_published', '=', True)]])
        if visitor_domain:
            domain = expression.AND([domain, visitor_domain])

        ctx = literal_eval(filter_sudo.context) if filter_sudo.context else {}
        sort = literal_eval(filter_sudo.sort) if filter_sudo.sort else []
        try:
            records = Model.with_context(
                **ctx, lang=website.default_lang_id.code,
            ).search(
                domain,
                order=','.join(sort) or None,
                limit=limit,
            )
        except MissingError:
            _logger.warning(
                "The domain %s of snippet filter %s generated a MissingError",
                domain, self.id,
            )
            return []
        return self._filter_records_to_values(records.sudo())

    # ------------------------------------------------------------------
    # Legacy demo filter retirement (used by the 18.0.2.0.1 migration)
    # ------------------------------------------------------------------

    def _woow_is_referenced_on_website(self):
        """Return whether a view (website page, COW copy, ...) embeds a
        dynamic snippet bound to this filter (``data-filter-id``)."""
        self.ensure_one()
        # arch_db is a translated jsonb column: quotes appear escaped.
        pattern = r"""data-filter-id=\\?["']%d\\?["']""" % self.id
        self.env.cr.execute(
            "SELECT 1 FROM ir_ui_view WHERE arch_db::text ~ %s LIMIT 1",
            [pattern],
        )
        return bool(self.env.cr.fetchone())

    def _woow_retire_legacy_filters(self):
        """Retire the res.partner demo filters that older versions shipped
        as regular data.  Unreferenced filters are deleted (with their
        ``ir.filters``); filters still used on a page are kept but their
        ``ir.filters`` is archived so they are no longer served publicly.

        :return: tuple (deleted names, archived names)
        """
        deleted, archived = [], []
        for snippet_filter in self.sudo().exists():
            if snippet_filter._woow_is_referenced_on_website():
                if snippet_filter.filter_id.active:
                    snippet_filter.filter_id.active = False
                archived.append(snippet_filter.name)
                continue
            ir_filter = snippet_filter.filter_id
            deleted.append(snippet_filter.name)
            snippet_filter.unlink()
            if ir_filter.exists() and not self.sudo().search_count(
                    [('filter_id', '=', ir_filter.id)]):
                ir_filter.unlink()
        return deleted, archived

    # ------------------------------------------------------------------
    # Generic field mapping
    # ------------------------------------------------------------------

    def _filter_records_to_values(self, records, is_sample=False):
        """Override to map arbitrary fields to generic keys when woow_generic_mapping
        context flag is set.

        This allows QWeb templates to use stable keys (field_0, field_1, …, image)
        regardless of the actual model field names, enabling a single set of
        templates to render records from any model.
        """
        if not self.env.context.get('woow_generic_mapping'):
            return super()._filter_records_to_values(records, is_sample=is_sample)

        values = []
        field_list = [
            f.strip()
            for f in (self.field_names or '').split(',')
            if f.strip()
        ]
        visitor_env = self.sudo(False).env
        for record in records:
            data = {'_record': record}
            field_idx = 0
            for field_spec in field_list:
                raw_name = field_spec.split(':')[0]  # strip :widget suffix
                field_meta = record._fields.get(raw_name)
                if not field_meta or not field_meta.is_accessible(visitor_env):
                    # never render group-restricted fields to visitors
                    # who could not read them themselves
                    continue
                if field_meta.type in ('binary', 'image'):
                    if is_sample:
                        data['image'] = '/web/image'
                    else:
                        data['image'] = (
                            f'/web/image/{record._name}/{record.id}/{raw_name}'
                        )
                else:
                    val = record[raw_name]
                    if hasattr(val, 'display_name'):
                        val = val.display_name
                    data[f'field_{field_idx}'] = val
                    field_idx += 1
            data['call_to_action_url'] = getattr(record, 'website_url', '#')
            data['display_name'] = record.display_name
            values.append(data)
        return values
