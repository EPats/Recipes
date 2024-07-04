import atexit
import email
import imaplib
import os

from dotenv import load_dotenv

import logger

mail: imaplib.IMAP4_SSL | None = None


@atexit.register
def close_mail_connection():
    print('Closing mail connection')
    if mail:
        mail.close()
        mail.logout()
        print('Mail connection closed')


def assign_mail_instance():
    global mail
    mail = connect_to_gmail_imap()


def connect_to_gmail_imap():
    imap_url = os.getenv('IMAP_SERVER')
    try:
        global mail
        mail = imaplib.IMAP4_SSL(imap_url)
        mail.login(os.getenv('GMAIL_USER'), os.getenv('GMAIL_PASSWORD'))
        mail.select('inbox')  # Connect to the inbox.
        return mail
    except imaplib.IMAP4.error as e:
        logger.logger.error('Connection failed: {}'.format(e))
        raise


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


def mark_email_as_read(email_id):
    mail.store(email_id, '+FLAGS', '\\Seen')


def get_email_details(email_ids):
    emails = []
    for email_id in email_ids:
        # Fetch the email by ID using BODY.PEEK to avoid marking it as read
        status, msg_data = mail.fetch(email_id, '(BODY.PEEK[])')

        if status != 'OK':
            print('Failed to fetch email ID: {}'.format(email_id))
            continue

        emails.append((email_id, email.message_from_bytes(msg_data[0][1])))
    return emails


def get_emails(lookup_string):
    return mail.search(None, lookup_string)


def read_emails(lookup_string):
    if not mail:
        logger.logger.error('No mail connection')
        return

    # Search for unread emails
    status, messages = get_emails(lookup_string)
    if status != 'OK':
        print('No messages found!')
        return

    # Get the list of email IDs
    email_ids = messages[0].split()
    return get_email_details(email_ids)


def get_recipe_urls(emails):
    return [url.strip() for email_id, email_data in emails for url in get_body(email_data).split('\n') if url.strip()]


def get_whitelisted_emails_query():
    whitelisted_emails = [f'FROM "{email}"' for email in os.getenv("FROM_EMAILS").split(',')]
    if not whitelisted_emails:
        return ''
    elif len(whitelisted_emails) == 1:
        return whitelisted_emails[0]

    conditions = [f'({whitelisted_email})' for whitelisted_email in whitelisted_emails]
    final_email = conditions.pop(-1)
    conditions[-1] = f'{conditions[-1]} {final_email}'
    return f'OR {" OR ".join(conditions)}'


def main():
    assign_mail_instance()

    recipe_emails_filter = f'(UNSEEN SUBJECT "Recipes" {get_whitelisted_emails_query()})'
    print(f'{recipe_emails_filter=}')
    recipe_emails = read_emails(recipe_emails_filter)
    urls = get_recipe_urls(recipe_emails)
    print(urls)


if __name__ == '__main__':
    load_dotenv()
    main()
