from parsers.base_parser import BaseParser
from bs4 import BeautifulSoup
import json


class HouseAndGardenParser(BaseParser):

    def get_default_source(self) -> str:
        return 'House and Garden'

    def get_script_jsons(self) -> list[dict]:
        script_tags: list[BeautifulSoup] = self.get_script_tags()
        script_jsons: list[dict] = []
        for script_tag in script_tags:
            try:
                data = json.loads(script_tag.string)
                script_jsons.append(data)
            except json.JSONDecodeError:
                continue

        return script_jsons

    def get_page_data(self, script_jsons: list[dict | list]) -> dict:
        return self.get_recipes_data(script_jsons)[0]

    def get_base_data(self, script_tags: list[dict]) -> dict:
        base_data: dict = super().get_base_data(script_tags)
        page_data: dict = self.get_page_data(script_tags)
        base_data['alternative_title'] = page_data.get('alternativeHeadline', '')

        return base_data

    def get_recipe_image_url(self, recipe_data: dict) -> str:
        return recipe_data.get('image', '')[-1]