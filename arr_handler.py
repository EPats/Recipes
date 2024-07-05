import json
import time

from bs4 import BeautifulSoup

import email_handler
from logger import get_logger
import re
import os
import requests


def get_tvdb_series_id(url: str) -> str:
    try:
        response: requests.Response = requests.get(url)
        html_content: str = response.text

        # Parse the HTML content
        soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')

        # Find the series ID
        series_id: str = soup.find('a', class_='btn btn-success favorite_button').get('data-id')
        return series_id
    except requests.exceptions.RequestException as e:
        get_logger().error(f'Error fetching TVDB series ID: {e}')
        return ''


def get_media_components(url: str) -> tuple[str, str, str]:
    base_url: str = email_handler.get_base_url(url)
    id_site: str = base_url.split('.')[0]

    service: str = ''
    media_id: str = ''
    if id_site in ['tmdb', 'themoviedb']:
        url_split = url.split(f'{base_url}/')
        url_sections = url_split[1].split('/')
        service = 'Radarr' if url_sections[0].upper() == 'MOVIE' else 'Sonarr'
        media_id = re.findall(r'^\d+', url_sections[1])[0]
        id_site = 'tmdb'
    elif id_site == 'imdb':
        service = 'Radarr'
        media_id = re.findall(r'tt\d+', url)[0]
    elif id_site == 'thetvdb':
        id_site = 'tvdb'
        service = 'Sonarr'
        media_id = get_tvdb_series_id(url)
    return service, media_id, id_site



def add_to_service(service: str, media_id: str, id_site: str):
    service_address: str = os.getenv(f'{service.upper()}_ADDRESS')
    service_api_key: str = os.getenv(f'{service.upper()}_API_KEY')
    service_media_path: str = os.getenv(f'{service.upper()}_FILES')
    service_profile_id: int = int(os.getenv(f'{service.upper()}_PROFILE_ID'))
    add_options_title = 'searchForMovie' if service.upper() == 'RADARR' else 'searchForMissingEpisodes'
    database_id = 'tmdbId' if service.upper() == 'RADARR' else 'tvdbId'

    lookup_url: str
    request_url: str
    if service.upper() == 'RADARR':
        lookup_url = f'{service_address}/api/v3/movie/lookup/{id_site}?{id_site}id={media_id}&apikey={service_api_key}'
        request_url = f'{service_address}/api/v3/movie?apikey={service_api_key}'
    elif service.upper() == 'SONARR':
        lookup_url = f'{service_address}/api/v3/series/lookup?term={id_site}:{media_id}&apikey={service_api_key}'
        request_url = f'{service_address}/api/v3/series?apikey={service_api_key}'
    else:
        get_logger().error(f'Unknown service "{service}" for {media_id} from {id_site}')
        return

    media_details = get_json_response(lookup_url, media_id, id_site)

    if not media_details:
        get_logger().error(f'No data found for {media_id} from {id_site}')
        return

    media_to_add = {
        'title': media_details['title'],
        'qualityProfileId': service_profile_id,
        'titleSlug': media_details['titleSlug'],
        'images': media_details['images'],
        database_id: int(media_details[database_id]),
        'year': media_details['year'],
        'rootFolderPath': service_media_path,
        'monitored': True,
        'addOptions': {
            add_options_title: True  # Set to True if you want Sonarr to search for the episodes immediately
        }
    }

    if service.upper() == 'SONARR':
        media_to_add['seasons'] = [
            {'seasonNumber': season['seasonNumber'], 'monitored': True}
            for season in media_details['seasons']
        ]

    # Perform the request to add the series
    response: requests.Response = requests.post(request_url, json=media_to_add)
    added_media_response: list | dict = response.json()

    if isinstance(added_media_response, list):
        get_logger().error(f'Problem adding {media_id} from {id_site} to {service}: \n{json.dumps(added_media_response, indent=4)}')
    else:
        get_logger().info(f'Added {added_media_response['title']} through {service} API')


def get_json_response(url: str, media_id: str, id_site: str) -> dict:
    try:
        response = requests.get(url)
        if response.status_code == 200:
            response_json = response.json()
            if isinstance(response_json, list):
                return response_json[0]
            return response_json
        else:
            get_logger().warning(f'Failed to get data for {media_id} from {id_site}: {response.status_code}')
            return {}
    except requests.exceptions.RequestException as req_err:
        get_logger().error(f'Error retrieving data for {media_id} from {id_site}: {req_err}')


def process_media_request_emails(email_bodies: list[str]) -> None:
    urls: list[str] = email_handler.get_urls(email_bodies)
    get_logger().info(f'Media request url queue size: {len(urls)}')

    service: str
    media_id: str
    id_site: str
    for url in urls:
        service, media_id, id_site = get_media_components(url)

        if not service or not media_id or not id_site:
            get_logger().warning(f'No match found for {url}')
            continue

        add_to_service(service, media_id, id_site)

        time.sleep(1)  # Wait for 1 second before processing the next URL

