import json
import os
import requests
from bs4 import BeautifulSoup

import consts
from logger import logger as log


class BaseParser:
    def __init__(self, url: str):
        self.url = url
        self.soup = self.get_page(url)

    def get_default_source(self):
        return 'Default Source'

    def get_source(self, page_data):
        return page_data.get('publisher', {}).get('name', '') or self.get_default_source()

    def get_page(self, url: str):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup

    def get_script_tags(self):
        return self.soup.find_all('script', type='application/ld+json')

    def get_script_jsons(self):
        script_tags = self.get_script_tags()
        script_jsons_group = []
        for script_tag in script_tags:
            try:
                data = json.loads(script_tag.string)
                script_jsons_group.append(data)
            except json.JSONDecodeError:
                continue

        return [json_obj for jsons in script_jsons_group for json_obj in jsons]

    def get_page_data(self, script_jsons: list[dict]):
        for script_json in script_jsons:
            if (isinstance(script_json, dict) and
                    script_json.get('@type', '') == 'NewsArticle'):
                return script_json
        return {}

    def get_recipes_data(self, script_jsons):
        recipe_json = {}
        for script_json in script_jsons:
            if '@graph' in script_json:
                return [json_obj for json_obj in script_json['@graph']
                        if isinstance(script_json, dict) and
                        json_obj.get('@type', '') == 'Recipe']
        return []

    def get_recipes(self):
        script_jsons = self.get_script_jsons()
        if not script_jsons:
            return None

        recipes_data = self.get_recipes_data(script_jsons)
        base_data = self.get_base_data(script_jsons)

        recipes = []
        for recipe_data in recipes_data:
            recipe = base_data.copy()
            self.add_recipe_details(recipe_data, recipe)

            if 'image_url' in recipe:
                image_url = recipe.pop('image_url')
                recipe['image'] = self.download_image(image_url, recipe['name'], recipe['source'])

            recipes.append(recipe)
        return recipes

    def download_image(self, url, recipe_name, source):
        if not url:
            return None
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                if recipe_name:
                    image_ext = url.split('.')[-1]
                    image_name = f'{recipe_name}.{image_ext}'
                else:
                    image_name = url.split('/')[-1]

                path = os.path.join(consts.images_dir, source.replace(' ', '_')) if source else consts.images_dir
                os.makedirs(path, exist_ok=True)

                image_path = os.path.join(path, image_name)
                with open(image_path, 'wb') as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)
                return f'{source}/{image_name}'
        except Exception as e:
            print(f'Failed to download image: {e}')
        return None

    def get_base_data(self, script_tags: list[dict]):
        page_data = self.get_page_data(script_tags)

        return {
            'source': self.get_source(page_data),
            'url': self.url,
            'author': self.get_page_author(page_data),
            'published_date': self.get_published_date(page_data),
            'title': self.get_title(page_data),
            'image_url': self.get_image_url(page_data)
        }

    def get_page_author(self, page_data):
        return page_data.get('author', [{}])[0].get('name', '')

    def get_published_date(self, page_data):
        return page_data.get('datePublished', '')

    def get_title(self, page_data):
        return page_data.get('headline', '')

    def get_image_url(self, page_data):
        return page_data.get('image', ['https://unsplash.com/photos/grey-hlalway-IHtVbLRjTZU'])[-1]

    def add_recipe_details(self, recipe_data: dict, recipe):
        recipe['name'] = self.get_recipe_name(recipe_data)
        recipe['author'] = self.get_recipe_author(recipe_data) or recipe['author']
        recipe['description'] = self.get_recipe_description(recipe_data)
        recipe['image_url'] = self.get_recipe_image_url(recipe_data) or recipe['image_url']
        recipe['ingredients'] = self.get_recipe_ingredients(recipe_data)
        recipe['instructions'] = self.get_recipe_instructions(recipe_data)
        recipe['recipe_yield'] = self.get_recipe_yield(recipe_data)
        recipe['prep_time'] = self.get_recipe_prep_time(recipe_data)
        recipe['cook_time'] = self.get_recipe_cook_time(recipe_data)
        recipe['total_time'] = self.get_recipe_time(recipe_data)

        return recipe

    def get_recipe_name(self, recipe_data):
        return recipe_data.get('name')

    def get_recipe_author(self, recipe_data):
        return recipe_data.get('author', {}).get('name', '')

    def get_recipe_description(self, recipe_data):
        return recipe_data.get('description')

    def get_recipe_image_url(self, recipe_data):
        return recipe_data.get('image', '')[0]

    def get_recipe_ingredients(self, recipe_data):
        return recipe_data.get('recipeIngredient')

    def get_recipe_instructions(self, recipe_data):
        return recipe_data.get('recipeInstructions')

    def get_recipe_yield(self, recipe_data):
        return recipe_data.get('recipeYield')

    def get_recipe_prep_time(self, recipe_data):
        return recipe_data.get('prepTime')

    def get_recipe_cook_time(self, recipe_data):
        return recipe_data.get('cookTime')

    def get_recipe_time(self, recipe_data):
        return recipe_data.get('totalTime')
