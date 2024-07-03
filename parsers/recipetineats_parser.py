import json

from parsers.base_parser import BaseParser


class RecipeTinEatsParser(BaseParser):
    def get_script_jsons(self):
        script_tags = self.get_script_tags()
        script_jsons = []
        for script_tag in script_tags:
            try:
                data = json.loads(script_tag.string)
                script_jsons.append(data)
            except json.JSONDecodeError:
                continue

        return script_jsons

    def get_image_url(self, page_data):
        return page_data.get('image', {}).get('url', 'https://unsplash.com/photos/grey-hlalway-IHtVbLRjTZU')

