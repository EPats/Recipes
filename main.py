import time
import os
import json
from datetime import datetime, timedelta

import email_handler
import recipe_handler
from logger import logger


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


def check_for_new_urls(url_queue: list[str]) -> bool:
    logger.info('Checking for new URLs in emails')
    email_urls: list[str] = email_handler.get_urls_from_emails()
    url_queue.extend(email_urls)
    email_handler.close_mail_connection()
    return len(email_urls) > 0


def process_urls(url_queue: list[str], all_recipes: list[dict], unique_recipe_identifiers: set[str]) -> None:
    while url_queue:
        logger.info(f'URL Queue size: {len(url_queue)}')
        url: str = url_queue.pop(0)
        logger.info(f'Processing URL: {url}')
        recipes = recipe_handler.get_recipes_from_url(url)

        if recipes:
            logger.info(f'Found {len(recipes)} recipes at {url}')
        else:
            logger.warning(f'No recipes found at {url}')

        duplicate_recipes: list[dict] = []
        new_recipes: list[dict] = []
        recipe: dict
        for recipe in recipes:
            if recipe['unique_id'] in unique_recipe_identifiers:
                duplicate_recipes.append(recipe)
            else:
                unique_recipe_identifiers.add(recipe['unique_id'])
                new_recipes.append(recipe)

        if len(duplicate_recipes) > 0:
            logger.warning(f'Found {len(duplicate_recipes)} duplicate recipes at {url}.' +
                        f'Duplicates are not included in the output.')

        all_recipes.extend(new_recipes)
        save_recipes(all_recipes)
        time.sleep(1)  # Wait for 1 second before processing the next URL


def main():
    all_recipes: list[dict] = load_existing_recipes()
    unique_recipe_identifiers: set[str] = {recipe['unique_id'] for recipe in all_recipes}
    url_queue: list[str] = []
    wait_time = int(os.getenv('EMAIL_CHECK_INTERVAL'))
    min_wait_time = int(os.getenv('MIN_EMAIL_INTERVAL'))
    max_wait_time = int(os.getenv('MAX_EMAIL_INTERVAL'))

    while True:
        result = check_for_new_urls(url_queue)
        if result:
            process_urls(url_queue, all_recipes, unique_recipe_identifiers)
            wait_time = max(wait_time // 2, min_wait_time)
        else:
            wait_time = min(wait_time * 2, max_wait_time)

        next_check_time = datetime.now() + timedelta(seconds=wait_time)
        logger.info(f'Sleeping for {wait_time} seconds. Next scheduled check: {next_check_time:%Y-%m-%d %H:%M}')
        time.sleep(wait_time)


if __name__ == '__main__':
    main()
