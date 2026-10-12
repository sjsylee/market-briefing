"""국내 주식 일별 시세를 같은 문서·검색·브리핑 흐름에 태운다.

데이터는 FinanceDataReader로 받는다(무료, API 키 불필요). KREAM 스냅샷과 달리
거래일마다 값이 있으므로, 관측 기간과 거래일 수를 문서에 함께 적는다.
"""

from __future__ import annotations

from .documents import PriceDocument, korean_date, won


def fetch(start: str, end: str, top: int = 30, market: str = "KOSPI") -> list[PriceDocument]:
    """시가총액 상위 `top`개 종목의 종가 시계열을 문서로 만든다."""
    import FinanceDataReader as fdr

    listing = fdr.StockListing(market)
    if "Marcap" in listing.columns:
        listing = listing.sort_values("Marcap", ascending=False)
    docs = []
    for code, name in listing[["Code", "Name"]].head(top).itertuples(index=False):
        prices = fdr.DataReader(code, start, end)
        if len(prices) < 2:
            continue
        rows = [(d.strftime("%Y-%m-%d"), int(r.Close), int(r.Volume)) for d, r in prices.iterrows()]
        docs.append(build(code, name, market, rows))
    return docs


def build(code: str, name: str, market: str, rows: list[tuple[str, int, int]]) -> PriceDocument:
    """rows: (날짜, 종가, 거래량) 오름차순."""
    first, last = rows[0], rows[-1]
    low = min(rows, key=lambda r: r[1])
    high = max(rows, key=lambda r: r[1])
    change = round((last[1] - first[1]) / first[1] * 100, 1)
    text = (
        f"{name}({code}), {market} 상장 종목. "
        f"{korean_date(first[0])}부터 {korean_date(last[0])}까지 {len(rows)}거래일 동안 종가는 "
        f"{won(first[1])}에서 {won(last[1])}으로 {change:+.1f}% 변했다. "
        f"기간 최저 종가는 {won(low[1])}({korean_date(low[0])}), 최고 종가는 {won(high[1])}({korean_date(high[0])})다. "
        f"마지막 거래일 거래량은 {last[2]:,}주다."
    )
    return PriceDocument(
        id=f"stock:{code}", name=name, option=code, category=market,
        first_date=first[0], last_date=last[0], first_price=first[1], last_price=last[1],
        change_pct=change, points=[(d, c) for d, c, _ in rows], text=text, kind="stock",
    )
