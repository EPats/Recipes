import os
import re
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import consts
import logger
from parsers import base_parser
import imaplib
import email
from email.header import decode_header
from functools import partial


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


def connect_to_gmail_imap():
    imap_url = os.getenv('IMAP_SERVER')
    try:
        mail = imaplib.IMAP4_SSL(imap_url)
        mail.login(os.getenv('GMAIL_USER'), os.getenv('GMAIL_PASSWORD'))
        mail.select('inbox')  # Connect to the inbox.
        return mail
    except Exception as e:
        logger.logger.error('Connection failed: {}'.format(e))
        raise


def filter_by_sender_and_subject(email: tuple, sender_match: str, subject_match: str):
    email_id, email_data = email
    sender = re.search(r'<(.+)>', email_data.get('From')).group(1)
    subject, encoding = decode_header(email_data['Subject'])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding if encoding else 'utf-8')

    return sender == sender_match and subject == subject_match


def get_body(email_data):
    if email_data.is_multipart():
        plaintext_parts = [part for part in email_data.walk() if part.get_content_type() == 'text/plain']
        text = ''
        for plaintext_part in plaintext_parts:
            body = plaintext_part.get_payload(decode=True).decode()
            content_disposition = str(plaintext_part.get('Content-Disposition'))
            if (plaintext_part.get_content_type() == 'text/plain'
                    and 'attachment' not in content_disposition):
                text += body

        return text
    else:
        content_type = email_data.get_content_type()
        body = email_data.get_payload(decode=True).decode()

        if content_type == 'text/plain':
            return body
    return ''


def check_unread_emails(mail):
    try:
        # Search for unread emails
        status, messages = mail.search(None, '(UNSEEN)')

        if status != 'OK':
            print('No messages found!')
            return

        # Get the list of email IDs
        email_ids = messages[0].split()

        emails = []
        for email_id in email_ids:
            # Fetch the email by ID using BODY.PEEK to avoid marking it as read
            status, msg_data = mail.fetch(email_id, '(BODY.PEEK[])')

            if status != 'OK':
                print('Failed to fetch email ID: {}'.format(email_id))
                continue

            emails.append((email_id, email.message_from_bytes(msg_data[0][1])))

        filter_recipes = partial(filter_by_sender_and_subject,
                                 sender_match=os.getenv('FROM_EMAIL'),
                                 subject_match='Recipes')
        filtered_emails = filter(filter_recipes, emails.copy())

        urls = []
        for email_id, email_data in filtered_emails:
            body = get_body(email_data)
            urls.extend([url.strip() for url in body.split('\n') if url.strip()])

        print(urls)
    except Exception as e:
        print('Failed to check unread emails: {}'.format(e))
        raise

    finally:
        mail.close()
        mail.logout()


if __name__ == '__main__':
    load_dotenv()
    # main()
    check_unread_emails(connect_to_gmail_imap())