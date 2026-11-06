"""Compare an extracted menu with a hand-checked ground truth.

Items are matched by name similarity (accent/case-insensitive). On matched
pairs we check price and category. Unmatched predictions count as false
positives (invented items), unmatched truth as false negatives (missed items).
"""

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .postprocess import normalize_category
from .schema import Menu

NAME_THRESHOLD = 0.85


def simplify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.replace("-", " ").split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, simplify(a), simplify(b)).ratio()


@dataclass
class Scores:
    true_items: int
    predicted_items: int
    matched: int
    correct_prices: int
    correct_categories: int

    @property
    def precision(self) -> float:
        return self.matched / self.predicted_items if self.predicted_items else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.true_items if self.true_items else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def price_accuracy(self) -> float:
        return self.correct_prices / self.matched if self.matched else 0.0

    @property
    def category_accuracy(self) -> float:
        return self.correct_categories / self.matched if self.matched else 0.0

    def __add__(self, other: "Scores") -> "Scores":
        return Scores(
            self.true_items + other.true_items,
            self.predicted_items + other.predicted_items,
            self.matched + other.matched,
            self.correct_prices + other.correct_prices,
            self.correct_categories + other.correct_categories,
        )


def _flatten(menu: Menu) -> list[tuple[str, float | None, str]]:
    return [(row["item"], row["preco"], row["categoria"]) for row in menu.to_rows()]


def score_menu(predicted: Menu, truth: Menu) -> Scores:
    pred_rows, true_rows = _flatten(predicted), _flatten(truth)

    # Greedy matching: best-scoring pairs first, each row used at most once.
    candidates = sorted(
        (
            (similarity(p[0], t[0]), i, j)
            for i, p in enumerate(pred_rows)
            for j, t in enumerate(true_rows)
        ),
        reverse=True,
    )
    used_pred, used_true = set(), set()
    matched = correct_prices = correct_categories = 0
    for sim, i, j in candidates:
        if sim < NAME_THRESHOLD:
            break
        if i in used_pred or j in used_true:
            continue
        used_pred.add(i)
        used_true.add(j)
        matched += 1
        p_price, t_price = pred_rows[i][1], true_rows[j][1]
        if p_price is not None and t_price is not None and abs(p_price - t_price) < 0.01:
            correct_prices += 1
        if simplify(normalize_category(pred_rows[i][2])) == simplify(normalize_category(true_rows[j][2])):
            correct_categories += 1

    return Scores(len(true_rows), len(pred_rows), matched, correct_prices, correct_categories)
