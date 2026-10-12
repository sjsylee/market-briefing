"""Function Calling 에이전트.

`retrieval.ask`는 정규식으로 질문 종류를 나누지만, 여기서는 로컬 LLM이 도구를 고르고
인자를 채운다. 모델이 고른 도구 이름과 인자는 코드가 스키마로 검증한 뒤에만 실행하고,
최종 답변의 숫자는 도구 결과와 대조한다. 모델이 실행 경로를 정하되, 숫자와 권한은 코드가 쥔다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

import requests

from . import grounding, models, retrieval
from .documents import SOURCES

SYSTEM = (
    "너는 시세 데이터 안내원이다. 질문에 답하려면 반드시 도구를 호출해 데이터를 확인한다. "
    "순위(가장 많이 오른/내린)는 rank_movers, 특정 대상의 흐름은 search_prices를 쓴다. "
    "최종 답변은 도구 결과에 있는 숫자만 쓰고, 결과가 없으면 '" + retrieval.NO_ANSWER + "'라고 답한다."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "search_prices",
        "description": "질문과 관련된 시세 요약 문서를 유사도 순으로 찾는다.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "검색할 상품명·종목명이나 질문"},
            "k": {"type": "integer", "description": "가져올 문서 수(1~6)"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "rank_movers",
        "description": "관측 기간 변동률 순위를 계산한다. 이름에 keyword가 들어간 대상만 볼 수 있다.",
        "parameters": {"type": "object", "properties": {
            "direction": {"type": "string", "enum": ["up", "down"]},
            "keyword": {"type": "string", "description": "이름 필터(선택)"},
            "n": {"type": "integer", "description": "상위 몇 개(1~5)"},
        }, "required": ["direction"]},
    }},
]


class ToolError(ValueError):
    pass


def _validate(name: str, args: dict) -> dict:
    """모델이 만든 인자를 그대로 믿지 않는다. 모르는 도구·인자·범위 밖 값은 거절한다."""
    spec = next((t["function"] for t in TOOLS if t["function"]["name"] == name), None)
    if spec is None:
        raise ToolError(f"알 수 없는 도구: {name}")
    props = spec["parameters"]["properties"]
    unknown = set(args) - set(props)
    if unknown:
        raise ToolError(f"{name}: 알 수 없는 인자 {sorted(unknown)}")
    for req in spec["parameters"]["required"]:
        if req not in args or args[req] in ("", None):
            raise ToolError(f"{name}: 필수 인자 {req} 누락")
    clean = dict(args)
    if name == "search_prices":
        clean["k"] = _bounded_int(args.get("k", 4), 1, 6, "k")
    if name == "rank_movers":
        if args["direction"] not in ("up", "down"):
            raise ToolError("rank_movers: direction은 up 또는 down")
        clean["n"] = _bounded_int(args.get("n", 3), 1, 5, "n")
        clean["keyword"] = (args.get("keyword") or "").strip()
    return clean


def _bounded_int(value, lo: int, hi: int, label: str) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ToolError(f"{label}는 정수여야 함") from None
    if not lo <= v <= hi:
        raise ToolError(f"{label}는 {lo}~{hi}")
    return v


def _run(name: str, args: dict, index: retrieval.Index, embedder: models.Embedder) -> list[str]:
    if name == "search_prices":
        hits = [d for s, d in index.search(args["query"], args["k"], embedder) if s >= retrieval.MIN_SCORE]
        return [d["text"] for d in hits]
    pool = [d for d in index.docs if args["keyword"] in d["name"]] if args["keyword"] else index.docs
    ranked = sorted(pool, key=lambda d: d["change_pct"], reverse=args["direction"] == "up")[: args["n"]]
    out = []
    for i, d in enumerate(ranked, 1):
        src = SOURCES[d.get("kind", "kream")]
        out.append(f"{i}위 {d['name']}({d['option']}): {src['price']} {d['first_price']:,}원 → {d['last_price']:,}원, "
                   f"{d['change_pct']:+.1f}% ({d['first_date']}~{d['last_date']}, 대상 {len(pool)}개)")
    return out


@dataclass
class AgentResult:
    text: str
    calls: list[dict] = field(default_factory=list)  # 실행한 도구와 검증된 인자
    grounded: bool = True


ToolChat = Callable[[list[dict]], dict]  # messages -> assistant message(dict)


def tool_chat(messages: list[dict]) -> dict:
    res = requests.post(f"{models.OLLAMA_URL}/api/chat", json={
        "model": models.CHAT_MODEL, "stream": False, "tools": TOOLS, "messages": messages,
        "options": {"temperature": 0.1, "num_predict": 400, "repeat_penalty": 1.15},
    }, timeout=models.TIMEOUT)
    res.raise_for_status()
    return res.json()["message"]


def run(question: str, index: retrieval.Index, chat: ToolChat = tool_chat,
        embedder: models.Embedder = models.embed, max_steps: int = 3) -> AgentResult:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    calls: list[dict] = []
    evidence: list[str] = []

    nudged = False
    for _ in range(max_steps):
        reply = chat(messages)
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls and not evidence and not nudged:
            # 소형 모델은 도구를 부르지 않고 빈 답이나 추측을 내는 경우가 있어 한 번 더 요청한다.
            nudged = True
            messages.append({"role": "user", "content": "답하기 전에 반드시 도구를 호출해 데이터를 확인해 줘."})
            continue
        if not tool_calls:
            break
        messages.append({"role": "assistant", "content": reply.get("content", ""), "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc["function"]
            raw = fn.get("arguments") or {}
            args = json.loads(raw) if isinstance(raw, str) else raw
            try:
                clean = _validate(fn["name"], args)
                result = _run(fn["name"], clean, index, embedder)
                calls.append({"tool": fn["name"], "args": clean})
                evidence += result
                content = "\n".join(result) or "결과 없음"
            except ToolError as e:
                # 잘못된 호출은 실행하지 않고 이유를 돌려줘 모델이 한 번 더 고칠 기회를 준다.
                content = f"도구 호출 오류: {e}"
            messages.append({"role": "tool", "content": content})
    else:
        reply = chat(messages)

    if not evidence:
        return AgentResult(retrieval.NO_ANSWER, calls)
    text = (reply.get("content") or "").strip()
    bad = grounding.ungrounded(text, evidence)
    if bad or not text or retrieval.NO_ANSWER in text:
        # 근거가 있는데 모델이 거절하거나 어긋난 숫자를 쓰면, 판단을 모델에 맡기지 않고 근거를 그대로 보여 준다.
        return AgentResult("\n".join(evidence), calls, grounded=not bad)
    return AgentResult(text, calls)
