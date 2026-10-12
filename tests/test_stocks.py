from market_briefing import documents, media, stocks

ROWS = [("2026-09-01", 70000, 1_000_000), ("2026-09-02", 68000, 1_200_000), ("2026-09-03", 77000, 2_500_000)]


def test_stock_document_is_computed_from_closes():
    d = stocks.build("005930", "테스트전자", "KOSPI", ROWS)
    assert (d.kind, d.first_price, d.last_price, d.change_pct) == ("stock", 70000, 77000, 10.0)
    assert "3거래일 동안 종가는" in d.text and "최저 종가는 68,000원(9월 2일)" in d.text


def test_spoken_fact_does_not_read_ticker_aloud():
    d = stocks.build("005930", "테스트전자", "KOSPI", ROWS)
    assert documents.spoken_fact(d).startswith("테스트전자: 9월 1일 7만 원에서 9월 3일 7만 7천 원으로 10.0% 올랐다")


def test_stock_script_uses_stock_labels():
    d = stocks.build("005930", "테스트전자", "KOSPI", ROWS)
    assert "국내 주식 종가 기준으로 변동이 컸던 종목 1개" in media.compose_script([d])
