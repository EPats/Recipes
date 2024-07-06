import json
from bs4 import BeautifulSoup
from parsers.base_parser import BaseParser
from logger import get_logger
import re


class GuardianParser(BaseParser):

    def get_default_source(self) -> str:
        return 'The Guardian'

    def get_script_jsons(self) -> list[dict]:
        script_tags: list[BeautifulSoup] = self.get_script_tags()
        script_jsons_group: list[dict] = []
        script_tag: BeautifulSoup
        for script_tag in script_tags:
            try:
                data: dict | list = json.loads(script_tag.string)
                script_jsons_group.append(data)
            except json.JSONDecodeError:
                continue

        return [json_obj for jsons in script_jsons_group for json_obj in jsons]

    def get_recipes_data(self, script_jsons: list[dict | list]) -> list[dict]:
        recipes_data: list[dict] = super().get_recipes_data(script_jsons)
        if recipes_data:
            return recipes_data

        # If the recipe data is not in the script tags, it may be in the body of the page
        return self.get_recipes_from_body()

    def get_recipes_from_body(self) -> list[dict]:
        recipes = []

        # Find the main article image
        main_image = self.soup.find('figure', class_='dcr-142siv7')
        main_image_src = self.get_largest_image(main_image) if main_image else None

        # Find all h2 elements which likely represent recipe titles
        h2_titles = self.soup.find_all('h2')
        recipe_titles = [title for title in h2_titles if title.get('id', '').split('-')[0].lower() == title.text.strip().split(' ')[0].lower()]

        for title in recipe_titles:
            recipe = {'name': title.text.strip()}

            # Find image: first look for a figure after the title but before the next h2
            next_h2 = title.find_next('h2')
            recipe_image = title.find_next('figure', class_=lambda x: x != 'dcr-142siv7')
            if recipe_image and (not next_h2 or recipe_image.sourceline < next_h2.sourceline):
                recipe['image'] = self.get_largest_image(recipe_image)
            else:
                # If no specific recipe image found, use the main article image
                recipe['image'] = main_image_src

            # Get description (first paragraph after title)
            description = title.find_next('p')
            if description:
                recipe['description'] = description.text.strip()

            current = description
            # Get details (prep time, cook time, serves)
            details = description.find_next('p')
            if details and ('Prep' in details.text or 'Cook' in details.text or 'Serves' in details.text):
                details_text = ''.join(str(child) for child in details.contents)
                details_parts = re.split(r'(\n|<br\s?/>)', details_text)
                details_parts = [re.sub(r'<.*?>', '', detail) for detail in details_parts if detail and detail not in ['\n', '<br/>']]
                for detail in details_parts:
                    if 'Prep' in detail:
                        recipe['prepTime'] = detail
                    elif 'Cook' in detail:
                        recipe['cookTime'] = detail
                    elif 'Serves' in detail:
                        recipe['recipeYield'] = detail
                    elif 'Total' in detail:
                        recipe['totalTime'] = detail
                current = details

            # Get ingredients and instructions
            ingredients = []
            instructions = []
            current = current.next_sibling if details else None

            while current and current.name != 'h2':
                if current.name == 'p':
                    # Check if this paragraph contains ingredients
                    if '<br/>' in str(current):
                        # This is an ingredients paragraph
                        ingredients.append(''.join([str(el) for el in current.contents]))
                    else:
                        # This is an instruction paragraph
                        instructions.append(''.join(str(child) for child in current.contents))
                current = current.next_sibling

            recipe['recipeIngredient'] = ingredients
            recipe['recipeInstructions'] = instructions

            recipes.append(recipe)

        return recipes

    def get_largest_image(self, figure):
        picture = figure.find('picture')
        if picture:
            sources = picture.find_all('source')
            largest_width = 0
            largest_src = None
            for source in sources:
                srcset = source.get('srcset')
                if 'width' in srcset:
                    width = int(re.findall(r'width=(\d+)', srcset)[0])
                    if width > largest_width:
                        largest_width = width
                        largest_src = source['srcset']
            if largest_src:
                return largest_src

        # Fallback to img tag if no source found
        img = figure.find('img')

        return img['src'] if img and 'src' in img.attrs else None

