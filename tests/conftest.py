from pathlib import Path

import numpy as np
import pytest

from market_briefing import documents, retrieval, snapshots

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_data"
KEYWORDS = ["러닝화", "패딩", "브레이슬릿", "크로스백"]


def keyword_embedder(texts):
    """상품명 키워드로 만드는 결정적 벡터. 실제 임베딩 모델 없이 검색 흐름을 시험한다."""
    v = np.array([[1.0 if k in t else 0.0 for k in KEYWORDS] + [0.01] for t in texts], dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


@pytest.fixture
def sample_docs():
    return documents.build(snapshots.load(SAMPLE))


@pytest.fixture
def sample_index(sample_docs):
    return retrieval.Index.build(sample_docs, embedder=keyword_embedder)
