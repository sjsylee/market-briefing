"""Ollama 로컬 모델 호출. 테스트에서는 같은 시그니처의 가짜 함수로 바꿔 끼운다."""

from __future__ import annotations

import os
from typing import Callable

import numpy as np
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen2.5:3b")
TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "180"))

Embedder = Callable[[list[str]], np.ndarray]
Chat = Callable[[str, str], str]


def embed(texts: list[str]) -> np.ndarray:
    res = requests.post(f"{OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": texts}, timeout=TIMEOUT)
    res.raise_for_status()
    vectors = np.asarray(res.json()["embeddings"], dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def chat(system: str, user: str) -> str:
    res = requests.post(f"{OLLAMA_URL}/api/chat", json={
        "model": CHAT_MODEL,
        "stream": False,
        # 소형 모델이 같은 문장을 반복하며 끝나지 않는 경우가 있어 길이와 반복에 상한을 둔다.
        "options": {"temperature": 0.1, "num_predict": 400, "repeat_penalty": 1.15},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }, timeout=TIMEOUT)
    res.raise_for_status()
    return res.json()["message"]["content"].strip()
