from market_briefing import documents
from market_briefing.snapshots import Observation


def obs(date, price):
    return Observation(date, 1, "270", "테스트 러닝화", "신발", price, None, None, 1.0)


def test_change_low_high_are_computed_in_code():
    d = documents.build([obs("2026-02-01", 100000), obs("2026-02-10", 125000), obs("2026-02-05", 90000)])[0]
    assert (d.first_price, d.last_price, d.change_pct) == (100000, 125000, 25.0)
    assert "최저가는 90,000원(2월 5일)" in d.text and "최고가는 125,000원(2월 10일)" in d.text


def test_series_with_one_observation_is_skipped():
    assert documents.build([obs("2026-02-01", 100000)]) == []


def test_top_movers_counts_falls_as_well_as_rises(sample_docs):
    names = [d.name for d in documents.top_movers(sample_docs, 2)]
    assert names == ["샘플 러닝화 에어 템포 블랙", "샘플 다운 패딩 오버핏 네이비"]  # +22.2%, -14.6%


def test_spoken_fact_uses_manwon_for_narration():
    d = documents.build([obs("2026-02-01", 2_830_000), obs("2026-02-05", 3_650_000)])[0]
    assert documents.spoken_fact(d) == "테스트 러닝화(270): 2월 1일 283만 원에서 2월 5일 365만 원으로 29.0% 올랐다."
    assert documents.manwon(465_000) == "46만 5천 원"


def test_topic_particle_follows_final_sound():
    assert documents.topic("한미반도체") == "한미반도체는"
    assert documents.topic("SK이노베이션") == "SK이노베이션은"
    assert documents.topic("셀린느 백(본품+더스트백)") == "셀린느 백(본품+더스트백)은"
    assert documents.topic("나이키(270)") == "나이키(270)은"
