from menu_extractor.evaluation import score_menu
from menu_extractor.schema import Menu, MenuItem


def menu(*items):
    return Menu(items=[MenuItem(name=n, price=p, category=c) for n, p, c in items])


def test_perfect_match():
    truth = menu(("Pudim", 9.9, "Sobremesas"), ("Água", 4.0, "Bebidas"))
    scores = score_menu(truth, truth)
    assert scores.f1 == 1.0 and scores.price_accuracy == 1.0 and scores.category_accuracy == 1.0


def test_accent_and_case_insensitive_names():
    truth = menu(("Açaí tradicional", 15.0, "Açaí"))
    pred = menu(("ACAI TRADICIONAL", 15.0, "acai"))
    assert score_menu(pred, truth).matched == 1


def test_counts_missed_invented_and_wrong_price():
    truth = menu(("Pudim", 9.9, "Sobremesas"), ("Água", 4.0, "Bebidas"))
    pred = menu(("Pudim", 8.9, "Sobremesas"), ("Pastel de vento", 5.0, "Salgados"))
    scores = score_menu(pred, truth)
    assert scores.matched == 1
    assert scores.precision == 0.5 and scores.recall == 0.5
    assert scores.price_accuracy == 0.0
