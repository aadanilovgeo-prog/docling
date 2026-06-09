#!/usr/bin/env python3
"""
Надёжная склейка длинного скриншота страницы из серии viewport-кадров.

Алгоритм не зависит от диагонали/разрешения монитора: все расчёты идут от
фактической высоты области захвата (viewport), scrollY и scrollHeight.

Основные функции (API):
  get_page_metrics()          — метрики страницы перед съёмкой
  capture_viewport()          — один кадр viewport
  scroll_to_next_position()   — скролл с перекрытием
  find_overlap()              — поиск реального overlap между кадрами
  crop_duplicate_part()       — обрезка дублирующей верхней части
  stitch_images()             — последовательная склейка
  finalize_long_screenshot()  — финальная обрезка по высоте контента

Запуск:
  # Захват страницы в браузере (нужен: pip install playwright && playwright install chromium)
  python scroll_long_screenshot.py capture https://example.com -o docs/page.png

  # Склейка уже снятых кадров из папки (001.png, 002.png, ...)
  python scroll_long_screenshot.py stitch captures/ -o docs/page.png

  # Только overlap между двумя файлами (отладка)
  python scroll_long_screenshot.py overlap prev.png curr.png
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
from PIL import Image

try:
    from playwright.async_api import Page, async_playwright
except ImportError:  # pragma: no cover - optional dependency
    Page = Any  # type: ignore[misc, assignment]
    async_playwright = None  # type: ignore[assignment]

VERSION = "1.0.0"

LOG = logging.getLogger("scroll_long_screenshot")

# --- Конфигурация (все доли — без фиксированных px монитора) ----------------

DEFAULT_SCROLL_STEP_RATIO = 0.72       # scrollStep = viewportHeight * ratio
DEFAULT_SEARCH_RATIO = 0.35            # нижние/верхние 35% для поиска overlap
DEFAULT_EXCLUDE_TOP_RATIO = 0.10       # игнор верхних 10% (sticky header)
DEFAULT_MIN_CONFIDENCE = 0.62          # ниже — fallback
DEFAULT_SCROLL_SETTLE_MS = 350
DEFAULT_MAX_FRAMES = 500
DEFAULT_OVERLAP_STEP = 2               # шаг перебора overlap (px в координатах скрина)


@dataclass
class PageMetrics:
    viewport_width: int
    viewport_height: int
    device_pixel_ratio: float
    scroll_y: float
    scroll_height: float
    client_height: float

    @property
    def capture_width_px(self) -> int:
        return max(1, int(round(self.viewport_width * self.device_pixel_ratio)))

    @property
    def capture_height_px(self) -> int:
        return max(1, int(round(self.viewport_height * self.device_pixel_ratio)))

    @property
    def max_scroll_y(self) -> float:
        return max(0.0, self.scroll_height - self.client_height)

    @property
    def scroll_step_css(self) -> float:
        return self.viewport_height * DEFAULT_SCROLL_STEP_RATIO

    @property
    def expected_overlap_css(self) -> float:
        return self.viewport_height - self.scroll_step_css

    @property
    def expected_overlap_px(self) -> int:
        return max(1, int(round(self.expected_overlap_css * self.device_pixel_ratio)))


@dataclass
class OverlapData:
    overlap_px: int
    confidence: float
    method: Literal["matched", "fallback"]
    best_score: float
    message: str = ""


@dataclass
class CaptureState:
    metrics: PageMetrics
    frames: list[Image.Image] = field(default_factory=list)
    scroll_positions: list[float] = field(default_factory=list)
    overlaps: list[OverlapData] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StitchConfig:
    scroll_step_ratio: float = DEFAULT_SCROLL_STEP_RATIO
    search_ratio: float = DEFAULT_SEARCH_RATIO
    exclude_top_ratio: float = DEFAULT_EXCLUDE_TOP_RATIO
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    overlap_step: int = DEFAULT_OVERLAP_STEP
    hide_fixed_elements: bool = True


# --- JS: метрики, скролл, скрытие fixed/sticky --------------------------------

METRICS_JS = """
() => ({
  viewportWidth: window.innerWidth,
  viewportHeight: window.innerHeight,
  devicePixelRatio: window.devicePixelRatio || 1,
  scrollY: window.scrollY,
  scrollHeight: Math.max(
    document.body.scrollHeight,
    document.documentElement.scrollHeight,
    document.body.offsetHeight,
    document.documentElement.offsetHeight
  ),
  clientHeight: document.documentElement.clientHeight
})
"""

HIDE_FIXED_JS = """
() => {
  const touched = [];
  for (const el of document.querySelectorAll('*')) {
    const style = window.getComputedStyle(el);
    if (style.position === 'fixed' || style.position === 'sticky') {
      touched.push([el, el.style.display, el.style.visibility]);
      el.style.setProperty('display', 'none', 'important');
      el.style.setProperty('visibility', 'hidden', 'important');
    }
  }
  window.__scrollStitchHidden = touched;
  return touched.length;
}
"""

RESTORE_FIXED_JS = """
() => {
  const touched = window.__scrollStitchHidden || [];
  for (const [el, display, visibility] of touched) {
    el.style.display = display;
    el.style.visibility = visibility;
  }
  window.__scrollStitchHidden = [];
  return touched.length;
}
"""


def get_page_metrics(page: Page) -> PageMetrics:
    """Синхронная обёртка: getPageMetrics()."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_get_page_metrics(page))
    raise RuntimeError("get_page_metrics() cannot be used inside a running event loop")


async def async_get_page_metrics(page: Page) -> PageMetrics:
    raw = await page.evaluate(METRICS_JS)
    return PageMetrics(
        viewport_width=int(raw["viewportWidth"]),
        viewport_height=int(raw["viewportHeight"]),
        device_pixel_ratio=float(raw["devicePixelRatio"] or 1.0),
        scroll_y=float(raw["scrollY"]),
        scroll_height=float(raw["scrollHeight"]),
        client_height=float(raw["clientHeight"]),
    )


async def capture_viewport(page: Page) -> Image.Image:
    """Снимок текущего viewport (не full-page)."""
    png = await page.screenshot(type="png", animations="disabled", caret="hide")
    return Image.open(io.BytesIO(png)).convert("RGB")


async def scroll_to_next_position(
    page: Page,
    metrics: PageMetrics,
    *,
    scroll_step_ratio: float = DEFAULT_SCROLL_STEP_RATIO,
    settle_ms: int = DEFAULT_SCROLL_SETTLE_MS,
) -> tuple[float, float]:
    """
  Скролл с перекрытием. Возвращает (old_scroll_y, new_scroll_y).
  scrollStep = viewportHeight * scroll_step_ratio
    """
    old_y = metrics.scroll_y
    step = metrics.viewport_height * scroll_step_ratio
    target = min(old_y + step, metrics.max_scroll_y)
    await page.evaluate("(y) => window.scrollTo(0, y)", target)
    if settle_ms > 0:
        await page.wait_for_timeout(settle_ms)
    new_metrics = await async_get_page_metrics(page)
    return old_y, new_metrics.scroll_y


async def hide_fixed_elements(page: Page) -> int:
    return int(await page.evaluate(HIDE_FIXED_JS))


async def restore_fixed_elements(page: Page) -> int:
    return int(await page.evaluate(RESTORE_FIXED_JS))


# --- Overlap detection (numpy) ------------------------------------------------

def _to_gray_array(img: Image.Image) -> np.ndarray:
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    return gray


def _row_profile(arr: np.ndarray, block: int = 4) -> np.ndarray:
    """Усреднение по блокам строк — устойчивее к субпиксельным отличиям."""
    h, w = arr.shape
    usable = (h // block) * block
    if usable < block:
        return arr
    trimmed = arr[:usable].reshape(usable // block, block, w)
    return trimmed.mean(axis=1)


def _similarity(a: np.ndarray, b: np.ndarray) -> float:
    """1.0 = идентично, 0.0 = максимально различно."""
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return 0.0
    diff = np.abs(a - b)
    # Нормализация: средняя разница 0..255 -> confidence
    mad = float(diff.mean())
    return max(0.0, 1.0 - mad / 64.0)


def find_overlap(
    previous_image: Image.Image,
    current_image: Image.Image,
    *,
    expected_overlap_px: int | None = None,
    search_ratio: float = DEFAULT_SEARCH_RATIO,
    exclude_top_ratio: float = DEFAULT_EXCLUDE_TOP_RATIO,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    overlap_step: int = DEFAULT_OVERLAP_STEP,
) -> OverlapData:
    """
    Ищет реальное совпадение между нижней частью previous и верхней частью current.

    Для каждого кандидата overlap=o сравниваются:
      previous[h-o:h]  и  current[0:o]
    Верхние exclude_top строк current не участвуют в оценке (sticky header).
    """
    prev = _to_gray_array(previous_image)
    curr = _to_gray_array(current_image)

    if prev.shape[1] != curr.shape[1]:
        msg = f"width mismatch: {prev.shape[1]} vs {curr.shape[1]}"
        LOG.warning(msg)
        fb = expected_overlap_px or max(1, int(curr.shape[0] * 0.25))
        return OverlapData(fb, 0.0, "fallback", float("inf"), msg)

    h_prev, h_curr = prev.shape[0], curr.shape[0]
    search_limit = max(32, int(min(h_prev, h_curr) * search_ratio))
    exclude_top = max(0, int(h_curr * exclude_top_ratio))

    min_o = max(16, int(search_limit * 0.2))
    max_o = min(search_limit, h_prev - 1, h_curr - 1)
    if expected_overlap_px:
        min_o = max(16, int(expected_overlap_px * 0.5))
        max_o = min(max_o, int(expected_overlap_px * 1.5))

    if max_o <= min_o:
        max_o = min(h_prev, h_curr) - 1
        min_o = max(16, max_o // 3)

    best_overlap = expected_overlap_px or min_o
    best_conf = -1.0
    best_score = float("inf")
    second_conf = -1.0

    for o in range(min_o, max_o + 1, max(1, overlap_step)):
        prev_strip = prev[h_prev - o : h_prev, :]
        curr_strip = curr[0:o, :]
        skip = min(exclude_top, max(0, o - 24))
        if o - skip < 24:
            continue
        prev_cmp = prev_strip[skip:, :]
        curr_cmp = curr_strip[skip:, :]
        a = _row_profile(prev_cmp)
        b = _row_profile(curr_cmp)
        rows = min(a.shape[0], b.shape[0])
        if rows < 3:
            continue
        conf = _similarity(a[-rows:, :], b[-rows:, :])
        score = 1.0 - conf
        if conf > best_conf:
            second_conf = best_conf
            best_conf = conf
            best_score = score
            best_overlap = o

    margin = best_conf - second_conf if second_conf >= 0 else best_conf
    confident = best_conf >= min_confidence and (margin >= 0.03 or best_conf >= 0.75)

    if confident:
        return OverlapData(
            overlap_px=best_overlap,
            confidence=best_conf,
            method="matched",
            best_score=best_score,
            message=f"matched overlap={best_overlap}px conf={best_conf:.3f}",
        )

    fb = expected_overlap_px if expected_overlap_px else best_overlap
    fb = max(16, min(fb, h_curr - 1))
    msg = (
        f"low confidence ({best_conf:.3f}), fallback overlap={fb}px "
        f"(expected={expected_overlap_px})"
    )
    LOG.warning(msg)
    return OverlapData(
        overlap_px=fb,
        confidence=best_conf,
        method="fallback",
        best_score=best_score,
        message=msg,
    )


def crop_duplicate_part(current_image: Image.Image, overlap_data: OverlapData) -> Image.Image:
    """Обрезает верхнюю дублирующую часть current_image."""
    o = max(0, min(overlap_data.overlap_px, current_image.height - 1))
    return current_image.crop((0, o, current_image.width, current_image.height))


def stitch_images(
    images: Sequence[Image.Image],
    *,
    overlaps: Sequence[OverlapData] | None = None,
    config: StitchConfig | None = None,
    expected_overlap_px: int | None = None,
) -> Image.Image:
    """
  Последовательная склейка: первый кадр целиком, остальные без верхнего overlap.
  overlaps[i] соответствует стыку images[i] + images[i+1].
    """
    if not images:
        raise ValueError("stitch_images: empty image list")
    cfg = config or StitchConfig()
    if len(images) == 1:
        return images[0].copy()

    parts: list[Image.Image] = [images[0].copy()]
    overlap_list = list(overlaps or [])

    for i in range(1, len(images)):
        prev = images[i - 1]
        curr = images[i]
        if i - 1 < len(overlap_list):
            od = overlap_list[i - 1]
        else:
            od = find_overlap(
                prev,
                curr,
                expected_overlap_px=expected_overlap_px,
                search_ratio=cfg.search_ratio,
                exclude_top_ratio=cfg.exclude_top_ratio,
                min_confidence=cfg.min_confidence,
                overlap_step=cfg.overlap_step,
            )
        parts.append(crop_duplicate_part(curr, od))
    widths = {p.width for p in parts}
    if len(widths) != 1:
        target_w = max(widths)
        parts = [
            p.resize((target_w, int(p.height * target_w / p.width)), Image.Resampling.LANCZOS)
            if p.width != target_w
            else p
            for p in parts
        ]
    total_h = sum(p.height for p in parts)
    out = Image.new("RGB", (parts[0].width, total_h))
    y = 0
    for part in parts:
        out.paste(part, (0, y))
        y += part.height
    return out


def finalize_long_screenshot(
    stitched: Image.Image,
    metrics: PageMetrics | None = None,
    *,
    last_scroll_y: float | None = None,
) -> Image.Image:
    """
  Обрезка низа по фактической высоте контента; без пустой области в конце.
    """
    if metrics is None:
        return stitched

    dpr = metrics.device_pixel_ratio
    full_h_px = int(round(metrics.scroll_height * dpr))

    if last_scroll_y is not None:
        last_visible_bottom = int(round((last_scroll_y + metrics.client_height) * dpr))
        target_h = min(full_h_px, last_visible_bottom, stitched.height)
    else:
        target_h = min(full_h_px, stitched.height)

    target_h = max(1, min(target_h, stitched.height))
    if target_h < stitched.height:
        return stitched.crop((0, 0, stitched.width, target_h))
    return stitched


# --- Capture orchestration ----------------------------------------------------

async def _capture_loop(
    page: Page,
    cfg: StitchConfig,
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
) -> CaptureState:
    if cfg.hide_fixed_elements:
        hidden = await hide_fixed_elements(page)
        LOG.info("Hidden fixed/sticky elements: %d", hidden)

    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(cfg_scroll_settle_ms(cfg))

    state = CaptureState(metrics=await async_get_page_metrics(page))
    expected_overlap_px = int(round(
        state.metrics.viewport_height
        * (1.0 - cfg.scroll_step_ratio)
        * state.metrics.device_pixel_ratio
    ))

    prev_scroll_y = -1.0
    for frame_idx in range(max_frames):
        metrics = await async_get_page_metrics(page)
        state.metrics = metrics
        state.scroll_positions.append(metrics.scroll_y)

        frame = await capture_viewport(page)
        state.frames.append(frame)
        LOG.info(
            "Frame %d: scrollY=%.0f / %.0f, shot=%dx%d",
            frame_idx + 1,
            metrics.scroll_y,
            metrics.max_scroll_y,
            frame.width,
            frame.height,
        )

        at_bottom = metrics.scroll_y >= metrics.max_scroll_y - 0.5
        if at_bottom:
            LOG.info("Reached bottom at scrollY=%.0f", metrics.scroll_y)
            break

        _, new_scroll_y = await scroll_to_next_position(
            page,
            metrics,
            scroll_step_ratio=cfg.scroll_step_ratio,
            settle_ms=cfg_scroll_settle_ms(cfg),
        )

        if abs(new_scroll_y - metrics.scroll_y) < 0.5:
            LOG.warning("scrollY unchanged (%.0f) — stopping", new_scroll_y)
            state.warnings.append(f"scroll stalled at y={new_scroll_y:.0f}")
            break

        if abs(new_scroll_y - prev_scroll_y) < 0.5 and frame_idx > 0:
            LOG.warning("scrollY repeated — infinite loop guard")
            state.warnings.append("infinite loop guard triggered")
            break
        prev_scroll_y = new_scroll_y

    # Overlap между соседними кадрами
    for i in range(1, len(state.frames)):
        od = find_overlap(
            state.frames[i - 1],
            state.frames[i],
            expected_overlap_px=expected_overlap_px,
            search_ratio=cfg.search_ratio,
            exclude_top_ratio=cfg.exclude_top_ratio,
            min_confidence=cfg.min_confidence,
            overlap_step=cfg.overlap_step,
        )
        state.overlaps.append(od)
        if od.method == "fallback":
            state.warnings.append(f"frame {i + 1}: {od.message}")

    if cfg.hide_fixed_elements:
        await restore_fixed_elements(page)

    return state


def cfg_scroll_settle_ms(cfg: StitchConfig) -> int:
    return DEFAULT_SCROLL_SETTLE_MS


async def capture_long_screenshot(
    url: str,
    output: Path,
    *,
    cfg: StitchConfig | None = None,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    headless: bool = True,
    max_frames: int = DEFAULT_MAX_FRAMES,
) -> Path:
    """Полный цикл: метрики → серия кадров → склейка → finalize."""
    if async_playwright is None:
        raise RuntimeError("playwright not installed: pip install playwright && playwright install chromium")

    cfg = cfg or StitchConfig()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={
                "width": viewport_width or 1280,
                "height": viewport_height or 900,
            },
            device_scale_factor=None,
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=120_000)

        state = await _capture_loop(page, cfg, max_frames=max_frames)
        await browser.close()

    stitched = stitch_images(
        state.frames,
        overlaps=state.overlaps,
        config=cfg,
        expected_overlap_px=int(round(
            state.metrics.viewport_height
            * (1.0 - cfg.scroll_step_ratio)
            * state.metrics.device_pixel_ratio
        )),
    )
    last_y = state.scroll_positions[-1] if state.scroll_positions else 0.0
    final = finalize_long_screenshot(stitched, state.metrics, last_scroll_y=last_y)
    final.save(output, format="PNG", optimize=True)
    LOG.info("Saved %s (%dx%d)", output, final.width, final.height)
    for w in state.warnings:
        LOG.warning("Capture warning: %s", w)
    return output


# --- Stitch from folder (без браузера) --------------------------------------

_FRAME_RE = re.compile(r"(\d+)")


def _natural_sort_key(path: Path) -> tuple:
    m = _FRAME_RE.search(path.stem)
    return (int(m.group(1)) if m else 0, path.name.lower())


def load_frame_sequence(folder: Path) -> list[Image.Image]:
    folder = folder.resolve()
    files = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
        key=_natural_sort_key,
    )
    if not files:
        raise FileNotFoundError(f"No images in {folder}")
    return [Image.open(p).convert("RGB") for p in files]


def stitch_folder(
    folder: Path,
    output: Path,
    *,
    cfg: StitchConfig | None = None,
    viewport_height: int | None = None,
    device_pixel_ratio: float = 1.0,
) -> Path:
    """Склейка готовой серии скриншотов из папки."""
    cfg = cfg or StitchConfig()
    images = load_frame_sequence(folder)
    vh = viewport_height or images[0].height
    expected_overlap = int(round(vh * (1.0 - cfg.scroll_step_ratio) * device_pixel_ratio))

    overlaps: list[OverlapData] = []
    for i in range(1, len(images)):
        overlaps.append(
            find_overlap(
                images[i - 1],
                images[i],
                expected_overlap_px=expected_overlap,
                search_ratio=cfg.search_ratio,
                exclude_top_ratio=cfg.exclude_top_ratio,
                min_confidence=cfg.min_confidence,
                overlap_step=cfg.overlap_step,
            )
        )

    stitched = stitch_images(images, overlaps=overlaps, config=cfg)
    metrics = PageMetrics(
        viewport_width=images[0].width,
        viewport_height=vh,
        device_pixel_ratio=device_pixel_ratio,
        scroll_y=0.0,
        scroll_height=vh * len(images) * cfg.scroll_step_ratio / max(cfg.scroll_step_ratio, 0.01),
        client_height=vh,
    )
    final = finalize_long_screenshot(stitched, metrics)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    final.save(output, format="PNG", optimize=True)
    LOG.info("Stitched %d frames -> %s (%dx%d)", len(images), output, final.width, final.height)
    return output


# --- CLI ----------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Надёжная склейка длинного скриншота (viewport overlap)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="Захват URL через Playwright")
    cap.add_argument("url")
    cap.add_argument("-o", "--output", type=Path, required=True)
    cap.add_argument("--width", type=int, default=1280)
    cap.add_argument("--height", type=int, default=900)
    cap.add_argument("--scroll-ratio", type=float, default=DEFAULT_SCROLL_STEP_RATIO)
    cap.add_argument("--no-hide-fixed", action="store_true")
    cap.add_argument("--headed", action="store_true")

    st = sub.add_parser("stitch", help="Склейка кадров из папки")
    st.add_argument("folder", type=Path)
    st.add_argument("-o", "--output", type=Path, required=True)
    st.add_argument("--viewport-height", type=int, default=None)
    st.add_argument("--dpr", type=float, default=1.0)
    st.add_argument("--scroll-ratio", type=float, default=DEFAULT_SCROLL_STEP_RATIO)

    ov = sub.add_parser("overlap", help="Отладка overlap между двумя PNG")
    ov.add_argument("previous")
    ov.add_argument("current")
    ov.add_argument("--expected", type=int, default=None)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    cfg = StitchConfig(
        scroll_step_ratio=getattr(args, "scroll_ratio", DEFAULT_SCROLL_STEP_RATIO),
        hide_fixed_elements=not getattr(args, "no_hide_fixed", False),
    )

    if args.command == "capture":
        asyncio.run(
            capture_long_screenshot(
                args.url,
                args.output,
                cfg=cfg,
                viewport_width=args.width,
                viewport_height=args.height,
                headless=not args.headed,
            )
        )
        return 0

    if args.command == "stitch":
        stitch_folder(
            args.folder,
            args.output,
            cfg=cfg,
            viewport_height=args.viewport_height,
            device_pixel_ratio=args.dpr,
        )
        return 0

    if args.command == "overlap":
        prev = Image.open(args.previous).convert("RGB")
        curr = Image.open(args.current).convert("RGB")
        od = find_overlap(prev, curr, expected_overlap_px=args.expected)
        print(f"overlap_px={od.overlap_px} confidence={od.confidence:.3f} method={od.method}")
        print(od.message)
        return 0

    return 1


# Публичные алиасы в стиле camelCase (для совместимости с ТЗ) -----------------
getPageMetrics = async_get_page_metrics
captureViewport = capture_viewport
scrollToNextPosition = scroll_to_next_position
findOverlap = find_overlap
cropDuplicatePart = crop_duplicate_part
stitchImages = stitch_images
finalizeLongScreenshot = finalize_long_screenshot


if __name__ == "__main__":
    raise SystemExit(main())
