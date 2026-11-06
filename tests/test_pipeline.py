"""End-to-end with a fake LLM: no API key or network needed."""

import json
from pathlib import Path

import pytest

from menu_extractor.evaluation import score_menu
from menu_extractor.pipeline import extract_menu
from menu_extractor.schema import LlmItem, LlmMenu, LlmVariation, Menu



@pytest.fixture(scope="module")
def sample(tmp_path_factory) -> Path:
    """Generate 1 synthetic menu (image + ground truth) for the tests."""
    from scripts.generate_synthetic import generate

    folder = tmp_path_factory.mktemp("synthetic")
    generate(n=1, out=folder, seed=42)
    return folder / "menu_01"


class PerfectFakeLLM:
    """Returns the ground truth formatted as the LLM would (prices as text)."""

    def __init__(self, truth: Menu):
        self.truth = truth
        self.calls = 0

    def extract(self, image_png: bytes) -> LlmMenu:
        assert image_png.startswith(b"\x89PNG")
        self.calls += 1
        return LlmMenu(restaurant_name=self.truth.restaurant_name, items=[
            LlmItem(
                name=i.name, description=i.description, category=i.category,
                price_text=None if i.price is None else f"R$ {i.price:.2f}".replace(".", ","),
                variations=[LlmVariation(name=v.name, price_text=f"{v.price:.2f}") for v in i.variations],
            )
            for i in self.truth.items
        ])


def test_pipeline_with_perfect_llm_scores_100(sample):
    truth = Menu.model_validate(json.loads(sample.with_suffix(".json").read_text(encoding="utf-8")))
    llm = PerfectFakeLLM(truth)
    result = extract_menu([sample.with_suffix(".jpg")], llm)
    scores = score_menu(result.menu, truth)
    assert llm.calls == 1 and result.pages == 1
    assert scores.f1 == 1.0 and scores.price_accuracy == 1.0 and scores.category_accuracy == 1.0


def test_pdf_pages_become_png_images(tmp_path, sample):
    from PIL import Image

    from menu_extractor.pipeline import load_pages

    pdf = tmp_path / "menu.pdf"
    page = Image.open(sample.with_suffix(".jpg")).convert("RGB")
    page.save(pdf, save_all=True, append_images=[page])  # 2-page PDF
    pages = load_pages([pdf])
    assert len(pages) == 2 and all(p.startswith(b"\x89PNG") for p in pages)
