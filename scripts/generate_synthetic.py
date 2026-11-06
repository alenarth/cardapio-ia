"""Generate synthetic menu images with a known ground truth.

Why: to measure the extractor we need menus whose correct answer we know.
Rendering them ourselves gives perfect labels for free, with varied layouts,
fonts, price formats and "phone photo" noise. Real photos (labeled by hand)
should be added to data/real/ to complement this set.

Usage:  python -m scripts.generate_synthetic --n 15 --out data/synthetic
"""

import argparse
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from menu_extractor.schema import Menu, MenuItem, Variation

FONT_DIRS = [
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("C:/Windows/Fonts"),
    Path("/Library/Fonts"),
]
FONT_FILES = {
    "sans": ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"],
    "sans_bold": ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"],
    "serif": ["DejaVuSerif.ttf", "times.ttf", "Times New Roman.ttf"],
    "serif_bold": ["DejaVuSerif-Bold.ttf", "timesbd.ttf", "Times New Roman Bold.ttf"],
    "condensed": ["DejaVuSansCondensed.ttf", "arialn.ttf", "Arial Narrow.ttf"],
}

RESTAURANTS = {
    "Pizzaria": {
        "names": ["Pizzaria Bella Napoli", "Forno da Vila", "Pizzaria do Largo"],
        "sections": {
            "Pizzas salgadas": ["Margherita", "Calabresa", "Portuguesa", "Frango com Catupiry",
                                "Quatro Queijos", "Napolitana", "Marguerita Especial", "Pepperoni"],
            "Pizzas doces": ["Chocolate com Morango", "Romeu e Julieta", "Banana com Canela"],
            "Bebidas": ["Refrigerante lata", "Guaraná 2L", "Suco natural 500 ml", "Água sem gás"],
        },
        "sizes": ["Broto", "Média", "Grande"],
    },
    "Hamburgueria": {
        "names": ["Burger Brasa", "Smash do Bairro", "Chapa Quente"],
        "sections": {
            "Burgers": ["Clássico", "Cheddar Bacon", "Smash Duplo", "Veggie de Grão-de-bico",
                        "Costela BBQ", "Salada Burger"],
            "Acompanhamentos": ["Batata frita", "Onion rings", "Batata rústica", "Nuggets (8 un.)"],
            "Bebidas": ["Refrigerante lata", "Milkshake de baunilha", "Chá gelado", "Água com gás"],
        },
        "sizes": None,
    },
    "Japonês": {
        "names": ["Sushi Kazoku", "Temakeria Oishii", "Sakura Sushi"],
        "sections": {
            "Temakis": ["Temaki salmão", "Temaki skin", "Temaki califórnia", "Temaki atum"],
            "Combinados": ["Combinado 15 peças", "Combinado 30 peças", "Combo Hot Roll"],
            "Pratos quentes": ["Yakisoba de frango", "Lámen tradicional", "Guioza (6 un.)"],
            "Bebidas": ["Chá verde", "Refrigerante lata", "Água sem gás"],
        },
        "sizes": None,
    },
    "Marmitaria": {
        "names": ["Cozinha da Dona Lúcia", "Marmita Caseira RJ", "Sabor de Casa"],
        "sections": {
            "Pratos do dia": ["Frango grelhado", "Bife acebolado", "Feijoada completa",
                              "Strogonoff de frango", "Peixe empanado", "Escondidinho de carne"],
            "Sobremesas": ["Pudim", "Mousse de maracujá", "Brigadeiro de colher"],
            "Bebidas": ["Suco de laranja", "Refrigerante lata", "Água"],
        },
        "sizes": ["P", "M", "G"],
    },
    "Açaí": {
        "names": ["Açaí da Praia", "Point do Açaí", "Tropical Açaí"],
        "sections": {
            "Açaí": ["Açaí tradicional", "Açaí com banana", "Açaí Nutella", "Açaí fitness"],
            "Complementos": ["Granola", "Leite em pó", "Paçoca", "Morango", "Leite condensado"],
        },
        "sizes": ["300 ml", "500 ml", "700 ml"],
    },
}

SECTION_PRICES = {
    "Bebidas": (4, 14), "Complementos": (2, 6), "Sobremesas": (8, 18),
    "Acompanhamentos": (12, 28), "Temakis": (22, 40), "Combinados": (45, 119),
    "Pratos quentes": (28, 48), "Burgers": (26, 45), "Pratos do dia": (18, 32),
    "Pizzas salgadas": (32, 50), "Pizzas doces": (34, 48), "Açaí": (12, 18),
}

DESCRIPTIONS = ["Feito na hora", "Sugestão da casa", "Receita tradicional",
                "Ingredientes selecionados", None, None, None]
EXTRA_LINES = ["Delivery: (21) 9{0}{0}{1}{1}-{2}{2}{3}{3}", "Aberto de terça a domingo, 18h às 23h",
               "Rua das Laranjeiras, {0}{1}{2}", "Siga @{name}"]


def load_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for directory in FONT_DIRS:
        for filename in FONT_FILES[kind]:
            path = directory / filename
            if path.exists():
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def format_price(value: float, style: int) -> str:
    br = f"{value:.2f}".replace(".", ",")
    return [f"R$ {br}", br, f"R${br}", f"{value:.2f}", f"R$ {br}"][style]


def random_price(rng: random.Random, low: float, high: float) -> float:
    return round(rng.uniform(low, high)) + rng.choice([0.0, 0.5, 0.9, 0.99])


def build_truth(rng: random.Random) -> Menu:
    kind = rng.choice(list(RESTAURANTS))
    spec = RESTAURANTS[kind]
    items: list[MenuItem] = []
    for section, names in spec["sections"].items():
        for name in rng.sample(names, k=rng.randint(max(2, len(names) - 3), len(names))):
            low, high = SECTION_PRICES[section]
            sized = spec["sizes"] and section not in ("Bebidas", "Complementos", "Sobremesas") and rng.random() < 0.8
            if sized:
                base = random_price(rng, low, high)
                variations = [Variation(name=s, price=round(base + i * rng.choice([6, 8, 10]), 2))
                              for i, s in enumerate(spec["sizes"])]
                items.append(MenuItem(name=name, category=section, variations=variations,
                                      description=rng.choice(DESCRIPTIONS)))
            else:
                items.append(MenuItem(name=name, category=section,
                                      price=random_price(rng, low, high),
                                      description=rng.choice(DESCRIPTIONS)))
    return Menu(restaurant_name=rng.choice(spec["names"]), items=items)


def render(menu: Menu, rng: random.Random) -> Image.Image:
    family = rng.choice(["sans", "serif", "condensed"])
    bold = "serif_bold" if family == "serif" else "sans_bold"
    title_font, section_font = load_font(bold, 54), load_font(bold, 34)
    item_font, small_font = load_font(family, 26), load_font(family, 20)
    price_style = rng.randrange(5)
    leader = rng.random() < 0.5
    columns = rng.choice([1, 2])
    bg = rng.choice(["#fffaf0", "#ffffff", "#f6efe2", "#1f1f1f", "#fff4e0"])
    fg = "#f2f2f2" if bg == "#1f1f1f" else "#1d1d1d"
    accent = rng.choice(["#b3261e", "#0b6e4f", "#8a4b08", "#c2185b", "#1565c0"])

    width = 1400 if columns == 2 else 900
    col_width = (width - 120) // columns
    image = Image.new("RGB", (width, 4000), bg)
    draw = ImageDraw.Draw(image)
    draw.text((width // 2, 50), menu.restaurant_name, font=title_font, fill=accent, anchor="mt")

    sections: dict[str, list[MenuItem]] = {}
    for item in menu.items:
        sections.setdefault(item.category, []).append(item)

    col, y_start = 0, 150
    y = y_start
    heights = []
    section_list = list(sections.items())
    split = (len(section_list) + 1) // 2 if columns == 2 else len(section_list)
    for index, (section, items) in enumerate(section_list):
        if columns == 2 and index == split:
            heights.append(y)
            col, y = 1, y_start
        x0 = 60 + col * col_width
        x1 = x0 + col_width - 30
        draw.text((x0, y), section.upper(), font=section_font, fill=accent)
        y += 50
        for item in items:
            if item.variations:
                draw.text((x0, y), item.name, font=item_font, fill=fg)
                y += 34
                sizes = "   ".join(f"{v.name}: {format_price(v.price, price_style)}" for v in item.variations)
                draw.text((x0 + 20, y), sizes, font=small_font, fill=fg)
                y += 30
            else:
                price = format_price(item.price, price_style)
                baseline = y + 26
                draw.text((x0, baseline), item.name, font=item_font, fill=fg, anchor="ls")
                pw = draw.textlength(price, font=item_font)
                draw.text((x1 - pw, baseline), price, font=item_font, fill=fg, anchor="ls")
                if leader:
                    nw = draw.textlength(item.name, font=item_font)
                    dots_x = x0 + nw + 10
                    while dots_x < x1 - pw - 15:
                        draw.text((dots_x, baseline), ".", font=item_font, fill=fg, anchor="ls")
                        dots_x += 10
                y += 34
            if item.description:
                draw.text((x0 + 20, y), item.description, font=small_font, fill="#888888")
                y += 28
            y += 8
        y += 25
    heights.append(y)
    y = max(heights) + 20
    footer = rng.choice(EXTRA_LINES).format(*[rng.randint(0, 9) for _ in range(4)],
                                             name=menu.restaurant_name.lower().replace(" ", ""))
    draw.text((width // 2, y), footer, font=small_font, fill=fg, anchor="mt")
    image = image.crop((0, 0, width, y + 70))
    return photo_effect(image, rng, bg)


def photo_effect(image: Image.Image, rng: random.Random, bg: str) -> Image.Image:
    """Mild rotation, blur and noise, like a phone photo of a printed menu."""
    if rng.random() < 0.6:
        image = image.rotate(rng.uniform(-3, 3), expand=True, fillcolor="#9e9e9e")
    if rng.random() < 0.5:
        image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.0)))
    if rng.random() < 0.5:
        noise = Image.effect_noise(image.size, rng.uniform(8, 20)).convert("RGB")
        image = Image.blend(image, noise, 0.06)
    return image


def generate(n: int = 15, out: str | Path = "data/synthetic", seed: int = 42) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    for i in range(1, n + 1):
        truth = build_truth(rng)
        render(truth, rng).save(out / f"menu_{i:02d}.jpg", quality=85)
        (out / f"menu_{i:02d}.json").write_text(
            json.dumps(truth.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=15)
    parser.add_argument("--out", default="data/synthetic")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.n, args.out, args.seed)
    print(f"{args.n} cardápios gerados em {args.out}/")


if __name__ == "__main__":
    main()
