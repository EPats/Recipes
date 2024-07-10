import os
import json
import time

from typing import Type

import email_handler
import web_requests
from logger import get_logger

import recipes.recipe_parsers as parsers
from recipes import recipe_parsers

known_sites: list[str] = [
    'theguardian.com',
    'houseandgarden.co.uk',
    'bbcgoodfood.com',
    'loveandlemons.com',
    'realfood.tesco.com',
    'sainsbury.co.uk',
    'recipetineats.com'
]


archive_sites: list[str] = [
    'telegraph.co.uk',
    'thetimes.co.uk'
    ]


parser_classes: dict[str, Type[parsers.BaseParser]] = {
    **{site: parsers.BaseParser for site in known_sites},
    'pinchofyum.com': parsers.PinchOfYumParser,
    'waitrose.com': parsers.WaitroseParser,
    'jamieoliver.com': parsers.JamieOliverParser,
    'kingarthurbaking.com': parsers.KingArthurBakingParser

}


def get_recipes_from_url(url: str) -> list[dict]:
    base_url: str = web_requests.get_base_url(url)
    parser_class: Type[parsers.BaseParser] = parser_classes.get(base_url, parsers.UnknownParser)
    parser: parsers.BaseParser = parser_class(url, base_url in archive_sites)
    if not parser.has_soup_content():
        return []

    recipes: list[dict] = parser.get_recipes() or []
    if recipes:
        get_logger().info(f'Found {len(recipes)} recipes at {url}')
        if isinstance(parser, parsers.UnknownParser):
            base_url: str = web_requests.get_base_url(parser.url.replace(recipe_parsers.archive_prefix, ''))
            best_guess_name = parser.get_best_guess_name()
            root_path = f'recipes/output/unprocessed/{base_url}'
            os.makedirs(root_path, exist_ok=True)

            with open(f'{root_path}/{best_guess_name}_recipes.json', 'w', encoding='utf-8') as file:
                json.dump(recipes, file, indent=4)
    else:
        get_logger().warning(f'No recipes found at {url}')
        if not isinstance(parser, parsers.UnknownParser):
            parser.dump_unprocessed_data()
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
    return f'{recipe.get('recipe_name', '').replace(' ', '_')}||{recipe.get('url', '')}'


def process_recipe_emails(email_bodies: list[str]) -> None:
    all_recipes: list[dict] = load_existing_recipes()
    unique_recipe_identifiers: set[str] = {get_recipe_unique_id(recipe) for recipe in all_recipes}

    urls: list[str] = email_handler.get_urls(email_bodies)
    get_logger().info(f'Recipe url queue size: {len(urls)}')
    for url in urls:
        recipes: list[dict] = get_recipes_from_url(url)
        if not recipes:
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
            get_logger().warning(f'Found {len(duplicate_recipes)} duplicate recipes at {url}\n'
                                 f'Duplicates are not included in the output.')

        all_recipes.extend(new_recipes)
        save_recipes(all_recipes)
        time.sleep(1)  # Wait for 1 second before processing the next URL
