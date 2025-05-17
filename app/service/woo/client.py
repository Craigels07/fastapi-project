"""Helper to send WhatsApp messages."""

import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin


class WooCommerceAPIClient:
    def __init__(self, base_url, consumer_key, consumer_secret):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(consumer_key, consumer_secret)

    def _request(self, method, endpoint, params=None, data=None):
        url = urljoin(self.base_url, f"/wp-json/wc/v3/{endpoint}")
        response = requests.request(
            method, url, auth=self.auth, params=params, json=data
        )
        response.raise_for_status()
        return response.json()
