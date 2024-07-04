import json
from bs4 import BeautifulSoup
from parsers.base_parser import BaseParser


class RecipeTinEatsParser(BaseParser):
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