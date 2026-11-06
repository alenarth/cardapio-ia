"""Turn the raw LLM answer into a clean, validated Menu.

Every rule here exists because the LLM can be wrong. Instead of trusting
the output blindly, we normalize it and attach warnings that a human
reviewer can act on.
"""

from .prices import parse_price
from .schema import LlmMenu, Menu, MenuItem, Variation

MIN_PRICE = 0.5
MAX_PRICE = 1000.0
DEFAULT_CATEGORY = "Sem categoria"


def normalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(text.split())
    return cleaned or None


def normalize_category(category: str | None) -> str:
    cleaned = normalize_text(category)
    if not cleaned:
        return DEFAULT_CATEGORY
    return cleaned[0].upper() + cleaned[1:].lower()


def price_warnings(price: float | None, label: str) -> list[str]:
    if price is None:
        return [f"{label}: preço não encontrado"]
    if not MIN_PRICE <= price <= MAX_PRICE:
        return [f"{label}: preço suspeito (R$ {price:.2f})"]
    return []


def build_item(raw) -> MenuItem:
    name = normalize_text(raw.name) or "(sem nome)"
    variations = [
        Variation(name=normalize_text(v.name) or "?", price=parse_price(v.price_text))
        for v in raw.variations
    ]
    price = parse_price(raw.price_text)

    warnings: list[str] = []
    if variations:
        for variation in variations:
            warnings += price_warnings(variation.price, variation.name)
    else:
        warnings += price_warnings(price, "item")

    return MenuItem(
        name=name,
        description=normalize_text(raw.description),
        category=normalize_category(raw.category),
        price=price,
        variations=variations,
        warnings=warnings,
    )


def merge_menus(pages: list[LlmMenu]) -> Menu:
    """Combine pages (multi-photo or multi-page PDF) into one menu."""
    restaurant = next((p.restaurant_name for p in pages if p.restaurant_name), None)
    items: list[MenuItem] = []
    seen: dict[tuple[str, str], int] = {}
    warnings: list[str] = []

    for page in pages:
        for raw in page.items:
            item = build_item(raw)
            key = (item.category.lower(), item.name.lower())
            if key in seen:
                warnings.append(f"Item duplicado ignorado: {item.name}")
                continue
            seen[key] = len(items)
            items.append(item)

    if not items:
        warnings.append("Nenhum item encontrado. A imagem é um cardápio legível?")

    return Menu(restaurant_name=normalize_text(restaurant), items=items, warnings=warnings)
