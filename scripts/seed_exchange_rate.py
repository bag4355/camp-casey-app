from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from camp_casey_app.config import get_settings
from camp_casey_app.ingest.normalize import ensure_exchange_rate_seed
from camp_casey_app.repositories.exchange_rate_store import ExchangeRateFileStore
from camp_casey_app.services.exchange_rate import ExchangeRateService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=None, help="USD -> KRW rate")
    args = parser.parse_args()

    settings = get_settings()
    ensure_exchange_rate_seed(settings)
    service = ExchangeRateService(ExchangeRateFileStore(settings.exchange_rate_path), settings.timezone)
    if args.rate is not None:
        snapshot = service.set_manual_exchange_rate(args.rate, note="Seed script update")
        print(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    snapshot = service.get_active_exchange_rate()
    print(json.dumps(snapshot.model_dump(mode="json") if snapshot else {}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
