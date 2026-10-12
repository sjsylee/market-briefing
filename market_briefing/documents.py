"""관측 행을 상품·옵션별 시계열로 묶고, 검색과 원고 작성에 쓸 요약 문서를 만든다.

변동률·최저·최고가 같은 숫자는 전부 여기서 계산한다. 이후 단계의 모델은
이 문서에 적힌 숫자를 옮겨 쓰기만 하고, 새 숫자를 만들면 grounding 단계에서 걸러진다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .snapshots import Observation

# 데이터 출처별 표기. 문서·원고·차트·순위 답변이 같은 이름을 쓰도록 한곳에 둔다.
SOURCES = {
    "kream": {"label": "KREAM", "price": "즉시 구매가", "unit": "상품"},
    "stock": {"label": "국내 주식", "price": "종가", "unit": "종목"},
}


@dataclass
class PriceDocument:
    id: str  # "<product_id>:<option>"
    name: str
    option: str
    category: str
    first_date: str
    last_date: str
    first_price: int
    last_price: int
    change_pct: float
    points: list[tuple[str, int]]  # (date, 가격)
    text: str
    kind: str = "kream"

    def to_dict(self) -> dict:
        return asdict(self)


def korean_date(iso: str) -> str:
    """'2026-02-04' -> '2월 4일'. 낭독(TTS)과 숫자 대조 모두 이 형식을 기준으로 한다."""
    _, m, d = iso.split("-")
    return f"{int(m)}월 {int(d)}일"


def manwon(v: int) -> str:
    """낭독용 금액 표기. 2,830,000 -> '283만 원', 465,000 -> '46만 5천 원'."""
    man, rest = divmod(v, 10_000)
    cheon = rest // 1_000
    if man == 0:
        return f"{v:,}원"
    return f"{man:,}만 {cheon}천 원" if cheon else f"{man:,}만 원"


def spoken_fact(d: "PriceDocument") -> str:
    """브리핑 원고에 그대로 옮겨 쓸 수 있도록 낭독 표기로 정리한 한 줄 사실."""
    # 종목코드는 소리 내어 읽을 이유가 없어 주식은 이름만 쓴다.
    subject = d.name if d.kind == "stock" else f"{d.name}({d.option})"
    return (
        f"{subject}: {korean_date(d.first_date)} {manwon(d.first_price)}에서 "
        f"{korean_date(d.last_date)} {manwon(d.last_price)}으로 {abs(d.change_pct):.1f}% {'올랐다' if d.change_pct >= 0 else '내렸다'}."
    )


_DIGIT_HAS_BATCHIM = {"0": True, "1": True, "2": False, "3": True, "4": False, "5": False, "6": True, "7": True, "8": True, "9": False}


def topic(word: str) -> str:
    """주제 조사 은/는을 붙인다. 마지막 한글 음절의 받침(숫자는 읽는 소리)을 기준으로 한다."""
    for ch in reversed(word):
        if "가" <= ch <= "힣":
            return word + ("은" if (ord(ch) - 0xAC00) % 28 else "는")
        if ch.isdigit():
            return word + ("은" if _DIGIT_HAS_BATCHIM[ch] else "는")
        if ch.isalpha():
            return word + "는"
    return word + "은"


def won(v: int | None) -> str:
    return f"{v:,}원" if v is not None else "정보 없음"


def build(observations: list[Observation], min_points: int = 2) -> list[PriceDocument]:
    series: dict[tuple[int, str], list[Observation]] = {}
    for o in observations:
        series.setdefault((o.product_id, o.option), []).append(o)

    docs = []
    for (pid, option), obs in series.items():
        priced = sorted((o for o in obs if o.buy_now), key=lambda o: o.date)
        if len(priced) < min_points:
            continue
        docs.append(_document(pid, option, priced))
    return docs


def _document(pid: int, option: str, priced: list[Observation]) -> PriceDocument:
    first, last = priced[0], priced[-1]
    low = min(priced, key=lambda o: o.buy_now)
    high = max(priced, key=lambda o: o.buy_now)
    change = round((last.buy_now - first.buy_now) / first.buy_now * 100, 1)
    turnover = "정보 없음" if last.daily_turnover is None else f"{last.daily_turnover}"

    text = (
        f"{last.name} ({option}), 카테고리 {last.category}. "
        f"{korean_date(first.date)}부터 {korean_date(last.date)}까지 {len(priced)}번 관측한 즉시 구매가는 "
        f"{won(first.buy_now)}에서 {won(last.buy_now)}으로 {change:+.1f}% 변했다. "
        f"관측 기간 최저가는 {won(low.buy_now)}({korean_date(low.date)}), 최고가는 {won(high.buy_now)}({korean_date(high.date)})다. "
        f"마지막 관측일 기준 즉시 판매가는 {won(last.sell_now)}, 최근 5거래 평균 체결가는 {won(last.avg_sale_5)}, "
        f"일판 회전율은 {turnover}다."
    )
    return PriceDocument(
        id=f"{pid}:{option}", name=last.name, option=option, category=last.category,
        first_date=first.date, last_date=last.date, first_price=first.buy_now, last_price=last.buy_now,
        change_pct=change, points=[(o.date, o.buy_now) for o in priced], text=text,
    )


def top_movers(docs: list[PriceDocument], n: int = 3) -> list[PriceDocument]:
    """기간 변동률의 절댓값이 큰 순서. 오른 것과 내린 것을 함께 본다."""
    return sorted(docs, key=lambda d: abs(d.change_pct), reverse=True)[:n]
