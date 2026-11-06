"""End-to-end: files (images or PDF) -> PNG pages -> LLM -> clean Menu."""

import io
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from .llm import MenuLLM
from .postprocess import merge_menus
from .schema import Menu

MAX_SIDE = 2000  # px; enough for small print, keeps requests fast and cheap
PDF_SCALE = 2.0  # ~144 dpi


@dataclass
class ExtractionResult:
    menu: Menu
    pages: int
    seconds: float


def image_to_png(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")  # fixes rotated phone photos
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def pdf_to_pngs(path: Path) -> list[bytes]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    return [image_to_png(page.render(scale=PDF_SCALE).to_pil()) for page in pdf]


def load_pages(paths: list[str | Path]) -> list[bytes]:
    pages: list[bytes] = []
    for path in map(Path, paths):
        if path.suffix.lower() == ".pdf":
            pages += pdf_to_pngs(path)
        else:
            with Image.open(path) as image:
                pages.append(image_to_png(image))
    return pages


def extract_menu(paths: list[str | Path], llm: MenuLLM) -> ExtractionResult:
    start = time.perf_counter()
    pages = load_pages(paths)
    raw_pages = [llm.extract(page) for page in pages]
    return ExtractionResult(
        menu=merge_menus(raw_pages),
        pages=len(pages),
        seconds=time.perf_counter() - start,
    )
