import os
import requests
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import logging
import time
import json
import pandas as pd

load_dotenv()

logger = logging.getLogger(__name__)

url={
    "auth": "https://auth.prd.vald.com/oauth/token",
    "externalTenants_version": "https://prd-euw-api-externaltenants.valdperformance.com/version",
    "get_profiles": "https://prd-euw-api-externalprofile.valdperformance.com/profiles",
    "get_groups": "https://prd-euw-api-externaltenants.valdperformance.com/groups",
    "get_training_sessions": "https://prd-euw-api-extforcedecks.valdperformance.com/tests"
}

# Global token cache to persist across Streamlit reruns
_token_cache = {
    "access_token": None,
    "expires_at": None,
}


class ValdHubClient:
    """Client for interacting with Vald Hub API"""
    
    def __init__(self):

        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.tenant_id = os.getenv('TENANT_ID')
        
        if not self.client_id or not self.client_secret or not self.tenant_id:
            logger.warning("One or more required environment variables are not set")



        
    def get_token(self, client_id: str, client_secret: str) -> str:
        """
        Retrieves a bearer token with client credentials.
        Caches token globally until expiration to persist across Streamlit reruns.

        :param client_id: client ID from support
        :param client_secret: client secret from support
        :return: Authorization header value, e.g. "Bearer <token>"
        """
        global _token_cache
        
        now_ms = int(time.time() * 1000)
        if (
            _token_cache["access_token"]
            and _token_cache["expires_at"]
            and _token_cache["expires_at"] > now_ms
        ):
            logger.info("Using cached token (valid for ~%d min)", 
                       (_token_cache["expires_at"] - now_ms) // 60000)
            return _token_cache["access_token"]

        logger.info("Fetching new token from auth server...")
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": "vald-api-external",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            resp = requests.post(url["auth"], data=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            expires_in = data.get("expires_in")
            access_token = data.get("access_token")
            if not access_token or not expires_in:
                raise ValueError("Missing access_token or expires_in in auth response")

            bearer = f"Bearer {access_token}"
            _token_cache["access_token"] = bearer
            _token_cache["expires_at"] = now_ms + int(expires_in) * 1000

            logger.info("New token cached (expires in %d hours)", expires_in // 3600)
            return bearer

        except requests.RequestException as e:
            logger.error("Error retrieving token: %s", str(e))
            raise

    def get_version(self):
        try:
            response = requests.get(url["externalTenants_version"], timeout=10)
            response.raise_for_status()

            text = response.text
            #print("Status:", response.status_code)
            #print("Headers:", response.headers)
            #print("Body:", text)

            try:
                data = response.json()
                print("JSON:", data)
                return data
            except ValueError:
                # Jeśli serwer nie zwróci JSON, zwracamy tekst
                return text

        except requests.RequestException as e:
            print("Error retrieving version:", str(e))
            return None

    def get_profiles(self) -> Optional[Dict]:
        """Fetch athlete profiles from Vald Hub"""
        try:
            response = requests.get(
                url["get_profiles"], 
                timeout=10, 
                params={"TenantID": self.tenant_id}, 
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)}
            )
            response.raise_for_status()
            data = response.json()
            
            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching profiles: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing profiles: {e}")
            return None

    def get_groups(self) -> Optional[Dict]:
        """Fetch groups from Vald Hub"""
        try:
            response = requests.get(
                url["get_groups"], 
                timeout=10,
                params={"TenantID": self.tenant_id},
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)}
            )
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching groups: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing groups: {e}")
            return None
        
    def get_profiles_details(self, profile_id: str) -> Optional[Dict]:
        """Fetch detailed profile data for a specific athlete"""
        try:
            response = requests.get(
                f"{url['get_profiles']}/{profile_id}", 
                timeout=10, 
                params={"TenantID": self.tenant_id}, 
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)}
            )
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching profile details: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing profile details: {e}")
            return None
        
    def get_group_details(self, group_id: str) -> Optional[Dict]:
        """Fetch detailed data for a specific group"""
        try:
            response = requests.get(
                f"{url['get_groups']}/{group_id}", 
                timeout=10, 
                params={"TenantID": self.tenant_id}, 
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)}
            )
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching group details: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing group details: {e}")
            return None

    def get_training_sessions(
        self,
        profile_id=None,
        modified_from_utc="2026-01-01T00:00:00.000Z",
        page_size=100,
        page_number=1,
        fetch_all=False,
    ) -> Optional[Dict]:
        "Retrieves a list of ForceDecks training sessions. Supports paging."

        date = modified_from_utc or "2026-01-01T00:00:00.000Z"

        def _fetch_page(page_num):
            params = {
                "TenantId": str(self.tenant_id),
                "ModifiedFromUtc": date,
                "PageSize": page_size,
                "Page": page_num,
            }
            if profile_id:
                params["ProfileId"] = profile_id

            response = requests.get(
                url["get_training_sessions"],
                timeout=10,
                params=params,
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)},
            )
            response.raise_for_status()
            return response.json()

        try:
            if not fetch_all:
                data = _fetch_page(page_number)
                return data

            # Fetch all pages iteratively
            aggregated = {"tests": []}
            current_page = page_number
            while True:
                data = _fetch_page(current_page)
                tests = data.get("tests", [])
                aggregated["tests"].extend(tests)

                # If backend field exists for page count/next token, use it; fallback on page_size
                next_page_exists = False
                if "pageCount" in data and "page" in data:
                    next_page_exists = data.get("page") < data.get("pageCount")
                elif len(tests) >= page_size:
                    next_page_exists = True

                if not next_page_exists:
                    break

                current_page += 1

            return aggregated

        except requests.RequestException as e:
            logger.error(f"Error fetching training sessions: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing training sessions: {e}")
            return None
        
    def get_training_sessions_all(
        self,
        profile_id=None,
        modified_from_utc="2026-01-01T00:00:00.000Z",
        max_loops=10
        ):
    

        """Fetch all sessions using time-based pagination"""
        
        def _fetch(date):
            params = {
                "TenantId": str(self.tenant_id),
                "ModifiedFromUtc": date,
            }
            if profile_id:
                params["ProfileId"] = profile_id

            response = requests.get(
                url["get_training_sessions"],
                timeout=10,
                params=params,
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)},
            )

            response.raise_for_status()

            # DEBUG
            print(f"Status: {response.status_code}, length: {len(response.text)}")

            if not response.text.strip():
                return {"tests": []}

            try:
                return response.json()
            except ValueError:
                print("⚠️ Invalid JSON response:", response.text[:200])
                return {"tests": []}
            

        try:
            aggregated = []
            current_date = pd.to_datetime(modified_from_utc)

            for _ in range(max_loops):
                data = _fetch(current_date)

                if not data:
                    break

                tests = data.get("tests", [])
                if not tests:
                    break

                aggregated.extend(tests)

                dates = []
                for t in tests:
                    date_str = t.get("modifiedDateUtc") or t.get("recordedDateUtc")
                    if date_str:
                        try:
                            dates.append(pd.to_datetime(date_str, utc=True))
                        except Exception as e:
                            logger.warning(f"Invalid date format: {date_str} ({e})")

                if not dates:
                    break

                newest_date = max(dates)

                if newest_date <= current_date:
                    break

                current_date = newest_date + pd.Timedelta(seconds=1)

                time.sleep(0.2)
                #print(f"Fetching from: {current_date}, got: {len(tests)}")

            #print(f"returning: {aggregated}")
            return {"tests": aggregated}

        except Exception as e:
            logger.error(f"Error fetching sessions: {e}")
            if aggregated != []:
                logger.info(f"Returning aggregated data with {len(aggregated)} tests")
                return {"tests": aggregated}
            else:
                return None
            
    def get_test_details(self, teamId, testId) -> Optional[Dict]:
        """Fetch detailed data for a specific test/training session"""
        try:
            response = requests.get(
                url=f"https://prd-euw-api-extforcedecks.valdperformance.com/v2019q3/teams/{teamId}/tests/{testId}/trials", 
                timeout=10,  
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)}
            )
            response.raise_for_status()
            data = response.json()

            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching test details: {e}")
            logger.error(f"Requested URL: {response.url if 'response' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Error parsing test details: {e}")
            return None

    def get_raw_data(self, teamId, testId, includeSampleData=False) -> Optional[Dict]:
        """Fetch raw data for a specific test/training session"""
        try:
            response = requests.get(
                url=f"https://prd-euw-api-extforcedecks.valdperformance.com/v2019q3/teams/{teamId}/tests/{testId}/recording?includeSampleData={includeSampleData}", 
                timeout=10,  
                headers={"Authorization": self.get_token(self.client_id, self.client_secret)}
            )
            response.raise_for_status()
            data = response.json()

            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching raw data: {e}")
            logger.error(f"Requested URL: {response.url if 'response' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Error parsing raw data: {e}")
            return None
