import os
import json
import time

from typing import Type

import email_handler
from logger import get_logger

import recipes.recipe_parsers as parsers


parser_classes: dict[str, Type[parsers.BaseParser]] = {
    'pinchofyum.com': parsers.PinchOfYumParser
}


def get_recipes_from_url(url: str) -> list[dict]:
    base_url: str = email_handler.get_base_url(url)
    parser_class: Type[parsers.BaseParser] = parser_classes.get(base_url, parsers.BaseParser)
    parser: parsers.BaseParser = parser_class(url)
    if not parser.has_soup_content():
        return []
    recipes: list[dict] = parser.get_recipes() or []
    return recipes


def load_existing_recipes() -> list[dict]:
    filepath: str = os.getenv('OUTPUT_FILE')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    return []


def save_recipes(recipes: list[dict]) -> None:
    filepath: str = os.getenv('OUTPUT_FILE')
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(recipes, file, indent=4)


def get_recipe_unique_id(recipe: dict) -> str:
    return f'{recipe.get('recipe_name','').replace(' ', '_')}||{recipe.get('url','')}'


def dump_unprocessed_data(url: str):
    parser: parsers.BaseParser = parsers.BaseParser(url)
    if not parser.has_soup_content():
        return
    script_jsons: list[dict | list] = parser._get_script_jsons()
    url_name = url.replace('https://', '').replace('http://', '').replace('/', '_')
    root_path = 'recipes/output/unprocessed'
    os.makedirs(root_path, exist_ok=True)
    with open(f'{root_path}/{url_name}.json', 'w', encoding='utf-8') as file:
        json.dump(script_jsons, file, indent=4)
    with open(f'{root_path}/{url_name}.html', 'w', encoding='utf-8') as file:
        file.write(parser.soup.prettify())


def process_recipe_emails(email_bodies: list[str]) -> None:
    all_recipes: list[dict] = load_existing_recipes()
    unique_recipe_identifiers: set[str] = {get_recipe_unique_id(recipe) for recipe in all_recipes}

    urls: list[str] = email_handler.get_urls(email_bodies)
    get_logger().info(f'Recipe url queue size: {len(urls)}')
    for url in urls:
        recipes: list[dict] = get_recipes_from_url(url)
        if recipes:
            get_logger().info(f'Found {len(recipes)} recipes at {url}')
        else:
            get_logger().warning(f'No recipes found at {url}')
            dump_unprocessed_data(url)
            continue

        duplicate_recipes: list[dict] = []
        new_recipes: list[dict] = []
        recipe: dict
        for recipe in recipes:
            unique_id = get_recipe_unique_id(recipe)
            if unique_id in unique_recipe_identifiers:
                duplicate_recipes.append(recipe)
            else:
                unique_recipe_identifiers.add(unique_id)
                new_recipes.append(recipe)

        if len(duplicate_recipes) > 0:
            get_logger().warning(f'Found {len(duplicate_recipes)} duplicate recipes at {url} ; ' +
                        f'Duplicates are not included in the output.')

        all_recipes.extend(new_recipes)
        save_recipes(all_recipes)
        time.sleep(1)  # Wait for 1 second before processing the next URL
