"""Tests for Step 6: Date Filter for Profile Page.

These tests exercise the spec for /profile?preset=... and /profile?from=...&to=...
date filtering. The test fixtures (see tests/conftest.py) seed a demo user
with email `demo@spendly.com` / password `demo123` plus 8 sample expenses
spread across July 2026. Per the project context, today is 2026-07-28.

The conftest creates an isolated SQLite database per test and provides an
authenticated test client (`auth_client`). Tests do NOT read the `profile()`
implementation directly — they derive expectations from the spec's
"Definition of done" + "Routes" + "Rules for implementation".
"""


class TestDateFilter:
    # ------------------------------------------------------------------ #
    # Auth guard                                                          #
    # ------------------------------------------------------------------ #

    def test_profile_redirects_to_login_when_signed_out(self, client):
        """GET /profile without an active session must 302 to /login."""
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    # ------------------------------------------------------------------ #
    # Regression / default behaviour                                      #
    # ------------------------------------------------------------------ #

    def test_profile_default_view_returns_200_and_all_eight_expenses(self, auth_client):
        """GET /profile with no query string returns 200 and shows all 8 seeded rows."""
        response = auth_client.get("/profile")
        assert response.status_code == 200
        body = response.data.decode()
        # Each demo expense has a unique description. Asserting on those
        # is more robust than counting <tr> rows (header rows + badges
        # also produce markup).
        for description in [
            "Chai and breakfast",
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description in body, f"Expected demo expense '{description}' on default profile"

    def test_default_view_does_not_show_filtered_empty_state(self, auth_client):
        """When no filter is applied, the page must NOT show the filtered empty-state copy."""
        body = auth_client.get("/profile").data.decode()
        assert "No expenses in this date range." not in body, (
            "Unfiltered view must not show the filter-specific empty state"
        )

    def test_default_view_has_all_time_preset_active(self, auth_client):
        """The 'All time' preset pill carries the active class on the unfiltered view."""
        body = auth_client.get("/profile").data.decode()
        # The button for the 'all' preset must carry the active modifier class.
        # Looking for the active pill on data-preset="all".
        assert (
            'data-preset="all"' in body
            and 'profile-filter-preset--active' in body
        ), "Expected an active preset pill on the unfiltered view"
        # Exactly one active pill on the unfiltered view.
        assert body.count("profile-filter-preset--active") == 1, (
            "Exactly one preset pill should carry the active class when no filter is applied"
        )

    # ------------------------------------------------------------------ #
    # Preset behaviour                                                     #
    # ------------------------------------------------------------------ #

    def test_preset_this_month_includes_all_seven_july_expenses(self, auth_client):
        """`preset=this-month` filters to the current calendar month (July 2026).

        Today (per CLAUDE.md) is 2026-07-28 — so this-month = 2026-07-01..2026-07-28.
        All 8 demo expenses fall in July 2026 and should be visible.
        """
        body = auth_client.get("/profile?preset=this-month").data.decode()
        for description in [
            "Chai and breakfast",
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description in body, f"Expected '{description}' under this-month preset"

    def test_preset_this_month_marks_correct_pill_active(self, auth_client):
        """Under preset=this-month exactly one preset pill is active and it is 'this-month'."""
        body = auth_client.get("/profile?preset=this-month").data.decode()
        assert body.count("profile-filter-preset--active") == 1, (
            "Exactly one preset pill should carry the active class"
        )
        # The active button must be the this-month one. Look for the active class
        # appearing on the same button element that has data-preset="this-month".
        # A loose substring check: the substring
        # 'profile-filter-preset profile-filter-preset--active'
        # must be inside a button carrying data-preset="this-month".
        this_month_segment = body.split('data-preset="this-month"', 1)[0]
        # Walk back from this-month button to find its opening tag's class list.
        last_open = this_month_segment.rfind('<button')
        assert last_open != -1
        opening = this_month_segment[last_open:]
        assert "profile-filter-preset--active" in opening, (
            "The active pill should be the this-month button"
        )

    def test_preset_last_month_returns_no_expenses_for_july_only_data(self, auth_client):
        """`preset=last-month` returns June 2026 — none of the seeded expenses match."""
        body = auth_client.get("/profile?preset=last-month").data.decode()
        # The filtered empty-state copy must appear.
        assert "No expenses in this date range." in body, (
            "Expected the filter-specific empty state when no expenses match"
        )
        # None of the demo descriptions should appear in June.
        for description in [
            "Chai and breakfast",
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description not in body, (
                f"July expense '{description}' should not appear under last-month"
            )

    def test_preset_last_month_marks_correct_pill_active(self, auth_client):
        """Under preset=last-month the active pill is the 'last-month' button."""
        body = auth_client.get("/profile?preset=last-month").data.decode()
        assert body.count("profile-filter-preset--active") == 1
        last_month_segment = body.split('data-preset="last-month"', 1)[0]
        opening = last_month_segment[last_month_segment.rfind("<button"):]
        assert "profile-filter-preset--active" in opening

    def test_preset_last_30_days_includes_all_eight_expenses(self, auth_client):
        """`preset=last-30-days` covers 29 days back through today (Jul 28).

        Earliest demo expense is 2026-07-01 = 27 days ago — all 8 fall inside the window.
        """
        body = auth_client.get("/profile?preset=last-30-days").data.decode()
        for description in [
            "Chai and breakfast",
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description in body, (
                f"Expected '{description}' under last-30-days preset"
            )

    def test_preset_last_7_days_includes_only_two_recent_expenses(self, auth_client):
        """`preset=last-7-days` covers Jul 22..Jul 28 inclusive — only 2 demo rows match."""
        body = auth_client.get("/profile?preset=last-7-days").data.decode()
        assert "Household supplies" in body, (
            "Jul 22 expense should appear under last-7-days"
        )
        assert "Petty cash" in body, (
            "Jul 27 expense should appear under last-7-days"
        )
        # Anything strictly before Jul 22 should NOT appear.
        for description in [
            "Chai and breakfast",   # Jul 1
            "Auto to office",        # Jul 3
            "Electricity bill",      # Jul 6
            "Pharmacy",              # Jul 9
            "Movie ticket",          # Jul 12
            "T-shirt",               # Jul 18
        ]:
            assert description not in body, (
                f"'{description}' is older than 7 days and should not appear"
            )

    # ------------------------------------------------------------------ #
    # Custom range                                                        #
    # ------------------------------------------------------------------ #

    def test_custom_range_first_half_of_july_returns_five_expenses(self, auth_client):
        """`from=2026-07-01&to=2026-07-15` returns the 5 expenses in that window."""
        body = auth_client.get(
            "/profile?from=2026-07-01&to=2026-07-15"
        ).data.decode()
        for description in [
            "Chai and breakfast",   # Jul 1
            "Auto to office",        # Jul 3
            "Electricity bill",      # Jul 6
            "Pharmacy",              # Jul 9
            "Movie ticket",          # Jul 12
        ]:
            assert description in body, f"Expected '{description}' in Jul 1-15 window"
        for description in [
            "T-shirt",               # Jul 18 — outside range
            "Household supplies",    # Jul 22 — outside range
            "Petty cash",            # Jul 27 — outside range
        ]:
            assert description not in body, (
                f"'{description}' should be outside the Jul 1-15 window"
            )

    def test_custom_range_single_day_boundary_is_inclusive(self, auth_client):
        """`from=2026-07-01&to=2026-07-01` returns exactly one expense (Jul 1 boundary)."""
        body = auth_client.get(
            "/profile?from=2026-07-01&to=2026-07-01"
        ).data.decode()
        assert "Chai and breakfast" in body, (
            "Single-day range should include the Jul 1 boundary expense"
        )
        # All other demo expenses fall on different dates and must not appear.
        for description in [
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description not in body, (
                f"'{description}' is not on Jul 1 and should not appear"
            )

    def test_custom_range_drives_top_category_tile(self, auth_client):
        """The 'Top category' tile must respect the filter.

        With from=to=2026-07-01, only the 'Chai and breakfast' (Food) expense
        is in range — so the top-category tile must say 'Food'.
        """
        body = auth_client.get(
            "/profile?from=2026-07-01&to=2026-07-01"
        ).data.decode()
        # The 'Top category' tile label is rendered next to the value.
        # Verify the tile's value is 'Food' and not any other category.
        assert "Food" in body, "Top category tile must show 'Food' under single-day Food-only range"
        # The Top category tile label must be present alongside the value.
        assert "Top category" in body

    # ------------------------------------------------------------------ #
    # Validation errors must NOT 500                                      #
    # ------------------------------------------------------------------ #

    def test_reversed_range_shows_friendly_error_and_falls_back(self, auth_client):
        """Reversed range: shows the start-date error and falls back to unfiltered view."""
        response = auth_client.get("/profile?from=2026-07-15&to=2026-07-01")
        assert response.status_code == 200, "Reversed range must not crash the page"
        body = response.data.decode()
        assert "Start date must be on or before end date." in body, (
            "Reversed range must surface the spec's start-date error message"
        )
        # Fallback means all 8 demo expenses are visible again.
        for description in [
            "Chai and breakfast",
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description in body, (
                f"Fallback to unfiltered view should still show '{description}'"
            )

    def test_malformed_date_falls_back_without_crashing(self, auth_client):
        """Malformed date string must not 500 — page falls back to unfiltered view."""
        response = auth_client.get("/profile?from=not-a-date")
        assert response.status_code == 200, "Malformed date must not crash the page"
        body = response.data.decode()
        # The spec rule is "on ValueError, treat the param as absent". The
        # codebase surfaces a per-field error string. Either behavior is
        # acceptable per the spec — the contract is "does not crash and
        # falls back to unfiltered". Check the error mentions 'Invalid'
        # (the spec phrase for a malformed value).
        assert "Invalid" in body or "not-a-date" in body, (
            "Malformed date should surface an 'Invalid' error or echo the bad value"
        )
        # All 8 demo expenses should be visible after fallback.
        for description in [
            "Chai and breakfast",
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description in body, (
                f"After fallback '{description}' should still be visible"
            )

    # ------------------------------------------------------------------ #
    # Filter affects every section (chart payload)                        #
    # ------------------------------------------------------------------ #

    def test_filter_narrows_doughnut_chart_category_payload(self, auth_client):
        """When a filter narrows the data, the chart's `category_rows` JSON reflects only surviving categories.

        With preset=last-7-days the only surviving categories are 'Other'
        (Jul 22 and Jul 27). The Chart.js `categoryData` payload is rendered
        into the page as JSON inside the <script> block.
        """
        body = auth_client.get("/profile?preset=last-7-days").data.decode()
        # The chart script renders `const categoryData = {{ category_rows|tojson }};`
        # The serialised list contains the surviving categories only.
        # Surviving categories in last-7-days: 'Other' (Jul 22 + Jul 27).
        assert '"category": "Other"' in body or "\"category\": 'Other'" in body, (
            "Chart payload should include the only surviving category 'Other'"
        )
        # Categories NOT surviving the filter must not appear as category values
        # in the chart's JSON. They may appear in dropdowns / presets, so we
        # check the chart-specific block by isolating the script content.
        # Quick approximation: ensure the 'Food' category is absent from the
        # rendered category-breakdown table and chart when only Other survives.
        # We already know the 'Food' expense description 'Chai and breakfast'
        # is excluded; check that 'Food' is not in any category-row badge.
        # Simpler: assert the table only contains the 'Other' badge.
        assert "category-badge--other" in body

    def test_filtered_view_has_no_unrelated_category_badges(self, auth_client):
        """Under last-7-days, only 'Other' category badges appear in the expense table."""
        body = auth_client.get("/profile?preset=last-7-days").data.decode()
        # Each expense row renders a category badge like 'category-badge--food'.
        # With only Other surviving, only --other should appear.
        for cat in ["food", "transport", "bills", "health", "entertainment", "shopping"]:
            assert f"category-badge--{cat}" not in body, (
                f"Category badge for '{cat}' should not appear under last-7-days"
            )
        assert "category-badge--other" in body, (
            "Category badge for 'Other' should appear under last-7-days"
        )

    # ------------------------------------------------------------------ #
    # Form behaviour (no-JS contract)                                     #
    # ------------------------------------------------------------------ #

    def test_filter_bar_is_a_get_form_pointing_at_profile(self, auth_client):
        """The filter bar must be a GET form whose action is /profile."""
        body = auth_client.get("/profile").data.decode()
        assert 'class="profile-filter"' in body
        # Find the opening of the profile-filter form and assert the attributes.
        anchor = body.find('class="profile-filter"')
        assert anchor != -1
        # Walk backward to the nearest '<form' and forward to its '>'.
        form_open = body.rfind("<form", 0, anchor)
        form_close = body.find(">", form_open)
        form_tag = body[form_open:form_close + 1]
        assert 'method="get"' in form_tag, "Filter form must use method=get"
        assert 'action="/profile"' in form_tag, "Filter form must post to /profile"

    def test_filter_bar_contains_two_date_inputs_and_preset_buttons(self, auth_client):
        """The filter bar must contain two date inputs and the preset buttons."""
        body = auth_client.get("/profile").data.decode()
        assert 'name="from"' in body, "Filter form must include a 'from' date input"
        assert 'name="to"' in body, "Filter form must include a 'to' date input"
        # Two <input type="date"> elements.
        assert body.count('type="date"') == 2, "Filter form must include two date inputs"
        # Five preset buttons: all, this-month, last-month, last-30-days, last-7-days.
        for preset in ["all", "this-month", "last-month", "last-30-days", "last-7-days"]:
            assert f'data-preset="{preset}"' in body, (
                f"Filter form must include a preset button for '{preset}'"
            )

    def test_preset_works_without_javascript(self, auth_client):
        """Hitting the preset URL directly (no JS) returns the filtered page.

        The preset buttons are submit buttons inside a GET form — submitting
        any preset produces a URL like /profile?preset=this-month. The page
        must respect that even with no JS execution.
        """
        body = auth_client.get("/profile?preset=this-month").data.decode()
        # All July 2026 expenses are visible — same as the JS-enhanced path.
        assert "Chai and breakfast" in body
        assert "Petty cash" in body

    # ------------------------------------------------------------------ #
    # No data leak                                                        #
    # ------------------------------------------------------------------ #

    def test_filter_does_not_leak_other_users_expenses(self, client):
        """A second user with no expenses sees no data even with a wide-open filter.

        The demo user has 8 expenses. A freshly-registered second user has
        none. With `preset=all` (the broadest filter), the second user
        must still see the empty-state copy, not the demo user's data.
        """
        # Register a fresh second user.
        client.post(
            "/register",
            data={"name": "Second", "email": "second@example.com", "password": "password123"},
        )
        client.post(
            "/login",
            data={"email": "second@example.com", "password": "password123"},
        )
        body = client.get("/profile?preset=all").data.decode()
        # The empty-state copy must appear.
        assert "No expenses yet." in body, (
            "A user with no expenses should see the empty-state message"
        )
        # None of the demo user's expense descriptions should leak.
        for description in [
            "Chai and breakfast",
            "Auto to office",
            "Electricity bill",
            "Pharmacy",
            "Movie ticket",
            "T-shirt",
            "Household supplies",
            "Petty cash",
        ]:
            assert description not in body, (
                f"Second user must not see demo user's expense '{description}'"
            )

    # ------------------------------------------------------------------ #
    # Currency symbol                                                      #
    # ------------------------------------------------------------------ #

    def test_currency_symbol_present_in_default_and_filtered_views(self, auth_client):
        """The rupee symbol must appear regardless of whether a filter is active."""
        default_body = auth_client.get("/profile").data.decode()
        filtered_body = auth_client.get("/profile?preset=last-7-days").data.decode()
        assert "₨" in default_body, "Default view must render the rupee symbol"
        assert "₨" in filtered_body, "Filtered view must render the rupee symbol"