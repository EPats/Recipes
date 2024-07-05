import os
import json
import time

from typing import Type

import email_handler
from parsers.base_parser import BaseParser
from parsers.recipetineats_parser import RecipeTinEatsParser
from logger import get_logger


parser_classes: dict[str, Type[BaseParser]] = {
    'recipetineats.com': RecipeTinEatsParser
    # 'theguardian.com': guardian_parser.GuardianParser
}


def get_recipes_from_url(url: str) -> list[dict]:
    base_url: str = email_handler.get_base_url(url)
    parser_class: Type[BaseParser] = parser_classes.get(base_url, BaseParser)
    parser: BaseParser = parser_class(url)
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
    recipe_name = recipe.get('recipe_name', '').replace(' ', '_')
    recipe_url = recipe.get('url', '')
    return f'{recipe_name}||{recipe_url}'


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
            get_logger().warning(f'Found {len(duplicate_recipes)} duplicate recipes at {url}.' +
                        f'Duplicates are not included in the output.')

        all_recipes.extend(new_recipes)
        save_recipes(all_recipes)
        time.sleep(1)  # Wait for 1 second before processing the next URL
