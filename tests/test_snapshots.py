from pathlib import Path

from market_briefing import snapshots
from conftest import SAMPLE


def test_reads_only_daily_snapshot_files():
    obs = snapshots.load(SAMPLE)
    assert {o.date for o in obs} == {"2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23"}
    assert len(obs) == 16


def test_parses_prices_and_category():
    o = next(o for o in snapshots.load(SAMPLE) if o.product_id == 1001 and o.date == "2026-02-02")
    assert o.buy_now == 189000 and o.option == "270" and o.category == "신발 > 스니커즈"


def test_snapshot_date_handles_nfd_filenames():
    import unicodedata
    name = unicodedata.normalize("NFD", "KREAM 2026-02-04 즐겨찾기 전체 데이터.xlsx")
    assert snapshots.snapshot_date(Path(name)) == "2026-02-04"
    assert snapshots.snapshot_date(Path("KREAM 2026-02-04 리리셀 정산 데이터.xlsx")) is None
