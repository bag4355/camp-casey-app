from __future__ import annotations

from pathlib import Path
import shutil

from camp_casey_app.config import Settings
from camp_casey_app.ingest.normalize import ensure_exchange_rate_seed, run_full_ingest


def _seed_dir(source_dir: Path, target_dir: Path) -> None:
    """Bundle 내 source_dir의 파일을 target_dir로 복사 (존재하지 않는 파일만)."""
    if not source_dir.exists():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in source_dir.iterdir():
        target = target_dir / source.name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)


def ensure_data_ready(settings: Settings) -> None:
    # 번들된 raw / normalized / rag 파일을 DATA_ROOT로 시딩한다.
    # Render 등 외부 볼륨 환경의 첫 부팅에서 빈 디렉터리를 채워 준다.
    _seed_dir(settings.bundled_data_dir / "raw", settings.raw_data_dir)
    _seed_dir(settings.bundled_data_dir / "normalized", settings.normalized_data_dir)
    _seed_dir(settings.bundled_data_dir / "rag", settings.rag_dir)

    settings.normalized_data_dir.mkdir(parents=True, exist_ok=True)
    settings.rag_dir.mkdir(parents=True, exist_ok=True)
    settings.state_dir.mkdir(parents=True, exist_ok=True)

    required = [
        settings.stores_path,
        settings.holidays_path,
        settings.bus_path,
        settings.trains_path,
        settings.rag_chunks_path,
        settings.rag_index_path,
    ]
    if not all(path.exists() for path in required):
        run_full_ingest(settings)

    ensure_exchange_rate_seed(settings)
