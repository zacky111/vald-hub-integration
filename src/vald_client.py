import os
import requests
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import logging
import time

load_dotenv()

logger = logging.getLogger(__name__)


class ValdHubClient:
    """Client for interacting with Vald Hub API"""
    
    def __init__(self):

        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.tenant_id = os.getenv('TENANT_ID')

        self.token_cache = {
            "access_token": None,
            "expires_at": None,
        }
        
        if not self.client_id or not self.client_secret or not self.tenant_id:
            logger.warning("One or more required environment variables are not set")



        
    def get_token(self, client_id: str, client_secret: str) -> str:
        """
        Retrieves a bearer token with client credentials.
        Caches token until expiration.

        :param client_id: client ID from support
        :param client_secret: client secret from support
        :return: Authorization header value, e.g. "Bearer <token>"
        """
        now_ms = int(time.time() * 1000)
        if (
            self.token_cache["access_token"]
            and self.token_cache["expires_at"]
            and self.token_cache["expires_at"] > now_ms
        ):
            print("Returning cached token:", self.token_cache["access_token"])
            return self.token_cache["access_token"]

        url_auth = "https://auth.prd.vald.com/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": "vald-api-external",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            resp = requests.post(url_auth, data=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            expires_in = data.get("expires_in")
            access_token = data.get("access_token")
            if not access_token or not expires_in:
                raise ValueError("Missing access_token or expires_in in auth response")

            bearer = f"Bearer {access_token}"
            self.token_cache["access_token"] = bearer
            self.token_cache["expires_at"] = now_ms + int(expires_in) * 1000

            print("Caching new token:", self.token_cache)
            return bearer

        except requests.RequestException as e:
            print("Error retrieving token:", str(e))
            raise

        
    
    def _make_request(self, endpoint: str, method: str = 'GET', params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to Vald Hub API"""
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        

    ## to be deleted
    
    def get_athletes(self) -> Optional[List[Dict]]:
        """Fetch list of athletes from Vald Hub"""
        result = self._make_request('/athletes')
        return result.get('data', []) if result else []
    
    def get_athlete_data(self, athlete_id: str) -> Optional[Dict]:
        """Fetch specific athlete performance data"""
        return self._make_request(f'/athletes/{athlete_id}')
    
    def get_assessments(self, athlete_id: Optional[str] = None) -> Optional[List[Dict]]:
        """Fetch assessments, optionally filtered by athlete"""
        params = {'athlete_id': athlete_id} if athlete_id else None
        result = self._make_request('/assessments', params=params)
        return result.get('data', []) if result else []
    
    def get_assessment_details(self, assessment_id: str) -> Optional[Dict]:
        """Fetch detailed assessment data"""
        return self._make_request(f'/assessments/{assessment_id}')
    
    def get_metrics(self, athlete_id: str) -> Optional[Dict]:
        """Fetch performance metrics for an athlete"""
        return self._make_request(f'/metrics/{athlete_id}')
    
    def test_connection(self) -> bool:
        """Test connection to Vald Hub API"""
        result = self._make_request('/health')
        return result is not None
