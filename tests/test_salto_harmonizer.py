import pytest

from src.harmonizers.salto import clean_author


@pytest.mark.parametrize("byline, expected", [
    ("Martin Tarshito 18.03.2025", "Martin Tarshito"),
    ("Eine Kolumne von Michil Costa 26.05.2023", "Michil Costa"),
    ("Un editoriale di Maurizio Ferrandi 01.02.2024", "Maurizio Ferrandi"),
    ("Elena Mancini & Lukas Kafmann 08.05.2025", "Elena Mancini & Lukas Kafmann"),
    ("Redaktion - Redazione 22.10.2024", "Redaktion - Redazione"),
    ("Demos 2.0", "Demos 2.0"),
    ("Südtiroler Landwirt", "Südtiroler Landwirt"),
    ("", "Redaktion"),
])
def test_clean_author(byline, expected):
    assert clean_author(byline) == expected
