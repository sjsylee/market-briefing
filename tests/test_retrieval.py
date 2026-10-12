from market_briefing import retrieval
from conftest import keyword_embedder


def test_answer_uses_matching_document(sample_index):
    a = retrieval.ask("패딩 시세 어때?", sample_index, embedder=keyword_embedder,
                      chat=lambda s, u: "352,000원으로 -14.6% 변했습니다 [1]")
    assert a.grounded and a.sources[0]["name"] == "샘플 다운 패딩 오버핏 네이비"


def test_answer_with_invented_number_is_withheld(sample_index):
    a = retrieval.ask("패딩 시세 어때?", sample_index, embedder=keyword_embedder,
                      chat=lambda s, u: "곧 300,000원까지 내려갑니다")
    assert not a.grounded and a.ungrounded_numbers == ["300000"] and "300,000" not in a.text


def test_unrelated_question_does_not_call_model(sample_index):
    def must_not_be_called(*_):
        raise AssertionError("관련 문서가 없으면 모델을 부르면 안 된다")
    a = retrieval.ask("비트코인 시세 알려줘", sample_index, embedder=keyword_embedder, chat=must_not_be_called)
    assert a.text == retrieval.NO_ANSWER and a.sources == []


def test_index_round_trip(tmp_path, sample_index):
    sample_index.save(tmp_path)
    loaded = retrieval.Index.load(tmp_path)
    import json
    assert loaded.docs == json.loads(json.dumps(sample_index.docs))  # 저장 후에는 튜플이 리스트로 돌아온다
    assert (loaded.vectors == sample_index.vectors).all()


def test_ranking_question_is_computed_over_all_documents(sample_index):
    def must_not_be_called(*_):
        raise AssertionError("순위 질문은 모델 없이 계산해야 한다")
    a = retrieval.ask("가장 많이 오른 상품은?", sample_index, embedder=keyword_embedder, chat=must_not_be_called)
    assert "샘플 러닝화 에어 템포 블랙" in a.text and "+22.2%" in a.text

    a = retrieval.ask("패딩 중에 가장 많이 내린 건?", sample_index, embedder=keyword_embedder, chat=must_not_be_called)
    assert "샘플 다운 패딩 오버핏 네이비" in a.text and "-14.6%" in a.text
