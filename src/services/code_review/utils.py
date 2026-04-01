import requests
from cachetools import TTLCache

TOKEN_TTL = 3300
TOKEN_CACHE_SIZE = 100
_token_cache = TTLCache(maxsize=TOKEN_CACHE_SIZE, ttl=TOKEN_TTL)


def get_access_token(client_id: str, client_secret: str) -> str:
    if client_id in _token_cache:
        return _token_cache[client_id]

    url = "https://login.microsoftonline.com/autodesk.onmicrosoft.com/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://cognitiveservices.azure.com/.default",
        "grant_type": "client_credentials",
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]


def make_azure_openai_request(
    api_url: str, json: dict, client_id: str, client_secret: str, api_key: str
) -> dict:
    access_token = get_access_token(client_id, client_secret)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "api-key": api_key,
    }
    response = requests.post(api_url, headers=headers, json=json)
    response.raise_for_status()
    return response.json()
