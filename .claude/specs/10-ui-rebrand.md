# Spec: UI rebrand — Spendly → MoneyTrail

## Overview
Refresh the Spendly UI as a single teaching step that touches every page but no backend logic. The product is renamed from **Spendly** to **MoneyTrail**, the color palette switches from forest/amber to a "Royal Blue + Gold" wealth-management palette, the landing page hero is rebuilt as a split layout with a royalty-free illustration on the left and the existing mock-dashboard on the right, and small copy/icon polish is added throughout so the rebrand reads coherently. This step is UI-only — no routes, no DB, no auth changes — so it can land in a single PR and remain easy to review.

## Depends on
- All previous steps (01–09) — the existing pages, routes, and CSS tokens must be in place. The rebrand edits on top of them.

## Routes
No new routes.

## Database changes
No database changes.

## Templates
- **Modify:**
  - `templates/base.html` — `<title>` default and footer brand text become "MoneyTrail"; the `◈` brand mark icon stays (it's generic).
  - `templates/landing.html` — page title, hero copy ("Track every rupee. / Know where it goes."), CTA copy, footer text. Hero is restructured from a single stacked column into a two-column split (illustration on the left, mock-window on the right). The "See how it works" video modal block, hero badge, and the features + CTA sections stay.
  - `templates/login.html` — page title and "Sign in to your Spendly account" copy.
  - `templates/register.html` — page title and "Start tracking your expenses today" copy.
  - `templates/profile.html` — "Hi, {name}" greeting stays as-is (first-name copy); the avatar background gradient is updated to use the new `--accent` and `--accent-2` palette; the "Top category" tile accent follows the new palette; the Chart.js category color map is updated to harmonise with the new accent.
  - `templates/dashboard.html` — page title and "You are signed in to Spendly" copy.
  - `templates/terms.html` and `templates/privacy.html` — top brand heading only. The body copy is finalized legal text (per `CLAUDE.md`) and must not be paraphrased; only the `<h1>` brand line and `<title>` change.
- **Create:** none.

## Files to change
- `static/css/style.css` — only the `:root` block changes (palette tokens) plus a small number of dependent rules. The `◈` brand mark, paper/ink neutrals, fonts, radii, and component layout are unchanged so the rest of the app keeps its structure. New token values:
  - `--accent: #1E3A8A` (royal blue)
  - `--accent-light: #DBEAFE`
  - `--accent-2: #B8860B` (dark goldenrod)
  - `--accent-2-light: #FEF3C7`
  - `--ink: #1F2937` (graphite — replaces near-black for a softer "wealth" feel)
  - `--ink-soft: #374151`
  - `--ink-muted: #6B7280`
  - `--ink-faint: #9CA3AF`
  - `--paper: #F9FAFB`
  - `--paper-warm: #F3F4F6`
  - `--paper-card: #FFFFFF`
  - `--border: #E5E7EB`
  - `--border-soft: #F3F4F6`
  - The `bar-fill--*` and `category-badge--*` category colors are retuned to harmonise with the new accent (less saturated, leaning blue/grey/amber), and the profile avatar's `linear-gradient(135deg, var(--accent), var(--accent-2))` continues to work.
- `static/img/hero.svg` — **new file**, downloaded from the Pexels royalty-free library (one of: woman-analyzing-financial-line graphic — [Pexels 6289065](https://www.pexels.com/photo/illustration-of-woman-analyzing-financial-line-graphic-6289065/)) and re-saved as SVG. Stored under `static/img/` so it is served by Flask at `/static/img/hero.svg`.
- `app.py` — no functional changes; only the page title and any literal "Spendly" string in `render_template` data (none today — titles are set in templates, not in the route) is left alone.
- All template files listed under "Templates → Modify".

## Files to create
- `static/img/hero.svg` — the hero illustration, ~800–1200px wide, optimized SVG (under 100 KB). Source: Pexels license, free for commercial and non-commercial use, attribution appreciated but not required. The file path `/static/img/hero.svg` is referenced from `landing.html` via `url_for('static', filename='img/hero.svg')`.

## New dependencies
No new dependencies. The hero image is a static asset, not a JS library.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only (unchanged — this step doesn't touch queries).
- Passwords hashed with `werkzeug` (unchanged).
- **Use CSS variables — never hardcode hex values.** Every new color in `style.css` and any inline `<style>` in `templates/` must reference `var(--accent)`, `var(--accent-2)`, etc. The category-color exceptions in `bar-fill--*` and `category-badge--*` are pre-existing; if those hex values are touched during the retune, they remain as one-off class-scoped tokens (not `--accent`).
- All templates continue to extend `base.html`. No template is rewritten from scratch.
- The `◈` brand glyph in `base.html` and `landing.html` is left as-is. It is a generic Unicode character, not a logo, and the spec does not introduce a logo file.
- The legal copy in `terms.html` and `terms.html` body is **not** paraphrased. Only the brand heading at the top and the `<title>` block change.
- The video modal in `landing.html` (deferred-load YouTube iframe with autoplay-on-open / clear-on-close) must keep working exactly as it does today. The hero restructure must not touch the modal markup or its script.
- The hero image must be saved to `static/img/hero.svg` and referenced via `url_for('static', filename='img/hero.svg')` — never as a relative path.
- The new palette must be visible across all five pages (landing, login, register, profile, dashboard), not just the landing page. Verify by reloading each page after the change.
- The Chart.js category color map in `profile.html` is updated to use the new retuned hex values for the seven categories (Food, Transport, Bills, Health, Entertainment, Shopping, Other). The values must match the `.bar-fill--*` and `.category-badge--*` classes in `style.css` so the donut chart and the breakdown table use the same color per category.
- Do not change any route, view function, or template variable name. This step is template + CSS + one static asset only.

## Definition of done
- [ ] `git status` on `feature/10-ui-rebrand` lists only the expected files (no accidental `expense_tracker.db`, `__pycache__/`, etc.).
- [ ] `python app.py` starts on port 5001 with no errors and no tracebacks in the terminal.
- [ ] Every page (`/`, `/login`, `/register`, `/profile`, `/dashboard`, `/terms`, `/privacy`) loads at HTTP 200.
- [ ] The brand string "MoneyTrail" appears in the navbar, footer, and `<title>` of every page. The string "Spendly" does not appear in any user-visible text (the literal `◈` glyph may stay; it is not a word).
- [ ] The new color tokens are present in `style.css` `:root`, and `var(--accent)`, `var(--accent-2)`, `var(--ink)`, and `var(--paper)` are referenced from at least one rule (proves the variables are wired in).
- [ ] The hero illustration loads on `/` (visually — open in a browser; the image is not broken or 404). The mock-window still renders to the right of the image on screens ≥ 900px and stacks above the image on smaller screens.
- [ ] The "See how it works" video modal still opens, plays, and closes correctly (autoplay-on-open, clears-on-close, escape key closes, click-outside closes).
- [ ] The profile page donut chart still renders with one color per category and the colors match the breakdown table bar fills.
- [ ] No new pip packages were added (`requirements.txt` is unchanged).
- [ ] No SQL or query string in `app.py` was modified (verified by `git diff main -- app.py` showing zero or comment-only changes).
- [ ] The legal body text in `terms.html` and `privacy.html` is byte-identical to `main` (`git diff main -- templates/terms.html templates/privacy.html` shows changes only in `<title>` and the brand heading).
