import json
import os
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup
import web_requests
from logger import get_logger
from urllib.parse import urlparse, parse_qs


def get_best_image_url(urls: list[str]) -> str:
    def get_image_width(url):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        width = query.get('width', [0])[0]
        return int(width)

    # Sort URLs by width (descending) and take the first (largest) one
    best_url: str = max(urls, key=get_image_width)

    return best_url

def _is_valid_json(string: str) -> bool:
    try:
        json.loads(string)
        return True
    except json.JSONDecodeError:
        return False


def _has_at_sign_in_keys(d: dict) -> bool:
    return any('@' in key for key in d)


def _process_list(lst: list) -> list[dict]:
    return [item for item in lst if isinstance(item, dict) and _has_at_sign_in_keys(item)]


def _process_dict(d: dict) -> list[dict]:
    return [d] if _has_at_sign_in_keys(d) else []


def _get_second_level_jsons(nested_json: dict) -> list[dict]:
    return [
        item
        for value in nested_json.values()
        if isinstance(value, (dict, list))
        for item in (_process_dict(value) if isinstance(value, dict) else _process_list(value))
    ]


def _combine_authors(author1: str, author2: str) -> str | None:
    all_authors = [author.strip() for author in (author1 + ',' + author2).split(',') if author.strip()]
    return ', '.join(set(all_authors)) if all_authors else None


def download_image(url: str, recipe_name: str, source: str) -> str | None:
    if not url:
        return None

    try:
        response: requests.Response = requests.get(url, stream=True)
        response.raise_for_status()

        image_name: str
        if recipe_name:
            image_ext: str = Path(url).suffix.split('?')[0]
            image_name = f"{recipe_name}{image_ext}"
        else:
            image_name = url.split('/')[-1]

        image_name = re.sub(r'[?:/\\*"<>|]', '', image_name)

        images_dir: Path = Path(os.getenv('IMAGES_DIR', '.'))
        path: Path = images_dir / source.replace(' ', '_') if source else images_dir
        path.mkdir(parents=True, exist_ok=True)

        image_path: Path = path / image_name

        with image_path.open('wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        return f'{source}/{image_name}'

    except requests.RequestException as req_error:
        get_logger().error(f'HTTP error occurred while downloading the image at {url}: {req_error}')
    except OSError as os_error:
        get_logger().error(f'File system error occurred downloading the image at {url}: {os_error}')
    except Exception as unexpected_error:
        get_logger().error(f'An unexpected error occurred downloading the image at {url}: {unexpected_error}')

    return None


class BaseParser:
    def __init__(self, url: str):
        self.url: str = url
        self.soup: BeautifulSoup | None = web_requests.get_page(url)

    def _get_default_source(self) -> str:
        return 'Unknown Source'

    def has_soup_content(self) -> bool:
        return self.soup is not None and bool(self.soup.contents)

    def _get_script_tags(self) -> list[BeautifulSoup]:
        if not self.soup:
            return []
        return self.soup.find_all('script', type='application/ld+json')

    def _get_script_jsons(self) -> list[dict]:
        script_tags: list[BeautifulSoup] = self._get_script_tags()
        result = []
        for script_tag in script_tags:
            if _is_valid_json(script_tag.string):
                parsed = json.loads(script_tag.string)
                if isinstance(parsed, list):
                    result.extend(parsed)
                else:
                    result.append(parsed)
        return [item for item in result if isinstance(item, dict)]

    def _get_first_second_level_jsons(self) -> list[dict]:
        script_jsons: list[dict] = self._get_script_jsons()
        jsons: list[dict] = []

        for nested_json in script_jsons:
            jsons.append(nested_json)
            jsons.extend(_get_second_level_jsons(nested_json))

        return jsons

    def _get_page_data(self, json_objs: list[dict | list]) -> dict:
        return next(
            (obj for obj in json_objs
             if isinstance(obj, dict) and obj.get('@type') in {'Article', 'NewsArticle'}), {}
        )

    def get_recipes(self) -> list[dict] | None:
        json_objs: list[dict | list] = self._get_first_second_level_jsons()
        if not json_objs:
            return None

        base_data = self._get_base_data(json_objs)
        recipes_data = [json_obj for json_obj in json_objs if json_obj.get('@type') == 'Recipe' ]

        recipes: list[dict] = [
            self._get_single_recipe(recipe_data, base_data, json_objs)
            for recipe_data in recipes_data
        ]

        return recipes

    def _get_single_recipe(self, recipe_data: dict, base_data: dict, json_objs: list[dict]) -> dict:
        recipe: dict = self._merge_dicts_with_author_combine(
            base_data,
            self._get_recipe_details(recipe_data, json_objs)
        )

        if recipe.get('image'):
            recipe['image'] = download_image(
                recipe.get('image'),
                recipe.get('recipe_name', ''),
                recipe.get('source')
            )

        return recipe

    def _merge_dicts_with_author_combine(self, dict1: dict, dict2: dict) -> dict:
        merged = {**dict1, **{k: v for k, v in dict2.items() if v}}

        if 'author' in dict1 or 'author' in dict2:
            merged['author'] = _combine_authors(
                dict1.get('author', ''),
                dict2.get('author', '')
            )

        return merged

    def _get_base_data(self, script_jsons: list[dict]) -> dict:
        article_obj: dict = next((json_obj for json_obj in script_jsons
                                  if json_obj.get('@type') in {'Article', 'NewsArticle'}), {})
        if not article_obj:
            article_obj = next((json_obj for json_obj in script_jsons
                                if json_obj.get('@type') == 'Recipe'), {})

        return {
            'source': self._get_source(script_jsons),
            'url': self.url,
            'author': self._get_page_author(script_jsons),
            'published_date': self._get_published_date(article_obj),
            'article_title': self._get_title(article_obj),
            'image': self._get_image_url(article_obj, script_jsons)
        }

    def _get_recipe_details(self, recipe_data: dict, script_jsons: list[dict]) -> dict:
        return {
            'recipe_name': self._get_recipe_name(recipe_data),
            'author': self._get_recipe_author(recipe_data),
            'description': self._get_recipe_description(recipe_data),
            'image': self._get_recipe_image_url(recipe_data, script_jsons),
            'ingredients': self._get_recipe_ingredients(recipe_data),
            'instructions': self._get_recipe_instructions(recipe_data),
            'recipe_yield': self._get_recipe_yield(recipe_data),
            'prep_time': self._get_recipe_prep_time(recipe_data),
            'cook_time': self._get_recipe_cook_time(recipe_data),
            'total_time': self._get_recipe_time(recipe_data)
        }

    def _get_source(self, json_objs: list[dict]) -> str:
        organisation = next((json_obj for json_obj in json_objs
                             if json_obj.get('@type') == 'Organization'), {})
        return organisation.get('name', self._get_default_source())

    def _get_page_author(self, json_objs: list[dict]) -> str:
        authors = [json_obj.get('name') for json_obj in json_objs
                   if json_obj.get('@type', '') == 'Person' and json_obj.get('name')]
        return ', '.join(authors)

    def _get_published_date(self, article_obj: dict) -> str:
        return article_obj.get('datePublished')

    def _get_title(self, article_obj: dict) -> str:
        return article_obj.get('headline', '')

    def _get_image_url(self, article_obj: dict, json_objs: list[dict]) -> str:
        image_obj = article_obj.get('image')
        blank_image: str = 'https://unsplash.com/photos/grey-hlalway-IHtVbLRjTZU'

        if not image_obj:
            return blank_image
        elif isinstance(image_obj, str):
            return image_obj
        elif isinstance(image_obj, list):
            return get_best_image_url(image_obj)
        elif isinstance(image_obj, dict):
            if 'url' in image_obj:
                return image_obj['url']
            elif '@id' in image_obj:
                id: str = image_obj['@id']
                true_image_obj: dict = next((json_obj for json_obj in json_objs
                                             if json_obj.get('@id') == id), {})
                return true_image_obj.get('url', blank_image)

        return blank_image

    def _get_recipe_name(self, recipe_data: dict) -> str:
        return recipe_data.get('name')

    def _get_recipe_author(self, recipe_data: dict) -> str:
        author_details: list[dict] | dict | None = recipe_data.get('author')

        if not author_details:
            return ''

        if isinstance(author_details, dict):
            return author_details.get('name', '')

        return ', '.join([author.get('name') for author in author_details if 'name' in author])

    def _get_recipe_description(self, recipe_data: dict):
        return recipe_data.get('description', '')

    def _get_recipe_image_url(self, recipe_data: dict, script_jsons: list[dict]) -> str:
        return self._get_image_url(recipe_data, script_jsons)

    def _get_recipe_ingredients(self, recipe_data: dict) -> list | dict | str | None:
        return recipe_data.get('recipeIngredient')

    def _get_recipe_instructions(self, recipe_data: dict) -> list | dict | str | None:
        return recipe_data.get('recipeInstructions')

    def _get_recipe_yield(self, recipe_data: dict) -> list | dict | str | None:
        return recipe_data.get('recipeYield')

    def _get_recipe_prep_time(self, recipe_data: dict) -> str:
        return recipe_data.get('prepTime')

    def _get_recipe_cook_time(self, recipe_data: dict) -> str:
        return recipe_data.get('cookTime')

    def _get_recipe_time(self, recipe_data: dict) -> str:
        return recipe_data.get('totalTime')


class PinchOfYumParser(BaseParser):
    def _get_recipe_image_url(self, recipe_data: dict, script_jsons: list[dict]) -> str:
        return ''

    def _get_source(self, json_objs: list[dict]) -> str:
        website = next((json_obj for json_obj in json_objs
                        if json_obj.get('@type') == 'WebSite'), {})
        return website.get('name', self._get_default_source())
