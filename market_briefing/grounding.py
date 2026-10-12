"""생성 결과의 숫자가 근거 문서에 있는지 확인한다.

시세 브리핑에서 가장 위험한 실패는 모델이 그럴듯한 가격을 지어내는 것이다.
문장 의미까지 판정하지는 못하지만, 근거에 없는 숫자가 나오면 확실히 잡아낸다.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"[+-]?\d[\d,]*(?:\.\d+)?")

# 순번·개수처럼 문서에 없어도 자연스럽게 등장하는 작은 수
_ALWAYS_ALLOWED = {str(i) for i in range(0, 11)}


def numbers(text: str) -> set[str]:
    return {n.replace(",", "").lstrip("+") for n in _NUMBER.findall(text)}


def ungrounded(generated: str, sources: list[str]) -> set[str]:
    """generated에 나왔지만 sources 어디에도 없는 숫자. 비어 있어야 통과."""
    allowed = set(_ALWAYS_ALLOWED)
    for s in sources:
        allowed |= numbers(s)
    return {n for n in numbers(generated) if n not in allowed and n.lstrip("-") not in allowed}
