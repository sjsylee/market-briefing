"""문서 임베딩 색인과 근거 기반 질의응답."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import grounding, models
from .documents import PriceDocument

# bge-m3 기준, 관련 없는 질문(예: 데이터에 없는 종목)의 최고 유사도가 대체로 이 값 아래였다.
MIN_SCORE = 0.45
NO_ANSWER = "제공된 데이터로는 답할 수 없습니다."

ANSWER_PROMPT = (
    "너는 시세 데이터 안내원이다. 아래 [문서]에 적힌 내용만 근거로 한국어로 답한다. "
    "문서에 없는 숫자나 사실은 쓰지 않는다. 답할 수 없으면 '" + NO_ANSWER + "'라고만 쓴다. "
    "근거로 쓴 문장 끝에 문서 번호를 [1]처럼 붙인다."
)


class Index:
    def __init__(self, docs: list[dict], vectors: np.ndarray):
        self.docs = docs
        self.vectors = vectors

    @classmethod
    def build(cls, docs: list[PriceDocument], embedder: models.Embedder = models.embed, batch: int = 32) -> "Index":
        texts = [d.text for d in docs]
        vectors = np.concatenate([embedder(texts[i:i + batch]) for i in range(0, len(texts), batch)])
        return cls([d.to_dict() for d in docs], vectors)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "vectors.npy", self.vectors)
        (directory / "docs.json").write_text(json.dumps(self.docs, ensure_ascii=False))

    @classmethod
    def load(cls, directory: Path) -> "Index":
        return cls(json.loads((directory / "docs.json").read_text()), np.load(directory / "vectors.npy"))

    def search(self, query: str, k: int = 4, embedder: models.Embedder = models.embed) -> list[tuple[float, dict]]:
        scores = self.vectors @ embedder([query])[0]
        order = np.argsort(-scores)[:k]
        return [(float(scores[i]), self.docs[i]) for i in order]


@dataclass
class Answer:
    text: str
    sources: list[dict] = field(default_factory=list)
    grounded: bool = True
    ungrounded_numbers: list[str] = field(default_factory=list)


# "가장 많이 오른 셀린느 가방"처럼 순위를 묻는 질문. 유사도 검색은 상위 k개만 보므로
# 전체에서의 최댓값을 보장하지 못한다. 이런 질문은 모델 없이 전체 문서를 계산해 답한다.
_RANKING = re.compile(r"가장\s*(많이\s*)?(오른|상승|비싸진|내린|하락|떨어진)")
_STOPWORDS = {"가장", "많이", "오른", "상승", "내린", "하락", "떨어진", "비싸진", "가격", "시세", "알려줘", "상품", "뭐야", "어떤", "제품"}


def _strip_particle(word: str) -> str:
    return re.sub(r"(중에서|중에|에서|은|는|이|가|을|를|의)$", "", word)


def ranking_answer(question: str, docs: list[dict]) -> Answer | None:
    m = _RANKING.search(question)
    if not m:
        return None
    falling = m.group(2) in ("내린", "하락", "떨어진")
    words = [_strip_particle(w) for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", question)]
    words = [w for w in words if len(w) >= 2 and w not in _STOPWORDS]
    pool = [d for d in docs if any(w in d["name"] for w in words)] if words else docs
    if not pool:
        return Answer(NO_ANSWER)
    best = (min if falling else max)(pool, key=lambda d: d["change_pct"])
    text = (f"관측된 {len(pool)}개 상품 중 {'가장 많이 내린' if falling else '가장 많이 오른'} 것은 "
            f"{best['name']}({best['option']})로, 즉시 구매가가 {best['first_price']:,}원에서 "
            f"{best['last_price']:,}원으로 {best['change_pct']:+.1f}% 변했습니다. [1]")
    return Answer(text, [{"id": best["id"], "name": best["name"], "score": None}])


def ask(question: str, index: Index, k: int = 4,
        embedder: models.Embedder = models.embed, chat: models.Chat = models.chat) -> Answer:
    ranked = ranking_answer(question, index.docs)
    if ranked:
        return ranked

    hits = [(s, d) for s, d in index.search(question, k, embedder) if s >= MIN_SCORE]
    if not hits:
        # 관련 문서가 없으면 모델을 부르지 않는다. 그럴듯한 추측을 막는 가장 싼 방법이다.
        return Answer(NO_ANSWER)

    context = "\n".join(f"[{i}] {d['text']}" for i, (_, d) in enumerate(hits, 1))
    reply = chat(ANSWER_PROMPT, f"[문서]\n{context}\n\n[질문]\n{question}")
    bad = grounding.ungrounded(reply, [d["text"] for _, d in hits])
    sources = [{"id": d["id"], "name": d["name"], "score": round(s, 3)} for s, d in hits]
    if bad:
        return Answer("답변에 근거 문서와 맞지 않는 숫자가 있어 표시하지 않습니다.", sources, False, sorted(bad))
    return Answer(reply, sources)
