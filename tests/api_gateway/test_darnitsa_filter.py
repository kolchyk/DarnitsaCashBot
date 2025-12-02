from types import SimpleNamespace

from apps.api_gateway.routes.bot import _filter_darnitsa_products


def _make_line_item(name: str, price_kopecks: int, quantity: int = 1):
    return SimpleNamespace(product_name=name, unit_price=price_kopecks, quantity=quantity)


def test_filter_darnitsa_products_returns_prefix_matches_only():
    ocr_payload = {
        "line_items": [
            {
                "name": "Дарниця Цитрамон",
                "original_name": "Дарниця Цитрамон",
                "normalized_name": "DARNITSA CITRAMON",
                "is_darnitsa": True,
            },
            {
                "name": "Вітамін С (Дарниця)",
                "original_name": "Вітамін С (Дарниця)",
                "normalized_name": "VITAMIN S (DARNITSA)",
                "is_darnitsa": False,
            },
        ]
    }
    line_items = [
        _make_line_item("Дарниця Цитрамон", 1050, 1),
        _make_line_item("Вітамін С (Дарниця)", 2500, 1),
    ]

    result = _filter_darnitsa_products(line_items, ocr_payload)

    assert len(result) == 1
    assert result[0].name == "Дарниця Цитрамон"
    assert result[0].price == 10.5


def test_filter_darnitsa_products_works_without_ocr_entry():
    ocr_payload = {"line_items": []}
    line_items = [
        _make_line_item("Дарниця Но-Шпа", 1525, 2),
        _make_line_item("Цитрамон", 900, 1),
    ]

    result = _filter_darnitsa_products(line_items, ocr_payload)

    assert len(result) == 1
    assert result[0].name == "Дарниця Но-Шпа"
    assert result[0].quantity == 2

