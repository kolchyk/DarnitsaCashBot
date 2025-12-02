from libs.common.darnitsa import has_darnitsa_prefix


def test_has_darnitsa_prefix_cyrillic():
    assert has_darnitsa_prefix("Дарниця Цитрамон")
    assert has_darnitsa_prefix("Дарниця-Цитрамон")
    assert not has_darnitsa_prefix("ТОВ «Дарниця Фармацевтична фабрика»")


def test_has_darnitsa_prefix_latin():
    assert has_darnitsa_prefix("Darnitsa Citramon")
    assert not has_darnitsa_prefix("Pharma Darnitsa Citramon")


def test_has_darnitsa_prefix_after_separator():
    """Test cases where Дарниця appears after separator (dash, number, etc.)"""
    # From receipt example: "№ 13204 Каптопрес-Дарниця табл. 25 мг №20"
    assert has_darnitsa_prefix("№ 13204 Каптопрес-Дарниця табл. 25 мг №20")
    assert has_darnitsa_prefix("Каптопрес-Дарниця")
    assert has_darnitsa_prefix("KAPTOPRES-DARNITSIA TABL. 25 MG")
    assert has_darnitsa_prefix("Каптопрес Дарниця")
    assert has_darnitsa_prefix("13204 Дарниця")
    
    # Should not match when Дарниця is in the middle of a sentence (not a product name)
    assert not has_darnitsa_prefix("Препарат от Дарниця")  # "от" is too short and not a drug name
    assert not has_darnitsa_prefix("Pharma Darnitsa Citramon")  # English word before, not Cyrillic

