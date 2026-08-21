from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "store-assets" / "google-play" / "ko-KR"
RAW_ROOT = ASSET_ROOT / "raw"
SCREENSHOT_ROOT = ASSET_ROOT / "screenshots"

STORE_ICON_SOURCE = ROOT / "stockboda-play-icon-512.png"
HEADER_LOGO_SOURCE = ROOT / "frontend" / "src" / "assets" / "brand" / "stockboda-logo-horizontal.png"
WORDMARK_SOURCE = ROOT / "frontend" / "src" / "assets" / "brand" / "stockboda-wordmark.png"

FONT_REGULAR = Path("C:/Windows/Fonts/malgun.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/malgunbd.ttf")

BG = "#070B16"
SURFACE = "#111726"
BORDER = "#2A3650"
TEXT = "#F4F7FF"
MUTED = "#AAB5CA"
BLUE = "#2F6BFF"
CYAN = "#16C7E8"
UP = "#FF5A67"
DOWN = "#4D8CFF"


@dataclass(frozen=True)
class ScreenshotSpec:
    source: str
    output: str
    title: str
    subtitle: str


SCREENSHOTS = (
    ScreenshotSpec(
        "01-theme-ranking.png",
        "01-theme-ranking-1080x1920.png",
        "상승 테마를 한눈에",
        "기간별 테마 흐름과 상승률을 빠르게 확인",
    ),
    ScreenshotSpec(
        "02-theme-stocks.png",
        "02-theme-stocks-1080x1920.png",
        "테마별 종목까지 바로",
        "선택한 테마의 종목과 차트를 한 화면에서",
    ),
    ScreenshotSpec(
        "03-chart-detail.png",
        "03-chart-detail-1080x1920.png",
        "차트를 더 깊게 분석",
        "이평선과 보조지표를 원하는 방식으로 설정",
    ),
    ScreenshotSpec(
        "04-journal-input.png",
        "04-journal-input-1080x1920.png",
        "매매 기록은 간단하게",
        "체결 내역을 기록하고 손익을 자동 계산",
    ),
    ScreenshotSpec(
        "05-ai-review-source.png",
        "05-ai-review-1080x1920.png",
        "AI로 매매를 복기",
        "차트와 체결 시점으로 잘한 점과 개선점을 확인",
    ),
)

def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def resize_cover(image: Image.Image, size: tuple[int, int], *, top_align: bool = False) -> Image.Image:
    target_w, target_h = size
    source_w, source_h = image.size
    scale = max(target_w / source_w, target_h / source_h)
    resized = image.resize((round(source_w * scale), round(source_h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = 0 if top_align else max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def paste_feature_wordmark(image: Image.Image) -> None:
    ImageDraw.Draw(image).rounded_rectangle((326, 74, 662, 188), radius=22, fill="#F8FAFC")
    wordmark = Image.open(WORDMARK_SOURCE).convert("RGBA").resize((300, 100), Image.Resampling.LANCZOS)
    image.paste(wordmark, (344, 81), wordmark)


def paste_screenshot_brand(image: Image.Image) -> None:
    ImageDraw.Draw(image).rounded_rectangle((64, 34, 314, 106), radius=16, fill="#F8FAFC")
    logo = Image.open(HEADER_LOGO_SOURCE).convert("RGBA").resize((216, 72), Image.Resampling.LANCZOS)
    image.paste(logo, (81, 34), logo)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=text_font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    text_font: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    line_height = text_font.size + line_gap
    for line in wrap_text(draw, text, text_font, max_width):
        draw.text((x, y), line, font=text_font, fill=fill)
        y += line_height
    return y


def create_store_icon() -> Path:
    source = Image.open(STORE_ICON_SOURCE).convert("RGBA")
    icon = source.resize((512, 512), Image.Resampling.LANCZOS)
    output = ASSET_ROOT / "icon-512.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    icon.save(output, "PNG", optimize=True)
    return output


def create_feature_graphic(icon_path: Path) -> Path:
    image = Image.new("RGB", (1024, 500), BG)
    draw = ImageDraw.Draw(image)

    for x in range(28, 1024, 64):
        draw.line((x, 0, x, 500), fill="#111827", width=1)
    for y in range(26, 500, 64):
        draw.line((0, y, 1024, y), fill="#111827", width=1)

    draw.rounded_rectangle((46, 70, 288, 312), radius=30, fill="#050817", outline="#1C2C52", width=2)
    icon = Image.open(icon_path).convert("RGB").resize((218, 218), Image.Resampling.LANCZOS)
    image.paste(icon, (58, 82))

    paste_feature_wordmark(image)
    draw.text((336, 196), "테마 흐름부터 매매 복기까지", font=font(36, bold=True), fill=TEXT)
    draw.text((338, 260), "주식 테마 · 차트 · AI 복기", font=font(25), fill=MUTED)

    bars = (42, 70, 54, 96, 82, 136)
    bar_x = 630
    base_y = 424
    for index, height in enumerate(bars):
        color = UP if index in (1, 3, 5) else DOWN
        left = bar_x + index * 48
        draw.rounded_rectangle((left, base_y - height, left + 22, base_y), radius=4, fill=color)

    points = [(620, 395), (675, 358), (724, 375), (785, 306), (845, 328), (930, 222)]
    draw.line(points, fill=CYAN, width=9, joint="curve")
    draw.polygon(((930, 222), (902, 225), (926, 250)), fill=CYAN)

    output = ASSET_ROOT / "feature-graphic-1024x500.png"
    image.save(output, "PNG", optimize=True)
    return output


def clean_source(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    if image.width <= 600:
        crop_right = max(1, image.width - 7)
        target_height = min(image.height, round(crop_right * 16 / 9))
        return image.crop((0, 0, crop_right, target_height))

    crop_right = max(1, image.width - 10)
    target_height = min(image.height, round(crop_right * 16 / 9))
    return image.crop((0, 0, crop_right, target_height))


def create_store_screenshot(spec: ScreenshotSpec, icon_path: Path) -> Path:
    source_path = RAW_ROOT / spec.source
    source = clean_source(Image.open(source_path))
    app_screen = resize_cover(source, (900, 1600), top_align=True)

    canvas = Image.new("RGB", (1080, 1920), BG)
    draw = ImageDraw.Draw(canvas)

    paste_screenshot_brand(canvas)
    draw.text((72, 112), spec.title, font=font(58, bold=True), fill=TEXT)
    draw.text((74, 200), spec.subtitle, font=font(29), fill=MUTED)

    mask = rounded_mask((900, 1600), 28)
    canvas.paste(app_screen, (90, 300), mask)
    draw.rounded_rectangle((89, 299, 990, 1900), radius=29, outline=BORDER, width=3)

    output = SCREENSHOT_ROOT / spec.output
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG", optimize=True)
    return output


def create_contact_sheet(icon_path: Path, feature_path: Path, screenshots: list[Path]) -> Path:
    sheet = Image.new("RGB", (1800, 1180), "#EEF2F8")
    draw = ImageDraw.Draw(sheet)
    draw.text((50, 34), "StockBoda · Google Play 등록 이미지", font=font(42, bold=True), fill="#111827")

    icon = Image.open(icon_path).convert("RGB").resize((220, 220), Image.Resampling.LANCZOS)
    sheet.paste(icon, (52, 112))
    feature = Image.open(feature_path).convert("RGB").resize((1024, 500), Image.Resampling.LANCZOS)
    sheet.paste(feature, (324, 112))

    thumb_w, thumb_h = 270, 480
    for index, screenshot_path in enumerate(screenshots):
        shot = Image.open(screenshot_path).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = 52 + index * 344
        y = 430
        sheet.paste(shot, (x, y))
        draw.rectangle((x - 1, y - 1, x + thumb_w, y + thumb_h), outline="#CBD5E1", width=2)

    draw.text((52, 958), "앱 이름", font=font(25, bold=True), fill="#475569")
    draw.text((52, 1002), "스톡보다", font=font(38, bold=True), fill="#111827")
    draw.text((52, 1068), "스토어 아이콘 512×512 · 대표 그래픽 1024×500 · 휴대전화 스크린샷 1080×1920", font=font(24), fill="#64748B")

    output = ASSET_ROOT / "preview-contact-sheet.png"
    sheet.save(output, "PNG", optimize=True)
    return output


def main() -> None:
    missing = [RAW_ROOT / spec.source for spec in SCREENSHOTS if not (RAW_ROOT / spec.source).exists()]
    if missing:
        missing_text = "\n".join(str(path) for path in missing)
        raise SystemExit(f"Missing raw screenshots:\n{missing_text}")

    SCREENSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    icon_path = create_store_icon()
    feature_path = create_feature_graphic(icon_path)
    screenshots = [create_store_screenshot(spec, icon_path) for spec in SCREENSHOTS]
    preview_path = create_contact_sheet(icon_path, feature_path, screenshots)

    for path in (icon_path, feature_path, *screenshots, preview_path):
        with Image.open(path) as image:
            print(f"{path.relative_to(ROOT)}: {image.width}x{image.height} {image.mode}")


if __name__ == "__main__":
    main()
