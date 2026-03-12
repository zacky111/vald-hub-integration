import os
import requests
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class ValdHubClient:
    """Client for interacting with Vald Hub API"""
    
    def __init__(self):
        self.api_key = os.getenv('VALD_HUB_API_KEY')
        self.base_url = os.getenv('VALD_HUB_BASE_URL', 'https://api.vald-hub.com')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        if not self.api_key:
            logger.warning("VALD_HUB_API_KEY not set in environment variables")
    
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
