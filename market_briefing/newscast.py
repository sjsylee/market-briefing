"""경제 방송의 '증시 브리핑' 형식으로 영상을 만든다.

장면 구성: 오프닝 타이틀 → 코스피 지수 → 변동 상위 종목별 장면 → 클로징.
장면마다 낭독 문장을 따로 TTS로 만들고 그 길이만큼 화면을 보여 주며, 문장은 자막으로 함께 띄운다.
문장의 숫자와 상승·하락 방향은 데이터에서 만들고 모델은 쓰지 않는다(media.compose_script와 같은 이유).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .documents import PriceDocument, korean_date, manwon, ro, topic

NAVY, ACCENT, UP, DOWN, INK, MUTED = "#0b1f3a", "#f2b705", "#d1343a", "#1f6fd1", "#1d2433", "#6b7280"
W, H, DPI = 12.8, 7.2, 100


@dataclass
class Scene:
    kind: str  # opening | index | stock | closing
    narration: str
    doc: PriceDocument | None = None


def index_points(start: str, end: str, symbol: str = "^KS11") -> list[tuple[str, float]]:
    import FinanceDataReader as fdr

    df = fdr.DataReader(symbol, start, end)
    return [(d.strftime("%Y-%m-%d"), round(float(c), 2)) for d, c in df["Close"].items()]


def _direction(pct: float) -> str:
    return "올랐습니다" if pct >= 0 else "내렸습니다"


def plan(movers: list[PriceDocument], kospi: list[tuple[str, float]]) -> list[Scene]:
    start, end = kospi[0][0], kospi[-1][0]
    k0, k1 = kospi[0][1], kospi[-1][1]
    k_pct = round((k1 - k0) / k0 * 100, 1)
    scenes = [
        Scene("opening", f"{korean_date(start)}부터 {korean_date(end)}까지의 국내 증시 흐름을 정리해 드립니다."),
        Scene("index", f"이 기간 코스피 지수는 {k0:,.2f}에서 {ro(f'{k1:,.2f}')} {abs(k_pct):.1f}% {_direction(k_pct)}."),
    ]
    for d in movers:
        scenes.append(Scene("stock", (
            f"{topic(d.name)} {manwon(d.first_price)}에서 {manwon(d.last_price)}으로 "
            f"{abs(d.change_pct):.1f}% {_direction(d.change_pct)}."
        ), d))
    scenes.append(Scene("closing", "이 브리핑은 공개 시세 데이터를 요약한 것이며, 투자를 권하지 않습니다."))
    return scenes


def render(scenes: list[Scene], kospi: list[tuple[str, float]], out: Path, voice: str = "Yuna") -> Path:
    out.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, scene in enumerate(scenes):
        audio = out / f"scene{i}.aiff"
        subprocess.run(["say", "-v", voice, "-o", str(audio), scene.narration], check=True)
        frame = out / f"scene{i}.png"
        _draw(scene, kospi, frame, i, len(scenes))
        clip = out / f"scene{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(frame), "-i", str(audio),
            "-af", "apad=pad_dur=0.6",  # 문장 사이 숨 고르기
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", str(clip),
        ], check=True)
        clips.append(clip)

    listing = out / "clips.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips))
    video = out / "newscast.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(video)], check=True)
    (out / "newscast.txt").write_text("\n".join(s.narration for s in scenes) + "\n")
    return video


# ── 화면 ─────────────────────────────────────────────

def _draw(scene: Scene, kospi, path: Path, i: int, total: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .media import _use_korean_font

    _use_korean_font()
    fig = plt.figure(figsize=(W, H), dpi=DPI, facecolor="white")
    _header(fig, kospi)

    if scene.kind == "opening":
        fig.text(0.5, 0.56, "증시 브리핑", ha="center", va="center", fontsize=54, fontweight="bold", color=NAVY)
        fig.text(0.5, 0.44, f"국내 증시 · {korean_date(kospi[0][0])} ~ {korean_date(kospi[-1][0])}",
                 ha="center", fontsize=22, color=MUTED)
    elif scene.kind == "index":
        pct = (kospi[-1][1] - kospi[0][1]) / kospi[0][1] * 100
        _headline(fig, "코스피", f"{kospi[-1][1]:,.2f}", pct)
        _line(fig, kospi, UP if pct >= 0 else DOWN)
    elif scene.kind == "stock":
        d = scene.doc
        _headline(fig, f"{d.name} ({d.option})", f"{d.last_price:,}원", d.change_pct)
        _line(fig, [(day, float(p)) for day, p in d.points], UP if d.change_pct >= 0 else DOWN)
    else:
        fig.text(0.5, 0.52, "투자 판단의 책임은 투자자 본인에게 있습니다", ha="center", fontsize=24, color=INK)
        fig.text(0.5, 0.43, "자료: FinanceDataReader(공개 시세) · 제작: market-briefing", ha="center", fontsize=15, color=MUTED)

    _subtitle(fig, scene.narration)
    fig.text(0.975, 0.955, f"{i + 1}/{total}", ha="right", va="center", fontsize=12, color="white")
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _header(fig, kospi) -> None:
    from matplotlib.patches import Rectangle

    fig.add_artist(Rectangle((0, 0.91), 1, 0.09, transform=fig.transFigure, color=NAVY))
    fig.add_artist(Rectangle((0, 0.905), 1, 0.006, transform=fig.transFigure, color=ACCENT))
    fig.text(0.025, 0.955, "MARKET BRIEFING", va="center", fontsize=16, fontweight="bold", color="white")
    fig.text(0.24, 0.955, f"기준일 {korean_date(kospi[-1][0])}", va="center", fontsize=13, color="#cbd5e1")


def _headline(fig, title: str, value: str, pct: float) -> None:
    color = UP if pct >= 0 else DOWN
    fig.text(0.05, 0.82, title, fontsize=26, fontweight="bold", color=INK, va="center")
    fig.text(0.05, 0.73, value, fontsize=34, fontweight="bold", color=INK, va="center")
    fig.text(0.47, 0.73, f"{'▲' if pct >= 0 else '▼'} {abs(pct):.1f}%", fontsize=30, fontweight="bold", color=color, va="center")


def _line(fig, points, color) -> None:
    import matplotlib
    import matplotlib.dates as mdates
    import matplotlib.ticker  # noqa: F401  (FuncFormatter)

    ax = fig.add_axes([0.06, 0.25, 0.9, 0.4])
    xs = [np.datetime64(d) for d, _ in points]
    ys = [v for _, v in points]
    ax.plot(xs, ys, color=color, linewidth=3)
    ax.fill_between(xs, ys, min(ys), color=color, alpha=0.08)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-m/%-d"))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.tick_params(labelsize=11, colors=MUTED)
    ax.grid(axis="y", alpha=0.25)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)


def _subtitle(fig, text: str) -> None:
    from matplotlib.patches import Rectangle

    fig.add_artist(Rectangle((0, 0), 1, 0.16, transform=fig.transFigure, color=NAVY, alpha=0.92))
    fig.text(0.5, 0.08, text, ha="center", va="center", fontsize=20, color="white", wrap=True)
