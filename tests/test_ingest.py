from __future__ import annotations

import json


def test_manifest_counts(session_settings):
    manifest = json.loads(session_settings.manifest_path.read_text(encoding="utf-8"))
    assert manifest["stores"] == 6
    assert manifest["holidays"] == 15
    assert manifest["bus_stops"] == 41
    assert manifest["train_providers"] == 2
    assert manifest["menu_items"] >= 300
