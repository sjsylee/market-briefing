"""KREAM 즐겨찾기 스냅샷(xlsx)을 읽어 관측 행으로 바꾼다.

스냅샷은 같은 상품 목록을 날짜마다 내려받은 파일이다. 파일명에 날짜가 있고
(`KREAM 2026-02-04 즐겨찾기 전체 데이터.xlsx`), 1행은 제목, 2행이 헤더다.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# macOS 파일명은 NFD로 저장되는 경우가 있어 NFC로 맞춘 뒤 비교한다.
SNAPSHOT_NAME = re.compile(r"(\d{4}-\d{2}-\d{2}) 즐겨찾기 전체 데이터\.xlsx$")


@dataclass(frozen=True)
class Observation:
    date: str
    product_id: int
    option: str
    name: str
    category: str
    buy_now: int | None  # 즉시 구매가
    sell_now: int | None  # 즉시 판매가
    avg_sale_5: int | None  # 최근 5거래 평균 체결가
    daily_turnover: float | None  # 일판 회전율


def snapshot_date(path: Path) -> str | None:
    m = SNAPSHOT_NAME.search(unicodedata.normalize("NFC", path.name))
    return m.group(1) if m else None


def load(directory: Path) -> list[Observation]:
    observations: list[Observation] = []
    for path in sorted(directory.glob("*.xlsx")):
        date = snapshot_date(path)
        if date:
            observations.extend(_read(path, date))
    return observations


def _read(path: Path, date: str) -> list[Observation]:
    import openpyxl

    sheet = openpyxl.load_workbook(path, read_only=True).active
    rows = sheet.iter_rows(values_only=True)
    next(rows)  # 제목 행
    col = {str(h): i for i, h in enumerate(next(rows))}

    out = []
    for r in rows:
        if not r or r[col["ID"]] is None:
            continue
        get = lambda key: r[col[key]] if key in col else None
        out.append(Observation(
            date=date,
            product_id=int(get("ID")),
            option=str(get("옵션(사이즈)")),
            name=str(get("제품명")),
            category=_category(get("카테고리")),
            buy_now=_int(get("즉시 구매가")),
            sell_now=_int(get("즉시 판매가")),
            avg_sale_5=_int(get("평균 일판가 5")),
            daily_turnover=_float(get("일판 회전율")),
        ))
    return out


def _category(raw) -> str:
    try:
        return " > ".join(json.loads(raw))
    except (TypeError, ValueError):
        return str(raw or "")


def _float(v) -> float | None:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    f = _float(v)
    return None if f is None else int(f)
