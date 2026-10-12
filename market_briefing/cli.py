"""명령줄 진입점: `market-briefing index | ask | brief`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import agent, documents, media, newscast, retrieval, snapshots, stocks


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="market-briefing", description="시세 데이터(KREAM 스냅샷·국내 주식) RAG와 브리핑 영상 생성")
    p.add_argument("--data", type=Path, default=Path("data/raw"), help="스냅샷 xlsx 폴더")
    p.add_argument("--index", type=Path, default=Path("data/index"), help="색인 저장 위치")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("index", help="스냅샷을 문서화하고 임베딩 색인을 만든다")
    s = sub.add_parser("index-stocks", help="국내 주식 일별 종가로 색인을 만든다(FinanceDataReader)")
    s.add_argument("--start", required=True)
    s.add_argument("--end", required=True)
    s.add_argument("--top", type=int, default=30, help="시가총액 상위 종목 수")
    s.add_argument("--market", default="KOSPI")
    a = sub.add_parser("ask", help="색인을 근거로 질문에 답한다")
    a.add_argument("question")
    a.add_argument("-k", type=int, default=4)
    g = sub.add_parser("agent", help="로컬 LLM이 도구를 골라 답한다(Function Calling)")
    g.add_argument("question")
    nc = sub.add_parser("newscast", help="국내 주식 색인으로 증시 브리핑(방송 형식) 영상을 만든다")
    nc.add_argument("-n", type=int, default=3)
    nc.add_argument("--out", type=Path, default=Path("out-newscast"))
    nc.add_argument("--symbol", default="^KS11", help="지수 심볼(FinanceDataReader)")
    b = sub.add_parser("brief", help="변동 상위 상품으로 브리핑 원고·음성·영상을 만든다")
    b.add_argument("-n", type=int, default=3)
    b.add_argument("--out", type=Path, default=Path("out"))
    b.add_argument("--llm-script", action="store_true", help="원고를 로컬 LLM으로 쓰고 숫자 대조를 거친다(기본: 데이터로 문장 고정)")
    args = p.parse_args(argv)

    if args.command == "index":
        docs = documents.build(snapshots.load(args.data))
        retrieval.Index.build(docs).save(args.index)
        print(f"문서 {len(docs)}건을 색인했습니다 → {args.index}")

    elif args.command == "index-stocks":
        docs = stocks.fetch(args.start, args.end, args.top, args.market)
        retrieval.Index.build(docs).save(args.index)
        print(f"{args.market} {len(docs)}개 종목을 색인했습니다 → {args.index}")

    elif args.command == "ask":
        answer = retrieval.ask(args.question, retrieval.Index.load(args.index), k=args.k)
        print(json.dumps(answer.__dict__, ensure_ascii=False, indent=2))

    elif args.command == "agent":
        result = agent.run(args.question, retrieval.Index.load(args.index))
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))

    elif args.command == "newscast":
        index = retrieval.Index.load(args.index)
        docs = [documents.PriceDocument(**{**d, "points": [tuple(p) for p in d["points"]]}) for d in index.docs]
        movers = documents.top_movers(docs, args.n)
        start = min(d.first_date for d in movers)
        end = max(d.last_date for d in movers)
        kospi = newscast.index_points(start, (np.datetime64(end) + np.timedelta64(1, "D")).astype(str), args.symbol)
        video = newscast.render(newscast.plan(movers, kospi), kospi, args.out)
        print(video)

    elif args.command == "brief":
        index = retrieval.Index.load(args.index)
        docs = [documents.PriceDocument(**{**d, "points": [tuple(p) for p in d["points"]]}) for d in index.docs]
        movers = documents.top_movers(docs, args.n)
        script = media.write_script(movers) if args.llm_script else media.compose_script(movers)
        result = media.render(movers, script, args.out)
        print(json.dumps({k: str(v) for k, v in result.__dict__.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
