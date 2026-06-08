# Screenshots & Visual Guide

This document provides annotated screenshots demonstrating key features of the WoOW Snippet Builder module.

---

## Website Frontend

The module integrates seamlessly with the Odoo 18 website frontend.

![Website Frontend](screenshots/website_frontend.png)

*The website homepage with WoOW snippets rendering dynamic data from Odoo backend models.*

---

## Website Backend Dashboard

The website backend management view showing the snippet builder module is active.

![Website Backend](screenshots/website_backend.png)

*Access the website builder from Odoo backend → Website menu.*

---

## Module Installation

The WoOW Snippet Builder appears in the Odoo Apps/Modules list.

![Apps Modules](screenshots/apps_modules.png)

*Navigate to Settings → Apps to find and install WoOW Snippet Builder. The module depends only on the `website` module.*

---

## Snippet Filters

Dynamic Content snippets use `website.snippet.filter` records to define what data to display and how.

![Snippet Filters](screenshots/snippet_filters_list.png)

*The snippet filter records include pre-configured templates for Contacts and Companies. Custom filters can be added for any whitelisted model.*

---

## API: Models Endpoint

The `/woow_snippet/models` endpoint returns the list of 28 whitelisted models available for snippet queries.

![API Models](screenshots/api_models.png)

*Public endpoint returning available models. Used by the editor options panel to populate the Model dropdown.*

---

## API: Fields Endpoint

The `/woow_snippet/fields?model=res.partner` endpoint returns field definitions for a given model.

![API Fields](screenshots/api_fields_partner.png)

*Field metadata includes name, type, and string label. The editor uses this to populate Field, Label, and Value dropdowns with type-appropriate filtering.*

---

## Website Pages

The website pages list showing pages that can contain WoOW snippets.

![Website Pages](screenshots/website_pages.png)

*Any website page can contain WoOW snippets. Simply edit the page and drag a snippet from the BLOCKS panel.*

---

## Snippet Types Overview

### Stat Card
Displays aggregated metrics (count, sum, avg, min, max) with visual styles:
- **Default**: Simple number display with icon
- **Progress**: Circular or linear progress bar towards a target
- **Trend**: Shows change percentage vs. previous period
- **Threshold**: Color-coded alerts (green/yellow/red) based on configured thresholds

### Chart (Chart.js)
10 chart types with automatic data fetching:
- Bar, Line, Pie, Doughnut, Radar, Polar Area
- Horizontal Bar, Stacked Bar
- Gauge (custom), Funnel (custom)

### Data Table
Interactive paginated tables:
- Server-side pagination with configurable page size
- Column sorting (click header)
- Debounced search (300ms delay)
- XSS-safe rendering

### Dynamic Content
Extends native Odoo dynamic snippets:
- 6 QWeb display templates
- Generic field mapping (field_0, field_1, field_2, image)
- Context-aware filtering (page context or URL parameters)

---

## Editor Integration

All snippets are configured entirely within the Odoo 18 website editor:

1. **BLOCKS Panel** — Drag & drop snippets from the "WoOW Dynamic" category
2. **CUSTOMIZE Panel** — Configure data source, styling, and behavior without code

The editor panels dynamically populate dropdowns via RPC calls to the controller endpoints, ensuring only valid models and fields are selectable.
