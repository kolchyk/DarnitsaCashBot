from services.rules_engine.matcher import is_receipt_eligible


def test_is_receipt_eligible_true():
    catalog = {"SKU1": ["darnitsa", "citramon"]}
    items = [{"name": "Citramon Darnitsa 20 tablets"}]
    assert is_receipt_eligible(catalog, items)


def test_is_receipt_eligible_false():
    catalog = {"SKU1": ["darnitsa"]}
    items = [{"name": "Vitamin C"}]
    assert not is_receipt_eligible(catalog, items)

