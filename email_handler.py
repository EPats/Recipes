import atexit
from email import message, message_from_bytes
import imaplib
import json
import os

from logger import logger


mail: imaplib.IMAP4_SSL | None = None


@atexit.register
def exit_handler() -> None:
    close_mail_connection()


def close_mail_connection() -> None:
    logger.info('Closing mail connection')
    global mail
    if mail:
        mail.close()
        mail.logout()
        mail = None
        logger.info('Mail connection closed')
    else:
        logger.warn('No mail connection to close')


def assign_mail_instance() -> None:
    global mail
    mail = connect_to_imap_server()


def connect_to_imap_server() -> imaplib.IMAP4_SSL:
    imap_url: str = os.getenv('IMAP_SERVER')
    try:
        mail_instance: imaplib.IMAP4_SSL = imaplib.IMAP4_SSL(imap_url)
        mail_instance.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_APP_PASSWORD'))
        mail_instance.select('inbox')  # Connect to the inbox.
        return mail_instance
    except imaplib.IMAP4.error as e:
        logger.error('Connection failed: {}'.format(e))
        raise


def get_body(email_data: message.Message) -> str:
    if email_data.is_multipart():
        text: str = ''
        for part in email_data.walk():
            if part.get_content_type() == 'text/plain':
                content_disposition: str = str(part.get('Content-Disposition'))
                if 'attachment' not in content_disposition:
                    body: str = part.get_payload(decode=True).decode()
                    text += body
        return text
    else:
        content_type: str = email_data.get_content_type()

        if content_type == 'text/plain':
            return email_data.get_payload(decode=True).decode()
    return ''


def get_email_details(email_ids: list[bytes]) -> list[tuple[bytes, message.Message]]:
    emails: list[tuple[bytes, message.Message]] = []
    for email_id in email_ids:
        read_style = '(BODY[])' if os.getenv('MARK_AS_READ') == 'true' else '(BODY.PEEK[])'
        status, msg_data = mail.fetch(email_id.decode('utf-8'), read_style)

        if status != 'OK':
            logger.warn('Failed to fetch email ID: {}'.format(email_id))
            continue

        emails.append((email_id, message_from_bytes(msg_data[0][1])))
    return emails


def get_emails(lookup_string: str) -> tuple[str, list[bytes]]:
    return mail.search(None, lookup_string)


def read_emails(lookup_string: str) -> list[tuple[bytes, message.Message]] | None:
    if not mail:
        logger.error('No mail connection')
        return None

    # Search for unread emails
    status: str
    messages: list[bytes]
    status, messages = get_emails(lookup_string)
    if status != 'OK':
        logger.warn('No messages found!')
        return None

    # Get the list of email IDs
    email_ids: list[bytes] = messages[0].split()
    return get_email_details(email_ids)


def get_recipe_urls(emails: list[tuple[bytes, message.Message]]) -> list[str]:
    return [url.strip() for email_id, email_data in emails for url in get_body(email_data).split('\n') if url.strip()]


def get_whitelisted_emails_query() -> str:
    whitelisted_emails: list[str] = os.getenv('EMAILS_WHITELIST').split(',')
    whitelisted_emails.append(os.getenv('EMAIL_USER'))
    partial_queries: list[str] = [f'FROM "{email_address}"' for email_address
                                  in whitelisted_emails if email_address.strip()]
    if not partial_queries:
        return ''
    elif len(partial_queries) == 1:
        return partial_queries[0]

    conditions: list[str] = [f'({partial_query})' for partial_query in partial_queries]
    final_email: str = conditions.pop(-1)
    conditions[-1] = f'{conditions[-1]} {final_email}'
    return f'OR {" OR ".join(conditions)}'


def get_urls_from_emails() -> list[str]:
    assign_mail_instance()
    recipe_emails_filter: str = f'(UNSEEN SUBJECT "Recipes" {get_whitelisted_emails_query()})'
    recipe_emails: list[tuple[bytes, message.Message]] | None = read_emails(recipe_emails_filter)
    recipe_urls: list[str] = get_recipe_urls(recipe_emails)
    if recipe_urls:
        logger.info(f'Loaded {len(recipe_urls)} recipe URLs:\n{json.dumps(recipe_urls, indent=4)}')
    else:
        logger.info('No recipe URLs found in emails')
    return get_recipe_urls(recipe_emails)
