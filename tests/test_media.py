import pytest

from market_briefing import documents, media


def test_script_is_retried_until_numbers_are_grounded(sample_docs):
    movers = documents.top_movers(sample_docs, 1)
    replies = iter(["3월에는 26만 원이 됩니다", "2월 23일 23만 1천 원으로 22.2% 올랐습니다"])
    assert "23만 1천 원" in media.write_script(movers, chat=lambda s, u: next(replies))


def test_script_is_rejected_when_model_keeps_inventing(sample_docs):
    movers = documents.top_movers(sample_docs, 1)
    with pytest.raises(media.ScriptRejected):
        media.write_script(movers, chat=lambda s, u: "999,000원 돌파", attempts=2)


def test_chart_is_written(tmp_path, sample_docs):
    path = tmp_path / "chart.png"
    media.draw_chart(documents.top_movers(sample_docs, 3), path)
    assert path.stat().st_size > 10_000


def test_composed_script_keeps_direction_and_numbers(sample_docs):
    movers = documents.top_movers(sample_docs, 2)
    script = media.compose_script(movers)
    assert "23만 1천 원으로 22.2% 올랐습니다" in script and "35만 2천 원으로 14.6% 내렸습니다" in script
    assert media.grounding.ungrounded(script, [documents.spoken_fact(d) for d in movers]) == set()
