"""저장소에 함께 두는 가상 샘플 스냅샷을 만든다.

실제 운영 스냅샷은 공개하지 않으므로, 같은 형식의 작은 가상 데이터로
`market-briefing index/ask/brief` 흐름을 그대로 따라 해 볼 수 있게 한다.
"""

from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent.parent / "examples" / "sample_data"
HEADER = ["ID", "제품명", "모델명(품번)", "옵션(사이즈)", "상품 주소", "즉시 구매가", "보판 최저가(100점)",
          "즉시 판매가", "일판 회전율", "10거래일 최저가", "평균 일판가 3", "평균 일판가 5", "카테고리"]

# (ID, 제품명, 옵션, 카테고리, 날짜별 즉시 구매가)
PRODUCTS = [
    (1001, "샘플 러닝화 에어 템포 블랙", "270", ["신발", "스니커즈"], [189000, 192000, 205000, 231000]),
    (1002, "샘플 다운 패딩 오버핏 네이비", "L", ["의류", "아우터"], [412000, 398000, 371000, 352000]),
    (1003, "샘플 실버 체인 브레이슬릿", "ONE SIZE", ["패션잡화", "팔찌"], [268000, 270000, 268000, 274000]),
    (1004, "샘플 미니 크로스백 아이보리", "ONE SIZE", ["가방", "크로스백"], [1450000, 1520000, 1610000, 1590000]),
]
DATES = ["2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, date in enumerate(DATES):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["KREAM ⭐ 즐겨찾기 데이터 ⭐ (가상 샘플)"])
        ws.append(HEADER)
        for pid, name, option, category, prices in PRODUCTS:
            buy = prices[i]
            ws.append([pid, name, f"SAMPLE-{pid}", option, f"https://example.com/products/{pid}", buy, buy + 20000,
                       round(buy * 0.93), 2.4, round(buy * 0.9), round(buy * 0.95), round(buy * 0.94),
                       str(category).replace("'", '"')])
        wb.save(OUT / f"KREAM {date} 즐겨찾기 전체 데이터.xlsx")
    print(f"{len(DATES)}개 스냅샷 → {OUT}")


if __name__ == "__main__":
    main()
