from market_briefing import newscast, stocks

KOSPI = [("2026-09-01", 6835.80), ("2026-09-02", 6562.72), ("2026-10-08", 6625.93)]


def doc(code, name, a, b):
    return stocks.build(code, name, "KOSPI", [("2026-09-01", a, 1), ("2026-10-08", b, 1)])


def test_plan_orders_scenes_and_fixes_numbers_and_direction():
    scenes = newscast.plan([doc("042700", "한미반도체", 215000, 263000), doc("207940", "삼성바이오로직스", 1508000, 1220000)], KOSPI)
    assert [s.kind for s in scenes] == ["opening", "index", "stock", "stock", "closing"]
    assert scenes[1].narration == "이 기간 코스피 지수는 6,835.80에서 6,625.93으로 3.1% 내렸습니다."
    assert scenes[2].narration == "한미반도체는 21만 5천 원에서 26만 3천 원으로 22.3% 올랐습니다."
    assert "19.1% 내렸습니다" in scenes[3].narration


def test_scene_frame_is_drawn(tmp_path):
    scenes = newscast.plan([doc("042700", "한미반도체", 215000, 263000)], KOSPI)
    path = tmp_path / "f.png"
    newscast._draw(scenes[2], KOSPI, path, 2, len(scenes))
    assert path.stat().st_size > 20_000
