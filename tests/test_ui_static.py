from __future__ import annotations

from pathlib import Path


def test_static_hci_tokens_present():
    css = Path("camp_casey_app/web/static/app.css").read_text(encoding="utf-8")
    for token in [":focus-visible", ".tooltip-bubble", ".empty-state", ".skeleton", ".is-loading", ".interactive-card:hover", ".btn:active"]:
        assert token in css


def test_index_contains_accessibility_and_interaction_primitives(client):
    html = client.get("/").text
    assert '<main class="layout">' in html
    assert 'aria-live="polite"' in html
    assert 'data-currency-mode="usd_only"' in html
    assert 'tooltip-bubble' in html
    assert '<dialog id="store-dialog"' in html
