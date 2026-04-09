from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from camp_casey_app.config import get_settings
from camp_casey_app.ingest.normalize import run_full_ingest, ensure_exchange_rate_seed


def main() -> None:
    settings = get_settings()
    manifest = run_full_ingest(settings)
    ensure_exchange_rate_seed(settings)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
