import re
from typing import Type
from parsers.base_parser import BaseParser
from parsers.recipetineats_parser import RecipeTinEatsParser

parser_classes: dict[str, Type[BaseParser]] = {
    'recipetineats.com': RecipeTinEatsParser
    # 'theguardian.com': guardian_parser.GuardianParser
}

def get_base_url(url: str) -> str:
    base: str = re.sub(r'(https?://)?(www\.)?', '', url)
    base = base.split('/')[0]
    return base


def get_recipes_from_url(url: str) -> list[dict]:
    base_url: str = get_base_url(url)
    parser_class: Type[BaseParser] = parser_classes.get(base_url, BaseParser)
    parser: BaseParser = parser_class(url)
    recipes: list[dict] = parser.get_recipes() or []
    return recipes
