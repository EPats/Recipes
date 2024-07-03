import os

from parsers import recipetineats_parser

images_dir = 'recipe_images'
os.makedirs(images_dir, exist_ok=True)


parser_classes = {
    'recipetineats.com': recipetineats_parser.RecipeTinEatsParser
    # 'theguardian.com': guardian_parser.GuardianParser
}


output_file_path = 'recipes.json'