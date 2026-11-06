"""Run the extractor on every labeled menu and report quality metrics.

Each image `X.jpg|png|pdf` needs a ground truth `X.json` next to it
(same format as the app's JSON output).

Usage:
    python -m scripts.evaluate --data data/synthetic
    python -m scripts.evaluate --data data/real --out results/real.csv
"""

import argparse
import csv
import json
import time
from pathlib import Path

from menu_extractor.evaluation import Scores, score_menu
from menu_extractor.llm import GeminiMenuLLM
from menu_extractor.pipeline import extract_menu
from menu_extractor.schema import Menu

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
PAUSE_SECONDS = 4  # stay under free-tier rate limits


def find_cases(folder: Path) -> list[tuple[Path, Path]]:
    cases = []
    for path in sorted(folder.iterdir()):
        truth = path.with_suffix(".json")
        if path.suffix.lower() in EXTENSIONS and truth.exists():
            cases.append((path, truth))
    return cases


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/synthetic")
    parser.add_argument("--out", default="results/synthetic.csv")
    args = parser.parse_args()

    llm = GeminiMenuLLM()
    cases = find_cases(Path(args.data))
    if not cases:
        raise SystemExit(f"Nenhum par imagem + .json encontrado em {args.data}")

    total = Scores(0, 0, 0, 0, 0)
    rows, seconds = [], []
    for image, truth_path in cases:
        truth = Menu.model_validate(json.loads(truth_path.read_text(encoding="utf-8")))
        result = extract_menu([image], llm)
        scores = score_menu(result.menu, truth)
        total += scores
        seconds.append(result.seconds)
        rows.append({
            "arquivo": image.name,
            "itens_reais": scores.true_items,
            "itens_extraidos": scores.predicted_items,
            "precisao": round(scores.precision, 3),
            "recall": round(scores.recall, 3),
            "acerto_preco": round(scores.price_accuracy, 3),
            "acerto_categoria": round(scores.category_accuracy, 3),
            "segundos": round(result.seconds, 1),
        })
        print(f"{image.name}: F1 {pct(scores.f1)} | preço {pct(scores.price_accuracy)} | {result.seconds:.1f}s")
        time.sleep(PAUSE_SECONDS)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print("\n| Métrica | Valor |\n|---|---|")
    print(f"| Cardápios | {len(cases)} |")
    print(f"| Itens no gabarito | {total.true_items} |")
    print(f"| Precisão (itens extraídos que existem) | {pct(total.precision)} |")
    print(f"| Recall (itens reais encontrados) | {pct(total.recall)} |")
    print(f"| F1 | {pct(total.f1)} |")
    print(f"| Preço correto (itens encontrados) | {pct(total.price_accuracy)} |")
    print(f"| Categoria correta (itens encontrados) | {pct(total.category_accuracy)} |")
    print(f"| Tempo médio por cardápio | {sum(seconds) / len(seconds):.1f}s |")
    print(f"\nDetalhes por arquivo: {out}")


if __name__ == "__main__":
    main()
