import os
import re
import json
import requests
from bs4 import BeautifulSoup

import consts
from parsers import base_parser


def get_base_url(url):
    base = re.sub(r'(https?://)?(www\.)?', '', url)
    base = base.split('/')[0]
    return base


def load_existing_recipes(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    return []


def save_recipes(filepath, recipes):
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(recipes, file, indent=4)
    print(f"Recipes data has been saved to {filepath}")


def process_urls(urls, all_recipes, output_file_path):
    for url in urls:
        base_url = get_base_url(url)
        parser_class = consts.parser_classes.get(base_url, base_parser.BaseParser)
        parser = parser_class(url)
        recipes = parser.get_recipes()
        for recipe in recipes:
            if recipe not in all_recipes:
                all_recipes.append(recipe)

    save_recipes(output_file_path, all_recipes)


def main():
    # Main script execution
    urls = [
        # 'https://www.theguardian.com/food/article/2024/jun/18/thomasina-miers-recipes-for-summer-salads',
        # 'https://www.theguardian.com/food/article/2024/jun/30/nigel-slaters-recipes-for-carrot-and-cucumber-pickle-and-gooseberry-flapjacks',
        'https://www.recipetineats.com/crispy-slow-roasted-pork-belly/'
    ]

    output_file_path = consts.output_file_path
    existing_recipes = load_existing_recipes(output_file_path)
    all_recipes = existing_recipes.copy()

    process_urls(urls, all_recipes, output_file_path)


if __name__ == '__main__':
    main()
