import atexit
from email import message, message_from_bytes
from email.header import decode_header
import imaplib
import os
import re

from logger import get_logger


mail: imaplib.IMAP4_SSL | None = None


@atexit.register
def exit_handler() -> None:
    close_mail_connection()


def close_mail_connection() -> None:
    get_logger().info('Closing mail connection')
    global mail
    if mail:
        mail.close()
        mail.logout()
        mail = None
        get_logger().info('Mail connection closed')
    else:
        get_logger().warning('No mail connection to close')


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
        get_logger().error('Connection failed: {}'.format(e))
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


def get_email_details(email_ids: list[bytes]) -> list[tuple[bytes, str, str]]:
    emails: list[tuple[bytes, str, str]] = []
    for email_id in email_ids:
        read_style: str = '(BODY[])' if os.getenv('MARK_AS_READ') == 'true' else '(BODY.PEEK[])'
        status: str
        msg_data: list[tuple[bytes, bytes]]
        subject: str
        encoding: str

        status, msg_data = mail.fetch(email_id.decode('utf-8'), read_style)
        if status != 'OK':
            get_logger().warning('Failed to fetch email ID: {}'.format(email_id))
            continue

        msg = message_from_bytes(msg_data[0][1])
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")

        body: str = get_body(msg)

        emails.append((email_id, subject, body))
    return emails


def get_emails(lookup_string: str) -> tuple[str, list[bytes]]:
    return mail.search(None, lookup_string)


def read_emails(lookup_string: str) -> list[tuple[bytes, str, str]] | None:
    if not mail:
        get_logger().error('No mail connection')
        return None

    # Search for unread emails
    status: str
    messages: list[bytes]
    status, messages = get_emails(lookup_string)
    if status != 'OK':
        get_logger().warning('No messages found!')
        return None

    # Get the list of email IDs
    email_ids: list[bytes] = messages[0].split()
    return get_email_details(email_ids)


def get_compound_query(query_type: str, query_elements: list[str]) -> str:
    partial_queries: list[str] = [f'{query_type} "{query_element}"' for query_element
                                  in query_elements if query_element.strip()]
    if not partial_queries:
        return ''
    elif len(partial_queries) == 1:
        return partial_queries[0]

    conditions: list[str] = [f'({partial_query})' for partial_query in partial_queries]
    final_query: str = conditions.pop(-1)
    conditions[-1] = f'{conditions[-1]} {final_query}'
    return f'OR {" OR ".join(conditions)}'


def get_whitelisted_query() -> str:
    whitelisted_emails: list[str] = os.getenv('EMAILS_WHITELIST').split(',')
    whitelisted_emails.append(os.getenv('EMAIL_USER'))
    return get_compound_query('FROM', whitelisted_emails)


def get_subjects_list() -> list[str]:
    return os.getenv('EMAIL_SUBJECTS').split(',')


def get_subjects_query() -> str:
    subjects: list[str] = get_subjects_list()
    return get_compound_query('SUBJECT', subjects)


def create_subject_queues() -> dict[str, list[str]]:
    emails_by_subject: dict[str, list[str]] = {subject: [] for subject in get_subjects_list()}
    emails_by_subject['Other'] = []
    return emails_by_subject


def get_emails_by_subject() -> dict[str, list[str]]:
    assign_mail_instance()
    emails_filter: str = f'(UNSEEN {get_subjects_query()} {get_whitelisted_query()})'
    emails: list[tuple[bytes, str, str]] | None = read_emails(emails_filter) or []

    subjects: list[str] = get_subjects_list()
    subject: str

    emails_by_subject: dict[str, list[str]] = create_subject_queues()

    for email_obj in emails:
        email_id, subject, body = email_obj
        subject = subject if subject in subjects else 'Other'
        emails_by_subject[subject].append(body)

    return emails_by_subject


def get_urls(email_bodies: list[str]) -> list[str]:
    urls: list[str] = []
    for email_body in email_bodies:
        urls.extend(re.findall(r'(https?://\S+)', email_body))
    return urls


def get_base_url(url: str) -> str:
    base: str = re.sub(r'(https?://)?(www\.)?', '', url)
    base = base.split('/')[0]
    return base
