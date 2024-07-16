import time
import os
import json
from datetime import datetime, timedelta

from dotenv import load_dotenv

import arr_handler
import email_handler
import web_requests
from recipes import recipe_handler
from logger import init_logger, get_logger


def check_for_new_emails(queues: dict) -> bool:
    get_logger().info('Checking for new emails')
    emails_by_subject: dict[str, list[str]] = email_handler.get_emails_by_subject()
    total: int = 0
    for subject in emails_by_subject:
        emails: list[str] = emails_by_subject[subject]
        total += len(emails)
        if emails:
            queues.get(subject, []).extend(emails)
            get_logger().info(f'Loaded {len(emails)} emails for "{subject}"')
        else:
            get_logger().info(f'No emails found for "{subject}"')
    return total > 0


def process_emails(queues: dict[str, list[str]]) -> None:
    subject: str
    for subject in queues:
        emails: list[str] = queues[subject]
        if not emails:
            continue

        match subject:
            case 'Recipes':
                recipe_handler.process_recipe_emails(emails)
            case 'Media Requests':
                arr_handler.process_media_request_emails(emails)
            case _:
                get_logger().warning(f'No processing logic for emails with subject: {subject}' +
                               f'\nEmails: {json.dumps(emails, indent=4)}')


def main():
    queues = email_handler.create_subject_queues()

    wait_time = int(os.getenv('EMAIL_CHECK_INTERVAL'))
    min_wait_time = int(os.getenv('MIN_EMAIL_INTERVAL'))
    max_wait_time = int(os.getenv('MAX_EMAIL_INTERVAL'))

    while True:
        # emails_found = check_for_new_urls(url_queue)
        emails_found = check_for_new_emails(queues)
        if emails_found:
            # process_urls(url_queue, all_recipes, unique_recipe_identifiers)
            process_emails(queues)
            wait_time = max(wait_time // 2, min_wait_time)
        else:
            wait_time = min(wait_time * 2, max_wait_time)

        next_check_time = datetime.now() + timedelta(seconds=wait_time)
        get_logger().info(f'Sleeping for {wait_time} seconds. Next scheduled check: {next_check_time:%Y-%m-%d %H:%M}')
        time.sleep(wait_time)


def setup() -> None:
    load_dotenv()
    init_logger()



def testing():
    txt = '''
    https://www.thetimes.com/life-style/food-drink/article/chilled-summer-soup-recipes-sc22x76mx
    https://www.independent.co.uk/life-style/food-and-drink/tom-kerridge-recipes-pub-kitchen-cookbook-b2423595.html
https://www.kingarthurbaking.com/recipes/cakey-brownies-recipe

https://www.theguardian.com/food/2023/oct/17/nigel-slaters-recipe-for-mushroom-ragout
https://www.theguardian.com/food/2023/oct/21/tomato-souffle-brown-butter-sole-yotam-ottolenghi-french-recipes
https://www.theguardian.com/food/2023/oct/28/strudel-meat-free-carbonara-and-shrimp-yotam-ottolenghis-recipes-inspired-by-the-movies
https://www.theguardian.com/food/2023/nov/01/how-to-make-timballo-recipe-felicity-cloake-masterclass
https://www.theguardian.com/food/2023/nov/11/middle-eastern-influenced-irish-recipes-yotam-ottolenghi-barmbrack-farls-irish-stew
https://www.theguardian.com/food/2023/dec/02/yotam-ottolenghi-vegetarian-christmas-recipes-rice-pie-sticky-sprouts-and-yoghurty-beans
https://www.recipetineats.com/green-beans-with-a-mountain-of-panko/
https://www.theguardian.com/food/2023/dec/09/vegan-giardiniera-italian-pickles-recipe-meera-sodha
https://www.theguardian.com/food/2023/dec/06/best-summer-recipes-salads-stuffed-eggplants-chicken-salad-skewers-pasta-yotam-ottolenghi
https://www.theguardian.com/food/2023/dec/30/baked-cheese-glazed-sausages-veggie-dip-easy-recipes-new-year-yotam-ottolenghi
https://www.theguardian.com/food/2024/jan/05/plant-based-three-ingredient-pure-chocolate-mousse-recipe-philip-khoury
https://www.telegraph.co.uk/recipes/0/smoked-trout-sea-bass-crudo-salmon-roe-diana-henry-recipe/
https://www.theguardian.com/food/2024/jan/22/quick-easy-mushroom-leek-spinach-tagliatelle-recipe-rukmini-iyer
https://www.theguardian.com/food/2024/jan/20/roast-cabbage-chana-dal-swede-carrot-bulgur-preserved-lemon-lentils-butternut-squash-feta-yoghurt-yotam-ottolenghi-winter-vegetable-recipes
https://www.theguardian.com/food/2024/jan/29/nigel-slaters-prawn-toast-recipe
https://www.theguardian.com/food/2024/jan/27/30-minute-meal-yotam-ottolenghi-recipes-thai-deep-fried-omelette-tofu-broccoli-spicy-seaweed-sea-bass-spaghetti
https://www.theguardian.com/food/2024/jan/29/the-20-best-recipes-to-put-on-toast-broken-beans-creamy-mushrooms-truffled-leeks-and-more

https://www.theguardian.com/food/2024/mar/23/how-to-turn-stale-bread-leek-tops-and-aquafaba-into-brilliant-vegetarian-sausages-recipe-zero-waste-cooking
https://www.theguardian.com/food/2024/mar/17/nigel-slaters-recipes-for-potatoes-with-mussels-and-dill-and-filled-with-cauliflower-cheese
https://www.theguardian.com/food/2024/mar/30/yotam-ottolenghi-meatball-recipes-pork-peanut-gravy-ricotta-lamb-polpette
https://www.google.com/url?q=https://www.thetimes.co.uk/article/three-recipes-for-a-middle-east-feast-f633b98t9&usg=AOvVaw08xKXMcWca8R6QwdJVhmlZ&cs=1&hl=en-GB
https://www.houseandgarden.co.uk/recipe/italian-cauliflower-cheese-with-mushrooms
https://www.eatingwell.com/crispy-salmon-bites-with-creamy-sun-dried-tomato-dipping-sauce-8663055
https://www.theguardian.com/food/article/2024/jun/09/nigel-slaters-recipes-for-grilled-potatoes-with-curry-yoghurt-sauce-and-pea-croquettes

https://www.theguardian.com/food/article/2024/may/18/ask-ottolenghi-easy-sauces-to-perk-up-midweek-meals
https://www.theguardian.com/food/article/2024/may/15/balkan-favourites-recipes-crunchy-potatoes-fried-pepper-cream-gibanitsa-egg-cheese-filo-pie-spasia-dinkovski
https://www.thetimes.com/uk/scotland/article/clare-coghills-langoustine-roll-with-nduja-butter-recipe-0v2ptmth9

https://www.theguardian.com/food/article/2024/may/11/yotam-ottolenghi-five-ingredient-or-thereabouts-recipes-chicken-rice-spring-onion-broad-beans

https://www.theguardian.com/food/2024/apr/10/how-to-make-thai-green-curry-recipe-felicity-cloake
https://www.loveandlemons.com/french-onion-soup/'''

    urls = email_handler.get_urls([txt])

    # urls = ['https://www.eatingwell.com/crispy-salmon-bites-with-creamy-sun-dried-tomato-dipping-sauce-8663055']

    queues = {'Recipes': urls}
    process_emails(queues)
    # url = 'https://github.com/akamhy/waybackpy/issues/97'
    # arch_url = web_requests.get_archive_url('https://www.elliottpaterson.com')
    # arch_url = web_requests.save_archive(url)
    # print(arch_url)

if __name__ == '__main__':
    setup()
    # main()
    testing()
