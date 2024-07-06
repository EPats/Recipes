import json
import os
import requests
from bs4 import BeautifulSoup
from logger import get_logger


def get_page(url: str) -> BeautifulSoup:
    response: requests.Response = requests.get(url)
    if response.status_code != 200:
        get_logger().error(f'Error fetching page at {url}: {response.status_code}')
        return BeautifulSoup('', 'html.parser')
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


class BaseParser:
    def __init__(self, url: str):
        self.url = url
        self.soup = get_page(url)

    def get_default_source(self) -> str:
        return 'Default Source'

    def has_soup_content(self) -> bool:
        # Return true if self.soup isn't ''
        return bool(self.soup.contents)

    def get_script_tags(self) -> list[BeautifulSoup]:
        return self.soup.find_all('script', type='application/ld+json')

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
        script_json: BeautifulSoup
        for script_json in script_jsons:
            if (isinstance(script_json, dict) and
                    script_json.get('@type', '') == 'NewsArticle'):
                return script_json
        return {}

    def get_recipes_data(self, script_jsons: list[dict | list]) -> list[dict]:
        return [json_obj for json_obj in script_jsons
                if isinstance(json_obj, dict) and
                json_obj.get('@type', '') == 'Recipe']

    def get_recipes(self) -> list[dict] | None:
        script_jsons: list[dict | list] = self.get_script_jsons()
        if not script_jsons:
            return None

        recipes_data: list[dict] = self.get_recipes_data(script_jsons)
        base_data: dict = self.get_base_data(script_jsons)

        recipes: list[dict] = []
        for recipe_data in recipes_data:
            recipe: dict = base_data.copy()
            self.add_recipe_details(recipe_data, recipe)

            if 'image_url' in recipe:
                image_url: str = recipe.pop('image_url')
                recipe['image'] = self.download_image(image_url, recipe['recipe_name'], recipe['source'])

            recipes.append(recipe)
        return recipes

    def download_image(self, url: str, recipe_name: str, source: str) -> str | None:
        if not url:
            return None
        try:
            response: requests.Response = requests.get(url, stream=True)
            if response.status_code == 200:
                if recipe_name:
                    image_ext: str = url.split('.')[-1]
                    if '?' in image_ext:
                        image_ext = image_ext.split('?')[0]
                    image_name: str = f'{recipe_name}.{image_ext}'
                else:
                    image_name: str = url.split('/')[-1]

                for char in ['?', ':', '/', '\\', '*', '"', '<', '>', '|']:
                    image_name = image_name.replace(char, '')

                partial_path = (os.getenv('IMAGES_DIR'))
                path: str = os.path.join(partial_path, source.replace(' ', '_')) if source else partial_path
                os.makedirs(path, exist_ok=True)

                image_path: str = os.path.join(path, image_name)
                with open(image_path, 'wb') as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)
                return f'{source}/{image_name}'
        except requests.exceptions.RequestException as e:
            get_logger().error(f'HTTP error occurred while downloading the image at {url}: {e}')
        except OSError as e:
            get_logger().error(f'File system error occurred downloading the image at {url}: {e}')
        except Exception as e:
            get_logger().error(f'An unexpected error occurred downloading the image at {url}: {e}')
        return None

    def get_base_data(self, script_tags: list[dict]) -> dict:
        page_data: dict = self.get_page_data(script_tags)

        return {
            'source': self.get_source(page_data),
            'url': self.url,
            'author': self.get_page_author(page_data),
            'published_date': self.get_published_date(page_data),
            'article_title': self.get_title(page_data),
            'image_url': self.get_image_url(page_data)
        }

    def add_recipe_details(self, recipe_data: dict, recipe: dict) -> dict:
        recipe['recipe_name'] = self.get_recipe_name(recipe_data)

        recipe_author: str = self.get_recipe_author(recipe_data)
        page_author: str = recipe['author']
        all_authors: list[str] = [author for author in recipe_author.split(', ') if author]
        all_authors.extend([author for author in page_author.split(', ') if author])
        author = ', '.join(all_authors) if all_authors else ''

        recipe['author'] = author
        recipe['description'] = self.get_recipe_description(recipe_data)
        recipe['image_url'] = self.get_recipe_image_url(recipe_data) or recipe['image_url']
        recipe['ingredients'] = self.get_recipe_ingredients(recipe_data)
        recipe['instructions'] = self.get_recipe_instructions(recipe_data)
        recipe['recipe_yield'] = self.get_recipe_yield(recipe_data)
        recipe['prep_time'] = self.get_recipe_prep_time(recipe_data)
        recipe['cook_time'] = self.get_recipe_cook_time(recipe_data)
        recipe['total_time'] = self.get_recipe_time(recipe_data)

        return recipe

    def get_source(self, page_data: dict) -> str:
        return page_data.get('publisher', {}).get('name', '') or self.get_default_source()

    def get_page_author(self, page_data: dict) -> str:
        author_details: list[dict] | dict | None = page_data.get('author')

        if not author_details:
            return ''

        if isinstance(author_details, dict):
            return author_details.get('name', '')

        return ', '.join([author.get('name') for author in author_details if 'name' in author])


    def get_published_date(self, page_data: dict) -> str:
        return page_data.get('datePublished', '')

    def get_title(self, page_data: dict) -> str:
        return page_data.get('headline', '')

    def get_image_url(self, page_data: dict) -> str:
        image_obj = page_data.get('image', '')
        if not image_obj:
            return 'https://unsplash.com/photos/grey-hlalway-IHtVbLRjTZU'

        if isinstance(image_obj, dict):
            return image_obj.get('url', 'https://unsplash.com/photos/grey-hlalway-IHtVbLRjTZU')

        return image_obj[-1]


    def get_recipe_name(self, recipe_data: dict) -> str:
        return recipe_data.get('name')

    def get_recipe_author(self, recipe_data: dict) -> str:
        author_details: list[dict] | dict | None = recipe_data.get('author')

        if not author_details:
            return ''

        if isinstance(author_details, dict):
            return author_details.get('name', '')

        return ', '.join([author.get('name') for author in author_details if 'name' in author])

    def get_recipe_description(self, recipe_data: dict):
        return recipe_data.get('description', '')

    def get_recipe_image_url(self, recipe_data: dict) -> str:
        return recipe_data.get('image', '')

    def get_recipe_ingredients(self, recipe_data: dict) -> list | dict | str | None:
        return recipe_data.get('recipeIngredient')

    def get_recipe_instructions(self, recipe_data: dict) -> list | dict | str | None:
        return recipe_data.get('recipeInstructions')

    def get_recipe_yield(self, recipe_data: dict) -> list | dict | str | None:
        return recipe_data.get('recipeYield')

    def get_recipe_prep_time(self, recipe_data: dict) -> str:
        return recipe_data.get('prepTime')

    def get_recipe_cook_time(self, recipe_data: dict) -> str:
        return recipe_data.get('cookTime')

    def get_recipe_time(self, recipe_data: dict) -> str:
        return recipe_data.get('totalTime')


class GuardianParser(BaseParser):
    def get_default_source(self) -> str:
        return 'The Guardian'