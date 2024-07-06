import json
from bs4 import BeautifulSoup
from parsers.base_parser import BaseParser


class RecipeTinEatsParser(BaseParser):

    def get_default_source(self) -> str:
        return 'Recipe Tin Eats'

    def get_image_url(self, page_data: dict) -> str:
        return page_data.get('image', {}).get('url', 'https://unsplash.com/photos/grey-hlalway-IHtVbLRjTZU')

    def get_recipes_data(self, script_jsons: list[dict]) -> list[dict]:
        script_json: dict
        for script_json in script_jsons:
            if '@graph' in script_json:
                return [json_obj for json_obj in script_json['@graph']
                        if isinstance(script_json, dict) and
                        json_obj.get('@type', '') == 'Recipe']
        return []

    def get_recipe_image_url(self, recipe_data: dict) -> str:
        return recipe_data.get('image', '')[0]