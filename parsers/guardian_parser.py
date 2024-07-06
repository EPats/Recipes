import json

from parsers.base_parser import BaseParser
from logger import get_logger


class GuardianParser(BaseParser):
    def __init__(self, url: str):
        super().__init__(url)
        script_jsons: list[dict | list] = self.get_script_jsons()
        if script_jsons:
            recipes_data: list[dict] = self.get_recipes_data(script_jsons)
            base_data: dict = self.get_base_data(script_jsons)
            if not recipes_data:
                print(f'No recipes found at {url}')