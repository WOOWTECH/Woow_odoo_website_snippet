/** @odoo-module */
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";

/**
 * The Stat Card, Chart and Data Table data routes require a logged-in user
 * (auth='user').  Anonymous website visitors would only get a
 * "session expired" JSON error, so the widgets do not call the routes for
 * them and show a neutral sign-in notice instead of an error.
 */

const SESSION_EXPIRED = "odoo.http.SessionExpiredException";

/** True for the website's public (anonymous) user. */
export function isAnonymousVisitor() {
    return Boolean(session && session.is_website_user);
}

/** True when an RPC error means "you must be logged in". */
export function isLoginRequiredError(err) {
    if (!err) {
        return false;
    }
    const name = (err.data && err.data.name) || err.exceptionName;
    return name === SESSION_EXPIRED || err.code === 100;
}

/**
 * Replace the content of ``el`` with a muted sign-in notice.  Built with
 * DOM APIs only (no HTML parsing of any value).
 *
 * @param {HTMLElement} el
 * @param {string} iconClass e.g. 'fa-bar-chart'
 */
export function renderLoginRequired(el, iconClass) {
    if (!el) {
        return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "woow_login_required text-center text-muted py-4";
    const icon = document.createElement("i");
    icon.className = `fa ${iconClass || "fa-lock"} fa-2x mb-2 d-block opacity-50`;
    const text = document.createElement("small");
    text.className = "d-block";
    text.textContent = _t("Sign in to view this content.");
    const link = document.createElement("a");
    link.className = "small";
    const redirect = window.location.pathname + window.location.search;
    link.href = `/web/login?redirect=${encodeURIComponent(redirect)}`;
    link.textContent = _t("Sign in");
    wrapper.append(icon, text, link);
    el.replaceChildren(wrapper);
}
