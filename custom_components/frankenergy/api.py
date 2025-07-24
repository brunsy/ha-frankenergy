"""Frank Energy API."""

import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Any
from collections.abc import Mapping
import json
from urllib.parse import parse_qs

_LOGGER = logging.getLogger(__name__)

class FrankEnergyApi:
    """Define the Frank Energy API."""

    def __init__(self, email, password):
        """Initialise the API."""
        _LOGGER.warning("__init__")
        self._client_id = "9b63be56-54d0-4706-bfb5-69707d4f4f89"
        self._redirect_uri = 'eol://oauth/redirect'
        self._url_token_base = "https://energyonlineb2cprod.b2clogin.com/energyonlineb2cprod.onmicrosoft.com"
        self._url_data_base = "https://mobile-api.energyonline.co.nz"
        self._p = "B2C_1A_signin"

        self._email = email
        self._password = password

        self._accountNumber = None
        self._token = None
        self._refresh_token = None
        self._refresh_token_expires_in = 0
        self._access_token_expires_in = 0

    def get_setting_json(self, page: str) -> Mapping[str, Any] | None:
        """Get the settings from json result."""
        for line in page.splitlines():
            if line.startswith("var SETTINGS = ") and line.endswith(";"):
                json_string = line.removeprefix("var SETTINGS = ").removesuffix(";")
                return json.loads(json_string)
        return None

    async def get_refresh_token(self):
        """Get the refresh token."""
        _LOGGER.debug("API get_refresh_token")

        jar = aiohttp.CookieJar(quote_cookie=False)
        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            url = f"{self._url_token_base}/oauth2/v2.0/authorize"
            scope = f'openid offline_access {self._client_id}'
            params = {
                'p': self._p,
                'client_id': self._client_id,
                'response_type': 'code',
                'response_mode': 'query',
                'scope': scope,
                'redirect_uri': self._redirect_uri,
            }

            _LOGGER.debug("Step: 1")
            async with session.get(url, params=params) as response:
                response_text = await response.text()

            settings_json = self.get_setting_json(response_text)
            trans_id = settings_json.get("transId")
            csrf = settings_json.get("csrf")

            url = f"{self._url_token_base}/{self._p}/SelfAsserted?tx={trans_id}&p={self._p}"
            payload = {
                "request_type": "RESPONSE",
                "email": self._email,
            }
            headers = {
                'X-CSRF-TOKEN': csrf,
            }
            _LOGGER.debug("Step: 2")
            async with session.post(url, headers=headers, data=payload) as response:
                await response.text()

            url = f"{self._url_token_base}/{self._p}/api/SelfAsserted/confirmed"
            params = {
                'csrf_token': csrf,
                'tx': trans_id,
                'p': self._p,
            }
            _LOGGER.debug("Step: 3")
            async with session.get(url, params=params) as response:
                response_text = await response.text()
                csrf_cookie = response.cookies.get('x-ms-cpim-csrf')
                if csrf_cookie is None:
                    _LOGGER.error("CSRF cookie not found in step 3 response")
                    raise RuntimeError("Missing CSRF cookie during login flow")
                csrf = csrf_cookie.value

            payload = {
                "request_type": "RESPONSE",
                "signInName": self._email,
                "password": self._password
            }

            headers = {
                'X-CSRF-TOKEN': csrf,
            }

            url = f"{self._url_token_base}/{self._p}/SelfAsserted?tx={trans_id}&p={self._p}"
            _LOGGER.debug("Step: 4")
            async with session.post(url, headers=headers, data=payload) as response:
                await response.text()

            url = f"{self._url_token_base}/{self._p}/api/CombinedSigninAndSignup/confirmed"
            params = {
                'rememberMe': 'false',
                'csrf_token': csrf,
                'tx': trans_id,
                'p': self._p
            }
            headers = {}
            _LOGGER.debug("Step: 5")
            async with session.get(url, headers=headers, params=params, allow_redirects=False) as response:
                response.raise_for_status()
                response_data = await response.text()

                location = response.headers.get('Location', '')
                query_params = parse_qs(location.split('?', 1)[1])
                if 'error' in query_params:
                    error = query_params['error'][0]
                    _LOGGER.error("Error in response: %s", error)
                    error_description = query_params['error_description'][0]
                    _LOGGER.error("Error description in response: %s", error_description)

            code = query_params['code'][0]
            url = f"{self._url_token_base}/{self._p}/oauth2/v2.0/token"
            params = {
                'p': self._p,
                'grant_type': 'authorization_code',
                'client_id': self._client_id,
                'scope': scope,
                'redirect_uri': self._redirect_uri,
                'code': code,
            }

            headers = {}
            async with session.get(url, headers=headers, params=params) as response:
                response_data = await response.json()
                refresh_token = response_data.get('refresh_token')
                access_token = response_data.get('access_token')
                refresh_token_expires_in = response_data.get('refresh_token_expires_in')
                access_token_expires_in = response_data.get('expires_in')

            self._token = access_token
            self._refresh_token = refresh_token
            self._refresh_token_expires_in = refresh_token_expires_in
            self._access_token_expires_in = access_token_expires_in
            _LOGGER.debug("Refresh token retrieved successfully")

    async def get_api_token(self):
        """Get token from the Frank Energy API."""
        token_data = {
            "p": self._p,
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "refresh_token": self._refresh_token,
        }

        jar = aiohttp.CookieJar(quote_cookie=False)
        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            url = f"{self._url_token_base}/oauth2/v2.0/token"
            async with session.post(url, data=token_data) as response:
                if response.status == 200:
                    jsonResult = await response.json()
                    self._token = jsonResult["access_token"]
                    _LOGGER.debug(f"Auth Token: {self._token}")
                else:
                    _LOGGER.error("Failed to retrieve the token page.")

    async def get_data(self):
        """Get data from the API."""

        access_token_threshold = timedelta(minutes=5).total_seconds()
        if self._access_token_expires_in <= access_token_threshold:
            _LOGGER.warning("Access token needs renewing")
            await self.get_api_token()

        refresh_token_threshold = timedelta(minutes=5).total_seconds()
        if self._refresh_token_expires_in <= refresh_token_threshold:
            _LOGGER.warning("Refresh token needs renewing")
            await self.get_refresh_token()

        headers = {
            "authorization": "Bearer " + self._token,
            "brand-id": "GEOL",
            "platform": "Android",
            "mobile-build-number": "1"
        }

        to_date = datetime.now()
        from_date = to_date - timedelta(days=4)

        url = f"{self._url_data_base}/v2/private/usage/electricity/aggregatedSiteUsage/hourly"
        params = {
            'startDate': from_date.strftime("%Y-%m-%d"),
            'endDate': to_date.strftime("%Y-%m-%d"),
        }

        jar = aiohttp.CookieJar(quote_cookie=False)
        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if not data:
                        _LOGGER.warning("Fetched consumption successfully but there was no data")
                    return data
                else:
                    _LOGGER.error("Could not fetch consumption")
                    return None
