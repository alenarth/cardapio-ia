from menu_extractor.postprocess import merge_menus
from menu_extractor.schema import LlmItem, LlmMenu, LlmVariation


def item(name, price="R$ 10,00", category="Lanches", variations=None):
    return LlmItem(name=name, description=None, category=category,
                   price_text=price, variations=variations or [])


def test_parses_prices_and_normalizes_category():
    menu = merge_menus([LlmMenu(restaurant_name="Teste", items=[item("X-Burger", "R$ 25,90", "  LANCHES ")])])
    assert menu.items[0].price == 25.9
    assert menu.items[0].category == "Lanches"
    assert menu.items[0].warnings == []


def test_flags_missing_and_suspicious_prices():
    menu = merge_menus([LlmMenu(restaurant_name=None, items=[item("A", None), item("B", "R$ 9.999,00")])])
    assert "preço não encontrado" in menu.items[0].warnings[0]
    assert "preço suspeito" in menu.items[1].warnings[0]


def test_variations_are_parsed_and_checked():
    sizes = [LlmVariation(name="Broto", price_text="R$ 30,00"), LlmVariation(name="Grande", price_text=None)]
    menu = merge_menus([LlmMenu(restaurant_name=None, items=[item("Calabresa", None, "Pizzas", sizes)])])
    pizza = menu.items[0]
    assert [v.price for v in pizza.variations] == [30.0, None]
    assert len(pizza.warnings) == 1  # only the missing size price, not the item price
    assert [r["item"] for r in menu.to_rows()] == ["Calabresa (Broto)", "Calabresa (Grande)"]


def test_merges_pages_and_drops_duplicates():
    page1 = LlmMenu(restaurant_name=None, items=[item("Coca lata", category="Bebidas")])
    page2 = LlmMenu(restaurant_name="Bar do Zé", items=[item("Coca  lata", category="bebidas"), item("Suco")])
    menu = merge_menus([page1, page2])
    assert menu.restaurant_name == "Bar do Zé"
    assert [i.name for i in menu.items] == ["Coca lata", "Suco"]
    assert any("duplicado" in w for w in menu.warnings)


def test_warns_on_empty_menu():
    assert merge_menus([LlmMenu(restaurant_name=None, items=[])]).warnings
