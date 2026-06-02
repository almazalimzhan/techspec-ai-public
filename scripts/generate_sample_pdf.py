"""Generate a synthetic PDF technical specification for local demos."""

from __future__ import annotations

from pathlib import Path
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_TEXT = PROJECT_ROOT / "data" / "sample" / "sample_tech_spec_ru.txt"
OUTPUT_PDF = PROJECT_ROOT / "data" / "sample" / "sample_tech_spec_ru.pdf"

FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)


def find_font_file() -> Path | None:
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    return None


def wrap_text(text: str, width: int = 88) -> list[str]:
    lines: list[str] = []
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]

    for paragraph in paragraphs:
        lines.extend(textwrap.wrap(paragraph, width=width, replace_whitespace=False))
        lines.append("")

    return lines


def paginate_lines(lines: list[str], max_lines: int = 52) -> list[list[str]]:
    pages: list[list[str]] = []
    for start in range(0, len(lines), max_lines):
        pages.append(lines[start : start + max_lines])

    return pages


def main() -> None:
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit(
            "PyMuPDF is required. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    text = SOURCE_TEXT.read_text(encoding="utf-8")
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    font_file = find_font_file()
    font_name = "DemoSans" if font_file else "helv"

    for page_lines in paginate_lines(wrap_text(text)):
        page = doc.new_page(width=595, height=842)
        if font_file:
            page.insert_font(fontname=font_name, fontfile=str(font_file))

        y = 54
        for line in page_lines:
            if line:
                page.insert_text(
                    (48, y),
                    line,
                    fontsize=10.5,
                    fontname=font_name,
                    color=(0, 0, 0),
                )
            y += 14

    if OUTPUT_PDF.exists():
        OUTPUT_PDF.unlink()

    doc.save(OUTPUT_PDF)
    print(f"Generated {OUTPUT_PDF.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
