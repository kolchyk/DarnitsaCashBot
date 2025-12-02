from libs.common.darnitsa import has_darnitsa_prefix


def test_has_darnitsa_prefix_cyrillic():
    assert has_darnitsa_prefix("Дарниця Цитрамон")
    assert has_darnitsa_prefix("Дарниця-Цитрамон")
    assert not has_darnitsa_prefix("ТОВ «Дарниця Фармацевтична фабрика»")


def test_has_darnitsa_prefix_latin():
    assert has_darnitsa_prefix("Darnitsa Citramon")
    assert not has_darnitsa_prefix("Pharma Darnitsa Citramon")

