{
    'name': 'WoOW Snippet Builder',
    'version': '18.0.2.0.2',
    'category': 'Website',
    'summary': 'Dynamic website snippets with native editor integration',
    'description': """
WoOW Snippet Builder
====================
Provides four dynamic website snippets that integrate natively with
the Odoo 18 website editor BLOCKS and CUSTOMIZE panels:

- **Dynamic Content**: Extends the native dynamic snippet system to display
  records from any model using configurable QWeb templates.
- **Stat Card**: Aggregation-based stat cards showing count, sum, avg, min, max
  with progress bar, trend, and threshold sub-types.
- **Chart**: Chart.js powered visualisations including bar, line, pie, doughnut,
  radar, polar area, horizontal bar, stacked bar, gauge, and funnel.
- **Data Table**: Paginated, searchable, sortable data tables for any model.

All snippets are configured entirely within the website editor — no backend
navigation required.
    """,
    'author': 'WoOW Technology',
    'website': 'https://woowtech.com',
    'depends': ['website'],
    'data': [
        # Only the website designer CRUD row on website.snippet.filter (the
        # public read row of 18.0.2.0.0 is gone and removed on upgrade).
        'security/ir.model.access.csv',
        'data/woow_dynamic_filter_templates.xml',
        'views/snippets/snippets.xml',
        'views/snippets/s_woow_dynamic_content.xml',
        'views/snippets/s_woow_stat.xml',
        'views/snippets/s_woow_chart.xml',
        'views/snippets/s_woow_data_table.xml',
        'views/ha_dashboard.xml',
    ],
    'demo': [
        'demo/woow_snippet_filter_demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'woow_snippet_builder/static/src/snippets/woow_snippet_access.js',
            'woow_snippet_builder/static/src/snippets/s_woow_dynamic_content/000.js',
            'woow_snippet_builder/static/src/snippets/s_woow_stat/000.js',
            'woow_snippet_builder/static/src/snippets/s_woow_chart/000.js',
            'woow_snippet_builder/static/src/snippets/s_woow_data_table/000.js',
        ],
        'website.assets_wysiwyg': [
            'woow_snippet_builder/static/src/snippets/s_woow_dynamic_content/options.js',
            'woow_snippet_builder/static/src/snippets/s_woow_stat/options.js',
            'woow_snippet_builder/static/src/snippets/s_woow_chart/options.js',
            'woow_snippet_builder/static/src/snippets/s_woow_data_table/options.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
