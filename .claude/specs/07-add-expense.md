---
# Spec: Add Expense

## Overview
The Add Expense feature allows logged-in users to create new expense records. Users enter an amount, select a category from a predefined list, pick a date (defaulting to today), and optionally add a description. On successful submission, the expense is saved to the database and the user is redirected to their profile page.

## Depends on
- Step 03: Login and Logout (for authentication)
- Step 04: Profile Page Design (for displaying expenses)

## Routes
- `GET /expenses/add` — Add expense form — logged-in only
- `POST /expenses/add` — Process expense creation — logged-in only

## Database changes
No database changes. The `expenses` table already exists with all required columns:
- `id` (INTEGER PRIMARY KEY)
- `user_id` (INTEGER NOT NULL, FK to users)
- `amount` (REAL NOT NULL)
- `category` (TEXT NOT NULL)
- `date` (TEXT NOT NULL, YYYY-MM-DD)
- `description` (TEXT)
- `created_at` (TEXT DEFAULT datetime('now'))

## Templates
- **Create:** `templates/expenses/add.html` — Form with fields for amount, category dropdown, date picker, and optional description
- **Modify:** `templates/profile.html` — Add a link/button to navigate to `/expenses/add`

## Files to change
- `app.py` — Implement GET and POST handlers for `/expenses/add`
- `templates/profile.html` — Add "Add Expense" button/link in the expenses section

## Files to create
- `templates/expenses/add.html` — New template for the add expense form

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate: amount must be positive number, category must be from the predefined list, date must be valid YYYY-MM-DD
- Pre-populate the date field with today's date (ISO format)
- Categories from `database/db.py` CATEGORIES tuple

## Definition of done
- [ ] GET /expenses/add renders a form with amount, category dropdown, date input, and description
- [ ] Category dropdown shows all 7 categories from database/db.py
- [ ] Date input defaults to today's date
- [ ] POST /expenses/add with valid data creates a new expense and redirects to /profile
- [ ] POST /expenses/add with invalid data re-renders the form with an error message
- [ ] Unauthenticated access to /expenses/add redirects to /login
- [ ] Profile page has a visible "Add Expense" button that links to /expenses/add
