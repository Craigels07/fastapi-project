"""
Meta Graph API Service
Handles WhatsApp Business Account (WABA) verification and management
via Meta's Graph API.
"""

import os
import httpx
from typing import Dict


class MetaGraphAPIService:
    """Service for interacting with Meta Graph API"""

    def __init__(self):
        self.access_token = os.getenv("META_SYSTEM_USER_ACCESS_TOKEN")
        self.graph_api_version = os.getenv("META_GRAPH_API_VERSION", "v18.0")
        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"
        
        if not self.access_token:
            raise ValueError("META_SYSTEM_USER_ACCESS_TOKEN must be set in environment")

    async def verify_waba(self, waba_id: str) -> Dict[str, str]:
        """
        Verify a WhatsApp Business Account (WABA) via Meta Graph API.
        MUST be called BEFORE sender registration to ensure WABA is verified.
        
        Args:
            waba_id: WhatsApp Business Account ID from Meta Embedded Signup
            
        Returns:
            Dictionary containing:
                - id: WABA ID
                - name: Business name
                - business_verification_status: VERIFIED, PENDING, or FAILED
                
        Raises:
            Exception: If WABA verification check fails or WABA is not verified
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{waba_id}",
                    params={
                        "fields": "business_verification_status,name,id",
                        "access_token": self.access_token
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "Unknown error")
                    raise Exception(f"Meta Graph API error: {error_message}")
                
                data = response.json()
                
                verification_status = data.get("business_verification_status", "UNKNOWN")
                
                # CRITICAL: Only allow VERIFIED WABAs
                if verification_status != "VERIFIED":
                    raise Exception(
                        f"WABA {waba_id} is not verified. Status: {verification_status}. "
                        "Please complete business verification in Meta Business Manager before proceeding."
                    )
                
                return {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "business_verification_status": verification_status
                }
                
        except httpx.HTTPError as e:
            raise Exception(f"Failed to verify WABA: {str(e)}")

    async def get_waba_phone_numbers(self, waba_id: str) -> list:
        """
        Get all phone numbers registered to a WABA.
        
        Args:
            waba_id: WhatsApp Business Account ID
            
        Returns:
            List of phone number dictionaries
            
        Raises:
            Exception: If API call fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{waba_id}/phone_numbers",
                    params={
                        "access_token": self.access_token
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "Unknown error")
                    raise Exception(f"Meta Graph API error: {error_message}")
                
                data = response.json()
                return data.get("data", [])
                
        except httpx.HTTPError as e:
            raise Exception(f"Failed to get WABA phone numbers: {str(e)}")

    async def get_phone_number_details(self, phone_number_id: str) -> Dict:
        """
        Get details for a specific phone number.
        
        Args:
            phone_number_id: Phone number ID from Meta
            
        Returns:
            Dictionary containing phone number details
            
        Raises:
            Exception: If API call fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{phone_number_id}",
                    params={
                        "fields": "display_phone_number,verified_name,quality_rating,code_verification_status",
                        "access_token": self.access_token
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "Unknown error")
                    raise Exception(f"Meta Graph API error: {error_message}")
                
                return response.json()
                
        except httpx.HTTPError as e:
            raise Exception(f"Failed to get phone number details: {str(e)}")
