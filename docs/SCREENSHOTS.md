# WoOW Snippet Builder -- Visual Gallery

A comprehensive visual walkthrough of the **WoOW Snippet Builder** module for Odoo 18. Every screenshot below was captured from a live Odoo instance running the module against real `res.partner` data.

---

## Table of Contents

1. [Overview -- Full Showcase Page](#1-overview--full-showcase-page)
2. [Stat Cards -- Four Render Styles](#2-stat-cards--four-render-styles)
3. [Charts -- Interactive Chart.js Visualizations](#3-charts--interactive-chartjs-visualizations)
4. [Data Table -- Search, Sort, and Paginate](#4-data-table--search-sort-and-paginate)
5. [Dynamic Content -- Templated Record Cards](#5-dynamic-content--templated-record-cards)
6. [Public Access -- Unauthenticated Visitor View](#6-public-access--unauthenticated-visitor-view)
7. [Backend Administration -- Module, Settings, and Filters](#7-backend-administration--module-settings-and-filters)
8. [API Endpoints -- JSON Responses](#8-api-endpoints--json-responses)

---

## 1. Overview -- Full Showcase Page

The showcase page is a single website page that exercises every snippet type the module provides. It serves as both a functional demo and an integration test: if this page renders correctly, the entire module is working.

### Full Showcase Page

![Full Showcase Page](screenshots/showcase_full.png)

*The complete WoOW Snippet Builder showcase page rendered end-to-end. From top to bottom it contains: a hero banner with animated gradient, four stat cards summarizing contact data, a bar chart and pie chart section, a data table with live search, and dynamic content cards -- all powered by live queries against `res.partner`. This single page validates that every snippet type, every JavaScript controller, and every backend endpoint are functioning correctly together.*

### Showcase Page -- Top Section (Hero + Stats)

![Showcase Hero and Stat Cards](screenshots/showcase_hero.png)

*The top portion of the showcase page. The hero banner displays the module title with a call-to-action button. Directly below sit four stat cards, each demonstrating a different render style against the same `res.partner` dataset. This section loads first and gives an immediate visual confirmation that the module is active and data is flowing.*

---

## 2. Stat Cards -- Four Render Styles

Stat cards display a single aggregated metric (count, sum, average, min, or max) drawn from any whitelisted Odoo model. The module ships four distinct visual render styles, each suited to a different analytical purpose. All four are visible side by side on the showcase page.

### All Four Stat Card Styles

![Stat Cards -- All Four Styles](screenshots/showcase_stat_cards.png)

*Four stat cards rendered side by side, each querying `res.partner` but presenting the result in a different style:*

- **Default (leftmost)** -- Displays "30 Contacts" as a plain numeric value with a large icon. Best for simple KPIs where the number itself tells the story. The value is computed via `search_count` on the model.
- **Progress (second from left)** -- Shows "36% of 50" with a circular progress ring. The current count (18) is measured against a configurable target (50). Ideal for goal tracking: fundraising targets, onboarding milestones, quota completion.
- **Trend (second from right)** -- Reads "+2 (+20%)" with an upward-pointing arrow. Compares the current period's count against the previous period and calculates both absolute and percentage change. Green indicates growth; red would indicate decline. Useful for week-over-week or month-over-month dashboards.
- **Threshold (rightmost)** -- Displays "30% of target" with a horizontal bar that has turned yellow, indicating the value has crossed the warning threshold but not yet reached the danger threshold. Three color zones are configurable: green (on track), yellow (warning), and red (critical). Designed for SLA monitoring, inventory alerts, or budget burn-rate tracking.

### Stat Cards -- Alternative Session

![Stat Cards -- Older Session](screenshots/demo_stat_cards.png)

*A different demo session showing three stat cards with different data: "30 Contacts", "18 Companies", and "11 Countries". This demonstrates that stat cards can be pointed at different models or filtered subsets of the same model, each with its own icon, label, and color scheme. The card layout is fully responsive and reflows on smaller screens.*

---

## 3. Charts -- Interactive Chart.js Visualizations

The chart snippet wraps Chart.js and connects it to Odoo's `read_group` API. The user selects a model, a group-by field, and an aggregate function in the website editor; the snippet fetches data at page load and renders an interactive chart with tooltips, legends, and responsive sizing.

### Bar Chart and Pie Chart

![Bar Chart and Pie Chart](screenshots/showcase_charts.png)

*The charts section of the showcase page showing two charts side by side. On the left, a vertical bar chart titled "Partners by Country" groups `res.partner` records by the `country_id` field and displays the count per country. Each bar is a distinct color from the module's built-in palette. On the right, a pie chart presents the same "Partners by Country" data as proportional slices. Hovering over any slice or bar reveals a tooltip with the exact count. Both charts are fully responsive and redraw on window resize.*

### Radar Chart and Additional Chart Types

![Radar and Additional Charts](screenshots/showcase_charts_2.png)

*Additional chart types rendered on the showcase page. This section demonstrates that the same data can be visualized in multiple ways without any code changes -- only the `data-chart-type` attribute differs. The module supports ten chart types in total: Bar, Line, Pie, Doughnut, Radar, Polar Area, Horizontal Bar, Stacked Bar, Gauge, and Funnel.*

### Charts -- Multi-Type Demo (Older Session)

![Charts -- Bar, Doughnut, Radar, Line](screenshots/demo_charts.png)

*A four-chart demo layout from a separate session. Top-left: a bar chart showing "Partners per City" with cities on the x-axis. Top-right: a doughnut chart (hollow center variant of pie) showing the same city distribution. Bottom-left: a radar chart mapping city counts onto a polygon. Bottom-right: a line chart connecting city counts with smooth curves. This screenshot confirms that all four major chart families (bar, arc, radar, line) render correctly from the same underlying data source.*

---

## 4. Data Table -- Search, Sort, and Paginate

The data table snippet renders a fully interactive HTML table with server-side pagination, column sorting, and debounced search. All data fetching happens via JSON-RPC calls to the backend controller, meaning the table works with datasets of any size without loading all records into the browser.

### Interactive Data Table with Search and Pagination

![Data Table](screenshots/showcase_data_table.png)

*A data table displaying `res.partner` records with five columns: Name, Email, Phone, City, and Country. Key interactive features visible in this screenshot:*

- **Search box** (top-right) -- Accepts free-text input and filters results with a 300ms debounce delay to avoid excessive server calls. The search queries across all displayed fields using Odoo's `ilike` operator.
- **Sortable column headers** -- Each column header is clickable. Clicking toggles between ascending and descending sort order, indicated by an arrow icon. Sorting is performed server-side via the `order` parameter on `search_read`.
- **Pagination controls** (bottom) -- Shows "1-10 of 30" indicating the first page of three. Page buttons allow navigation between pages. The page size is configurable in the editor (default: 10 rows per page).
- **XSS-safe rendering** -- All field values are HTML-escaped before insertion into the DOM, preventing injection attacks from user-supplied data.

### Data Table -- Alternative Session

![Data Table -- Older Session](screenshots/demo_data_table.png)

*An alternative view of the Contact List Table from a different demo session showing city, country, email, and name fields. This confirms that the column selection is fully configurable: the editor lets you pick any combination of fields from the model, and the table header labels are derived from the field's `string` attribute in Odoo's field metadata.*

---

## 5. Dynamic Content -- Templated Record Cards

Dynamic content snippets extend Odoo's native `website.snippet.filter` system with custom QWeb templates. Rather than displaying a single aggregated value (like stat cards) or a visualization (like charts), dynamic content renders individual records in a repeating layout -- cards, lists, or grids.

### Card Template -- Contact Cards

![Dynamic Content Cards](screenshots/showcase_dynamic_content.png)

*The Dynamic Content section of the showcase page using the Card Template. Each card represents one `res.partner` record and displays three mapped fields: city (field_0), email (field_1), and company (field_2). Cards are arranged in a responsive grid that reflows from 3 columns on desktop to 1 column on mobile. The template uses generic field slots (field_0, field_1, field_2, image) so the same card layout works for any model -- contacts, products, events, or any other whitelisted model.*

### Card Layout -- Context Filter Demo

![Dynamic Content Cards -- Context Filter](screenshots/demo_dynamic_content_cards.png)

*A context filter demonstration showing contact cards with email, company, and phone fields. Context filtering allows dynamic content to react to the current page context or URL parameters. For example, placing this snippet on a partner's portal page would automatically filter to show only records related to that partner, without any manual configuration.*

### List View -- Records Grouped by City

![Dynamic Content List View](screenshots/demo_dynamic_content_list.png)

*Dynamic content rendered in a list-style template, with records organized by city. This alternative template demonstrates that the same underlying `website.snippet.filter` record can be displayed in multiple visual formats. The template is selected via a dropdown in the editor's CUSTOMIZE panel. Six templates ship with the module: Card, List, Hero Card, Compact, Table, and Timeline.*

---

## 6. Public Access -- Unauthenticated Visitor View

A critical feature of the WoOW Snippet Builder is that all snippets render correctly for unauthenticated website visitors. The backend controllers use `sudo()` for data access, and the JavaScript controllers bypass Odoo's model-name guard to ensure public pages load without login prompts or permission errors.

### Public Showcase -- Hero and Stat Cards (Not Logged In)

![Public View -- Hero and Stats](screenshots/demo_showcase_hero.png)

*The showcase page as seen by a public (unauthenticated) visitor. Note the "Sign In" link visible in the top navigation bar, confirming the user is not logged in. Despite this, the hero banner renders fully and all four stat cards display their computed values correctly. This works because the snippet controllers use `sudo()` to read data and the route decorators include `auth='public'`, allowing anonymous access.*

### Public Showcase -- Dynamic Content Section (Not Logged In)

![Public View -- Dynamic Content](screenshots/demo_showcase_dynamic_content.png)

*The dynamic content section of the showcase page rendered for a public visitor. The contact cards display city, email, and company information without requiring authentication. The "Sign In" link in the navigation confirms the anonymous access context. This is essential for marketing sites, public dashboards, and customer-facing portals where the audience is not expected to have Odoo credentials.*

### Public Showcase -- Top Section

![Public View -- Top Section](screenshots/demo_showcase_top.png)

*The top section of the public showcase page showing the hero banner and the beginning of the stat cards section. This screenshot captures the initial viewport that a visitor sees before scrolling, confirming that above-the-fold content loads correctly without authentication.*

---

## 7. Backend Administration -- Module, Settings, and Filters

The module integrates with standard Odoo backend administration workflows. It appears in the Apps list for installation, creates `website.snippet.filter` records for dynamic content configuration, and adds its pages to the website's page management interface.

### Module Installation -- Odoo Apps

![Odoo Apps -- Module Installation](screenshots/apps_modules.png)

*The Odoo Apps/Modules page showing the WoOW Snippet Builder available for installation. The module's only dependency is `website`, making it lightweight to deploy. Installation creates the necessary QWeb templates, registers JavaScript assets, sets up controller routes, and seeds the initial snippet filter records. No additional Python dependencies or system packages are required.*

### Snippet Filter Records -- Backend Configuration

![Snippet Filters -- Backend List](screenshots/snippet_filters_list.png)

*The `website.snippet.filter` records created by the module, viewed in the Odoo backend. These records define the data source and display template for dynamic content snippets. Each filter specifies: the target model (e.g., `res.partner`), the number of records to fetch, the display template (e.g., card, list, grid), and any domain filters to apply. Pre-configured filters for Contacts and Companies ship with the module. Administrators can create custom filters for any of the 28 whitelisted models.*

### Website Backend Dashboard

![Website Backend Dashboard](screenshots/website_backend.png)

*The Odoo Website backend dashboard with the WoOW Snippet Builder module active. From this view, administrators can access the website editor, manage pages, configure snippets, and monitor website analytics. The module does not add its own top-level menu -- it integrates directly into the existing website workflow.*

### Website Pages List

![Website Pages](screenshots/website_pages.png)

*The website pages management view showing all pages that can contain WoOW snippets. The showcase and demo pages created by the module appear alongside any other site pages. Any existing or new page can use WoOW snippets: simply edit the page in the website editor and drag a snippet from the "WoOW Dynamic" category in the BLOCKS panel.*

### Website Frontend

![Website Frontend](screenshots/website_frontend.png)

*The website frontend homepage with the WoOW Snippet Builder module active. Snippets blend seamlessly with the site's existing theme and layout. The module's CSS uses scoped selectors to avoid conflicts with theme styles, and all JavaScript controllers are registered under the `woow_snippet` namespace to prevent collisions with other modules.*

---

## 8. API Endpoints -- JSON Responses

The module exposes two public JSON endpoints that power the editor's configuration panels. These endpoints are also useful for debugging, integration testing, and building external tools that interact with the snippet system.

### GET /woow_snippet/models -- Available Models

![API Response -- Models](screenshots/api_models.png)

*The JSON response from the `/woow_snippet/models` endpoint. It returns an array of 28 whitelisted model identifiers (e.g., `res.partner`, `res.company`, `sale.order`, `product.template`). The whitelist is defined in the Python controller and limits which Odoo models can be queried by snippets, preventing accidental exposure of sensitive models like `res.users` or `ir.config_parameter`. The editor's Model dropdown is populated directly from this response.*

### GET /woow_snippet/fields -- Field Metadata

![API Response -- Fields for res.partner](screenshots/api_fields_partner.png)

*The JSON response from `/woow_snippet/fields?model=res.partner`. Each entry contains three properties: `name` (the technical field name, e.g., `city`), `type` (the Odoo field type, e.g., `char`, `many2one`, `integer`), and `string` (the human-readable label, e.g., "City"). The editor uses this metadata to populate the Field, Label, and Group-By dropdowns with type-appropriate filtering -- for example, only `many2one` and selection fields appear in the Group-By dropdown since those are meaningful for aggregation. Relational fields show their related model name for clarity.*

---

## Appendix: Demo Page Screenshots

These additional screenshots capture the standalone demo page, which predates the showcase page and uses a simpler layout.

### Demo Page -- Top Section

![Demo Page Top](screenshots/snippet_demo_top.png)

*The top section of the original demo page. This page was the first integration test for the module and uses a more compact layout than the showcase page. It remains useful as a secondary validation that snippets render correctly on pages with different structures.*

### Demo Page -- Full View

![Demo Page Full](screenshots/snippet_demo_full.png)

*The complete demo page from top to bottom. Compared to the showcase page, the demo page uses fewer snippets and a narrower layout, confirming that snippets adapt to their container width rather than assuming a fixed page structure.*

---

*All screenshots were captured from a live Odoo 18 Community Edition instance running the WoOW Snippet Builder module with default `res.partner` demo data.*
