import json
import os
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup, Tag
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
            image_ext: str = Path(url).suffix.split('?')[0] or '.jpg'
            image_name = f"{recipe_name}{image_ext}"
        else:
            image_name = url.split('/')[-1]
            if '.' not in image_name:
                image_name += '.jpg'

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
    def __init__(self, url: str, use_archive: bool = False):
        self.uses_archive: bool = use_archive
        self.url = url
        self.request_url: str = web_requests.get_archive_url(url) if use_archive else url
        self.soup: BeautifulSoup | None = web_requests.get_page(self.request_url)

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

    def json_match_condition(self, json_key: str, key_match: set[str], json_obj: dict) -> bool:
       return ((isinstance(json_obj.get(json_key), str)
                and json_obj.get(json_key).lower() in key_match)
               or (isinstance(json_obj.get(json_key), list)
                   and (key_match & {item.lower() for item in json_obj.get(json_key)})))

    def get_first_json_as_match(self, json_key: str, key_match: set[str], json_objs: list[dict | list]) -> dict:
        return next((json_obj for json_obj in json_objs
              if self.json_match_condition(json_key, key_match, json_obj)), {})
    def get_first_recipe_json(self, json_objs: list[dict | list]) -> dict:
        return self.get_first_json_as_match('@type', {'recipe'}, json_objs)

    def _get_page_data(self, json_objs: list[dict | list]) -> dict:
        return self.get_first_json_as_match('@type', {'article', 'newsarticle'}, json_objs)

    def get_recipes(self) -> list[dict] | None:
        json_objs: list[dict | list] = self._get_first_second_level_jsons()
        if not json_objs:
            return None

        base_data: dict = self._get_base_data(json_objs)
        recipes_data: list[dict] = self._get_recipes_jsons(json_objs)

        return self._create_recipe_jsons(recipes_data, base_data, json_objs)

    def _get_recipes_jsons(self, json_objs: list[dict | list]) -> list[dict]:
        return [
            json_obj for json_obj in json_objs
            if self.json_match_condition('@type', {'recipe'}, json_obj)
        ]

    def _create_recipe_jsons(self, recipes_data: list[dict], base_data: dict, json_objs: list[dict | list]) -> list[dict]:
        return [
            self._get_single_recipe(recipe_data, base_data, json_objs)
            for recipe_data in recipes_data
        ]

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
        article_obj: dict = self.get_first_json_as_match('@type', {'article', 'newsarticle'}, script_jsons)

        if not article_obj:
            article_obj = self.get_first_recipe_json(script_jsons)

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
        organisation = self.get_first_json_as_match('@type', {'organization'}, json_objs)
        return organisation.get('name', 'Unknown Source')

    def _get_page_author(self, json_objs: list[dict]) -> str:
        authors = [json_obj.get('name') for json_obj in json_objs
                   if self.json_match_condition('@type', {'person'}, json_obj)
        # isinstance(json_obj.get('@type'), str)
        #            and json_obj.get('@type').lower() == 'person'
                   and json_obj.get('name')]
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
        elif isinstance(image_obj, list) and isinstance(image_obj[0], str):
            return get_best_image_url(image_obj)
        elif isinstance(image_obj, list) and isinstance(image_obj[0], dict) and 'url' in image_obj[0]:
            urls = [img['url'] for img in image_obj]
            return get_best_image_url(urls)
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

    def get_best_guess_name(self) -> str:
        url_last_part: str = self.url.split('/')[-2 if self.url[-1] == '/' else -1]
        name_parts: list[str] = url_last_part.split('-')
        index: int = min(6, len(name_parts))
        best_guess_name: str = '-'.join(name_parts[:index])
        return best_guess_name

    def dump_unprocessed_data(self, json_objs: list[dict | list] | None = None, base_data: dict | None = None,
                              recipes_data: list[dict] | None = None) -> None:
        base_url: str = web_requests.get_base_url(self.url)
        best_guess_name = self.get_best_guess_name()

        root_path = f'recipes/output/unprocessed/{base_url}'
        os.makedirs(root_path, exist_ok=True)

        json_objs = json_objs or self._get_first_second_level_jsons()
        if not json_objs:
            with open(f'{root_path}/{best_guess_name}.html', 'w', encoding='utf-8') as file:
                file.write(self.soup.prettify())
            return

        base_data = base_data or self._get_base_data(json_objs)
        recipes_data = recipes_data or self._get_recipes_jsons(json_objs)

        with open(f'{root_path}/{best_guess_name}_script_jsons.json', 'w', encoding='utf-8') as file:
            json.dump(json_objs, file, indent=4)
        with open(f'{root_path}/{best_guess_name}_base_data.json', 'w', encoding='utf-8') as file:
            json.dump(base_data, file, indent=4)
        with open(f'{root_path}/{best_guess_name}_recipes_data.json', 'w', encoding='utf-8') as file:
            json.dump(recipes_data, file, indent=4)
        with open(f'{root_path}/{best_guess_name}.html', 'w', encoding='utf-8') as file:
            file.write(self.soup.prettify())


class PinchOfYumParser(BaseParser):
    def _get_recipe_image_url(self, recipe_data: dict, script_jsons: list[dict]) -> str:
        return ''

    def _get_source(self, json_objs: list[dict]) -> str:
        website = self.get_first_json_as_match('@type', {'website'}, json_objs)
        return website.get('name', 'Unknown Source')


class JamieOliverParser(BaseParser):
    def _get_source(self, json_objs: list[dict]) -> str:
        return 'Jamie Oliver'

    def _get_title(self, article_obj: dict) -> str:
        return article_obj.get('name', '')


class WaitroseParser(BaseParser):
    def _get_source(self, json_objs: list[dict]) -> str:
        return 'Waitrose'

    def _get_title(self, article_obj: dict) -> str:
        return article_obj.get('name', '')

    def _get_recipe_author(self, recipe_data: dict) -> str:
        return 'Waitrose'

    def _get_recipe_image_url(self, recipe_data: dict, script_jsons: list[dict]) -> str:
        page_images = self.soup.find_all('img')
        image_element = next((img for img in page_images
                              if img.get('alt', '').lower() == recipe_data.get('name', '').lower()),
                             '')
        image_address = image_element.get('src', '')
        if '.' in image_address.split('/')[-1]:
            image_address = f'{image_address.split('.')[0]}&wid=992.{image_address.split('.')[1]}'
        else:
            image_address = f'{image_address}&wid=992'
        return image_address


class KingArthurBakingParser(BaseParser):
    def _get_source(self, json_objs: list[dict]) -> str:
        return 'King Arthur Baking'

    def _get_title(self, article_obj: dict) -> str:
        return article_obj.get('name', '')


class GuardianParser(BaseParser):
    def get_recipes(self) -> list[dict] | None:
        json_objs: list[dict | list] = self._get_first_second_level_jsons()
        if not json_objs:
            return None

        base_data = self._get_base_data(json_objs)
        recipes_data: list[dict] = self._get_recipes_jsons(json_objs)
        recipes: list[dict] = self._create_recipe_jsons(recipes_data, base_data, json_objs)

        if recipes:
            return recipes

        body: Tag | None = self.soup.find('div', {'class': re.compile('^article-body')})
        p_and_h2_elements: list[Tag] = body.find_all(['h2', 'p'])
        text_element: Tag
        # for text_element in p_and_h2_elements:
        #     print(f'{text_element=}')

        return recipes


class UnknownParser(BaseParser):
    def get_recipes(self) -> list[dict] | None:
        recipes: list[dict] = super().get_recipes()
        self.dump_unprocessed_data()
        return recipes
