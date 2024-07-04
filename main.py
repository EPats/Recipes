import time
import os
import json
from datetime import datetime, timedelta

from dotenv import load_dotenv

import arr_handler
import email_handler
import recipe_handler
from logger import init_logger, logger


def check_for_new_emails(queues: dict) -> bool:
    logger.info('Checking for new emails')
    emails_by_subject: dict[str, list[str]] = email_handler.get_emails_by_subject()
    total: int = 0
    for subject in emails_by_subject:
        emails: list[str] = emails_by_subject[subject]
        total += len(emails)
        if emails:
            queues.get(subject, []).extend(emails)
            logger.info(f'Loaded {len(emails)} emails for "{subject}"')
        else:
            logger.info(f'No emails found for "{subject}"')
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
                logger.warning(f'No processing logic for emails with subject: {subject}' +
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
        logger.info(f'Sleeping for {wait_time} seconds. Next scheduled check: {next_check_time:%Y-%m-%d %H:%M}')
        time.sleep(wait_time)


def setup() -> None:
    load_dotenv()
    init_logger()


if __name__ == '__main__':
    setup()
    main()
