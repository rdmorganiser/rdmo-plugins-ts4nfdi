import json
from urllib.request import Request, urlopen

from rdmo_ts4nfdi.utils import add_query_params, join_url

API_BASE_URL_DEFAULT = 'https://terminology.services.base4nfdi.de/api-gateway'


class GatewayProviderClient:
    """Small HTTP adapter used by RDMO dynamic option providers."""

    def get(self, provider_config: dict, params: dict):
        request_url = self.prepare_request_url(provider_config, params)
        request = Request(
            request_url,
            headers=self.request_headers(provider_config),
        )
        with urlopen(request, timeout=provider_config.get('timeout', 10)) as response:
            return json.load(response)

    @staticmethod
    def request_url(provider_config: dict) -> str:
        if provider_config.get('api_url'):
            return provider_config['api_url']
        return join_url(
            provider_config.get('base_url', API_BASE_URL_DEFAULT),
            provider_config.get('endpoint', ''),
        )

    @classmethod
    def prepare_request_url(cls, provider_config: dict, params: dict) -> str:
        """Build the exact URL passed to urllib, including encoded parameters."""

        return add_query_params(cls.request_url(provider_config), params)

    @staticmethod
    def request_headers(provider_config: dict) -> dict[str, str]:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'rdmo-ts4nfdi/provider-adapter',
        }
        if provider_config.get('api_token'):
            headers['Authorization'] = f'Bearer {provider_config["api_token"]}'
        return headers
