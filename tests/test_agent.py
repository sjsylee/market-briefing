from market_briefing import agent, retrieval
from conftest import keyword_embedder


def scripted(*replies):
    """도구 호출 응답을 순서대로 돌려주는 가짜 모델. 받은 메시지도 기록한다."""
    seen = []
    it = iter(replies)

    def chat(messages):
        seen.append([m["role"] for m in messages])
        return next(it)
    chat.seen = seen
    return chat


def call(name, **args):
    return {"content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def test_model_picks_tool_and_answer_is_grounded(sample_index):
    chat = scripted(call("rank_movers", direction="down", n=1),
                    {"content": "가장 많이 내린 것은 샘플 다운 패딩 오버핏 네이비로 -14.6%입니다."})
    r = agent.run("가장 많이 내린 상품은?", sample_index, chat=chat, embedder=keyword_embedder)
    assert r.grounded and "-14.6%" in r.text
    assert r.calls == [{"tool": "rank_movers", "args": {"direction": "down", "n": 1, "keyword": ""}}]


def test_invalid_arguments_are_rejected_and_reported_back(sample_index):
    chat = scripted(call("rank_movers", direction="sideways"),
                    call("rank_movers", direction="up", n=1),
                    {"content": "샘플 러닝화 에어 템포 블랙이 +22.2%로 가장 많이 올랐습니다."})
    r = agent.run("가장 많이 오른 건?", sample_index, chat=chat, embedder=keyword_embedder)
    assert [c["args"]["direction"] for c in r.calls] == ["up"]  # 잘못된 첫 호출은 실행하지 않음
    assert "tool" in chat.seen[1]  # 오류 내용을 모델에 돌려줌
    assert "+22.2%" in r.text


def test_unknown_tool_is_never_executed(sample_index):
    chat = scripted(call("delete_all"), {"content": "완료"}, {"content": "완료"})
    r = agent.run("다 지워줘", sample_index, chat=chat, embedder=keyword_embedder)
    assert r.calls == [] and r.text == retrieval.NO_ANSWER


def test_invented_number_falls_back_to_tool_output(sample_index):
    chat = scripted(call("search_prices", query="패딩 시세"), {"content": "패딩은 50만 원까지 오릅니다"})
    r = agent.run("패딩 시세?", sample_index, chat=chat, embedder=keyword_embedder)
    assert not r.grounded and "412,000원" in r.text  # 모델 문장 대신 근거 문서를 보여 줌


def test_answer_without_tool_use_is_refused(sample_index):
    chat = scripted({"content": "러닝화는 30만 원입니다"}, {"content": "30만 원입니다"})
    r = agent.run("러닝화 시세?", sample_index, chat=chat, embedder=keyword_embedder)
    assert r.text == retrieval.NO_ANSWER


def test_model_is_nudged_once_when_it_skips_tools(sample_index):
    chat = scripted({"content": ""}, call("rank_movers", direction="up", n=1),
                    {"content": "샘플 러닝화 에어 템포 블랙이 +22.2% 올랐습니다."})
    r = agent.run("가장 많이 오른 건?", sample_index, chat=chat, embedder=keyword_embedder)
    assert "+22.2%" in r.text and len(r.calls) == 1


def test_refusal_despite_evidence_shows_evidence(sample_index):
    chat = scripted(call("search_prices", query="러닝화"), {"content": retrieval.NO_ANSWER})
    r = agent.run("러닝화 시세?", sample_index, chat=chat, embedder=keyword_embedder)
    assert "189,000원" in r.text
