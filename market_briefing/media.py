"""브리핑 원고 → 음성(TTS) → 차트 → 영상.

TTS는 macOS 내장 `say`(한국어 음성 Yuna), 영상 합성은 ffmpeg를 쓴다.
둘 다 로컬에서 돌아가므로 원고와 데이터가 외부로 나가지 않는다.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import grounding, models
from .documents import PriceDocument, korean_date, spoken_fact

SCRIPT_PROMPT = (
    "너는 시세 브리핑 원고 작성자다. 주어진 [사실]만 사용해 40초 안팎의 한국어 낭독 원고를 쓴다. "
    "숫자·금액·날짜는 [사실]에 적힌 표기('283만 원', '2월 4일', '29.0%') 그대로 옮기고, 반올림하거나 새로 계산하지 않는다. "
    "원고 길이나 시간 같은 숫자도 쓰지 않는다. 상품명은 [사실]에 적힌 이름에서 브랜드와 핵심 단어를 그대로 쓰고 다른 품목으로 바꾸지 않는다. "
    "투자를 권하거나 앞으로의 가격을 전망하지 않는다. 제목·기호·목록 없이 문장만 쓴다."
)


class ScriptRejected(RuntimeError):
    pass


@dataclass
class Briefing:
    script: str
    movers: list[str]
    chart: Path
    audio: Path
    video: Path


def compose_script(movers: list[PriceDocument]) -> str:
    """기본 원고. 수치와 상승·하락 방향을 데이터에서 그대로 문장으로 만든다.

    소형 로컬 모델은 숫자를 맞게 옮겨도 '올랐다'를 '내렸다'로 바꿔 쓰는 경우가 있었다.
    숫자 대조로는 이런 방향 오류를 잡을 수 없어, 기본값은 모델 없이 사실을 고정한다.
    """
    start = min(d.first_date for d in movers)
    end = max(d.last_date for d in movers)
    lines = [f"{korean_date(start)}부터 {korean_date(end)}까지 관측한 KREAM 시세 가운데 변동이 컸던 상품 {len(movers)}개를 전해 드립니다."]
    lines += [spoken_fact(d).replace(": ", "은 ", 1).replace("다.", "습니다.") for d in movers]
    lines.append("이 브리핑은 관측 데이터를 요약한 것이며 투자나 구매를 권하지 않습니다.")
    return " ".join(lines)


def write_script(movers: list[PriceDocument], chat: models.Chat = models.chat, attempts: int = 3) -> str:
    facts = "\n".join(f"- {spoken_fact(d)}" for d in movers)
    sources = [spoken_fact(d) for d in movers] + [d.text for d in movers]
    for _ in range(attempts):
        script = chat(SCRIPT_PROMPT, f"[사실]\n{facts}")
        bad = grounding.ungrounded(script, sources)
        if not bad:
            return script
    raise ScriptRejected(f"근거에 없는 숫자가 계속 나와 원고를 쓰지 않았습니다: {sorted(bad)}")


def render(movers: list[PriceDocument], script: str, out: Path, voice: str = "Yuna") -> Briefing:
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.txt").write_text(script + "\n")
    chart, audio, video = out / "chart.png", out / "briefing.aiff", out / "briefing.mp4"

    draw_chart(movers, chart)
    subprocess.run(["say", "-v", voice, "-o", str(audio), script], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(chart), "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-vf", "scale=1280:-2",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(video),
    ], check=True)
    return Briefing(script, [d.id for d in movers], chart, audio, video)


def draw_chart(movers: list[PriceDocument], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    _use_korean_font()
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
    for d in movers:
        dates = [np.datetime64(day) for day, _ in d.points]
        base = d.points[0][1]
        ax.plot(dates, [p / base * 100 for _, p in d.points], marker="o", linewidth=2,
                label=f"{_short(d.name)} ({d.option})  {d.change_pct:+.1f}%")

    start = min(d.first_date for d in movers)
    end = max(d.last_date for d in movers)
    ax.set_title(f"KREAM 즉시 구매가 변동 상위 {len(movers)}개  ·  {korean_date(start)} ~ {korean_date(end)}", fontsize=15, pad=14)
    ax.set_ylabel("첫 관측가 = 100")
    ax.axhline(100, color="#999", linewidth=1, linestyle="--")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-m/%-d"))
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=10, frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _short(name: str, limit: int = 24) -> str:
    return name if len(name) <= limit else name[: limit - 1] + "…"


def _use_korean_font() -> None:
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for font in ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"):
        if Path(font).exists():
            font_manager.fontManager.addfont(font)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
            return
