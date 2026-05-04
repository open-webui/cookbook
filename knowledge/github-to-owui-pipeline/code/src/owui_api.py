#!/usr/bin/env python3
"""
OpenWebUI API Client

This module provides a client for interacting with the OpenWebUI API,
specifically for managing knowledge collections and files.
"""

import os
import requests
import logging
import time
import re
from typing import Dict, List, Optional, Any, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OpenWebUIClient:
    """Client for interacting with the OpenWebUI API."""
    
    def __init__(self, base_url: str, api_key: str, jwt_token: str, 
                 cf_client_id: Optional[str] = None, 
                 cf_client_secret: Optional[str] = None):
        """
        Initialize the OpenWebUI API client.
        
        Args:
            base_url: Base URL of the OpenWebUI instance
            api_key: OpenWebUI API key
            jwt_token: OpenWebUI JWT token
            cf_client_id: Cloudflare Access Client ID (optional)
            cf_client_secret: Cloudflare Access Client Secret (optional)
        """
        # Ensure base_url is properly formatted
        if not base_url:
            raise ValueError("Base URL cannot be empty")
            
        # Make sure base_url has a scheme
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
            
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.jwt_token = jwt_token
        self.cf_client_id = cf_client_id
        self.cf_client_secret = cf_client_secret
        self.cf_access_client_id = cf_client_id
        self.cf_access_client_secret = cf_client_secret
        
        # Extract domain from base_url for Cloudflare Access
        self.domain = self._extract_domain(base_url)
        
        # Create a session to reuse connections and cookies
        self.session = requests.Session()
        
        # Set up the session with the appropriate headers
        self._setup_session()
        
        # Flag to track if we've authenticated with Cloudflare Access
        self.cf_authenticated = False
        
    def _extract_domain(self, url: str) -> str:
        """
        Extract the domain from a URL.
        
        Args:
            url: URL to extract domain from
            
        Returns:
            Domain name
        """
        # Remove scheme
        domain = url.split('://')[-1]
        # Remove path and query
        domain = domain.split('/', 1)[0]
        # Remove port
        domain = domain.split(':', 1)[0]
        
        return domain
        
    def _setup_session(self):
        """Set up the session with the appropriate headers."""
        # Add Cloudflare Access headers if provided
        if self.cf_client_id and self.cf_client_secret:
            self.session.headers.update({
                'CF-Access-Client-Id': self.cf_client_id,
                'CF-Access-Client-Secret': self.cf_client_secret
            })
        
        # Add OpenWebUI authorization header
        self.session.headers.update({
            'Authorization': f'Bearer {self.jwt_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
    def _get_headers(self, for_file_upload=False) -> Dict[str, str]:
        """
        Get the headers for API requests.
        
        Args:
            for_file_upload: Whether the headers are for a file upload
            
        Returns:
            Dict containing the headers
        """
        headers = {}
        
        # For file uploads, don't include Content-Type
        if not for_file_upload:
            headers['Content-Type'] = 'application/json'
            
        return headers
    
    def _authenticate_cloudflare_access(self) -> bool:
        """
        Authenticate with Cloudflare Access directly.
        
        Returns:
            True if authentication was successful, False otherwise
        """
        if not self.cf_client_id or not self.cf_client_secret:
            logger.warning("Cloudflare Access credentials not provided")
            return False
            
        # Try to authenticate directly with Cloudflare Access using the token endpoint
        cf_token_url = f"https://{self.domain}/cdn-cgi/access/token"
        
        try:
            # Make a request to the Cloudflare Access token endpoint
            headers = {
                'CF-Access-Client-Id': self.cf_client_id,
                'CF-Access-Client-Secret': self.cf_client_secret,
                'Content-Type': 'application/json'
            }
            
            # First, try the token endpoint
            token_response = self.session.get(cf_token_url, headers=headers)
            
            if token_response.status_code == 200:
                try:
                    token_data = token_response.json()
                    if 'token' in token_data:
                        # Store the token in the session
                        self.session.headers.update({
                            'CF-Access-Token': token_data['token']
                        })
                        logger.info("Successfully obtained Cloudflare Access token")
                    else:
                        logger.warning("Token endpoint response did not contain a token")
                except ValueError:
                    logger.warning("Token endpoint response was not valid JSON")
            
            # Also try the certs endpoint as a backup
            cf_certs_url = f"https://{self.domain}/cdn-cgi/access/certs"
            certs_response = self.session.get(cf_certs_url, headers=headers)
            
            # Check if we got a successful response from either endpoint
            if token_response.status_code == 200 or certs_response.status_code == 200:
                logger.info("Successfully authenticated with Cloudflare Access")
                
                # Update session cookies with the ones from the responses
                self.session.cookies.update(token_response.cookies)
                self.session.cookies.update(certs_response.cookies)
                
                # Update session headers with Cloudflare Access headers
                self.session.headers.update({
                    'CF-Access-Client-Id': self.cf_client_id,
                    'CF-Access-Client-Secret': self.cf_client_secret
                })
                
                return True
            else:
                logger.warning(f"Failed to authenticate with Cloudflare Access: token={token_response.status_code}, certs={certs_response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error authenticating with Cloudflare Access: {e}")
            return False
    
    def _handle_cloudflare_redirect(self, response):
        """
        Handle Cloudflare Access redirect.
        
        Args:
            response: The response from the API
            
        Returns:
            True if the redirect was handled, False otherwise
        """
        # Check if we're being redirected to Cloudflare Access
        if response.status_code == 302 and 'cloudflareaccess.com' in response.headers.get('Location', ''):
            logger.info("Detected Cloudflare Access redirect, attempting to authenticate...")
            
            # Try to authenticate directly
            if self._authenticate_cloudflare_access():
                return True
                
        return False
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make a request to the OpenWebUI API.
        
        Args:
            method: HTTP method to use
            endpoint: API endpoint to call
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response from the API
        """
        url = f"{self.base_url}{endpoint}"
        
        # Add headers to the request if not already present
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
            
        # Add authorization header if not already present
        if 'Authorization' not in kwargs['headers']:
            kwargs['headers']['Authorization'] = f"Bearer {self.jwt_token}"
            
        # Add Cloudflare Access headers if provided
        if self.cf_client_id and self.cf_client_secret:
            kwargs['headers']['CF-Access-Client-Id'] = self.cf_client_id
            kwargs['headers']['CF-Access-Client-Secret'] = self.cf_client_secret
        
        # Make the request
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Handle Cloudflare Access redirect
            if self._handle_cloudflare_redirect(response):
                # Retry the request
                response = self.session.request(method, url, **kwargs)
            
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to {url}: {e}")
            raise
    
    def get_knowledge_collections(self) -> List[Dict]:
        """
        Get all knowledge collections from OpenWebUI.
        
        Returns:
            List of knowledge collections
        """
        endpoint = "/api/knowledge"
        
        try:
            response = self._make_request("GET", endpoint)
            response.raise_for_status()
            
            try:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'data' in data:
                    return data['data']
                else:
                    logger.warning(f"Unexpected response format: {data}")
                    return []
            except ValueError:
                logger.error("Invalid JSON response")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting knowledge collections: {e}")
            return []
    
    def get_knowledge_collection(self, collection_id: str) -> Dict:
        """
        Get a specific knowledge collection from OpenWebUI.
        
        Args:
            collection_id: ID of the collection to get
            
        Returns:
            Knowledge collection data
        """
        endpoint = f"/api/knowledge/{collection_id}"
        
        try:
            response = self._make_request("GET", endpoint)
            response.raise_for_status()
            
            try:
                return response.json()
            except ValueError:
                logger.error("Invalid JSON response")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting knowledge collection {collection_id}: {e}")
            return {}
    
    def create_knowledge_collection(self, name: str, description: str = "") -> Dict:
        """
        Create a new knowledge collection in OpenWebUI.
        
        Args:
            name: Name of the collection
            description: Description of the collection
            
        Returns:
            Created knowledge collection data
        """
        endpoint = "/api/knowledge"
        
        data = {
            "name": name,
            "description": description
        }
        
        try:
            response = self._make_request("POST", endpoint, json=data)
            response.raise_for_status()
            
            try:
                return response.json()
            except ValueError:
                logger.error("Invalid JSON response")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating knowledge collection {name}: {e}")
            return {}
    
    def delete_knowledge_collection(self, collection_id: str) -> bool:
        """
        Delete a knowledge collection from OpenWebUI.
        
        Args:
            collection_id: ID of the collection to delete
            
        Returns:
            True if the collection was deleted, False otherwise
        """
        endpoint = f"/api/knowledge/{collection_id}"
        
        try:
            response = self._make_request("DELETE", endpoint)
            response.raise_for_status()
            
            return True
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error deleting knowledge collection {collection_id}: {e}")
            return False
    
    def get_files(self) -> List[Dict]:
        """
        Get all files from OpenWebUI.
        
        Returns:
            List of files
        """
        endpoint = "/api/files"
        
        try:
            response = self._make_request("GET", endpoint)
            response.raise_for_status()
            
            try:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'data' in data:
                    return data['data']
                else:
                    logger.warning(f"Unexpected response format: {data}")
                    return []
            except ValueError:
                logger.error("Invalid JSON response")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting files: {e}")
            return []
    
    def upload_file(self, file_path: str) -> Dict:
        """
        Upload a file to OpenWebUI.
        
        Args:
            file_path: Path to the file to upload
            
        Returns:
            Uploaded file data
        """
        endpoint = "/api/files/upload"
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                
                # Make the request without Content-Type header
                headers = self._get_headers(for_file_upload=True)
                
                response = self._make_request("POST", endpoint, files=files, headers=headers)
                response.raise_for_status()
                
                try:
                    return response.json()
                except ValueError:
                    logger.error("Invalid JSON response")
                    return {}
                    
        except (requests.exceptions.RequestException, IOError) as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            return {}
    
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from OpenWebUI.
        
        Args:
            file_id: ID of the file to delete
            
        Returns:
            True if the file was deleted, False otherwise
        """
        endpoint = f"/api/files/{file_id}"
        
        try:
            response = self._make_request("DELETE", endpoint)
            response.raise_for_status()
            
            return True
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    def add_file_to_knowledge(self, collection_id: str, file_id_or_path: Union[str, Dict]) -> bool:
        """
        Add a file to a knowledge collection.
        
        Args:
            collection_id: ID of the collection to add the file to
            file_id_or_path: ID of the file to add, or path to a file to upload
            
        Returns:
            True if the file was added, False otherwise
        """
        # Check if file_id_or_path is a path to a file
        if isinstance(file_id_or_path, str) and os.path.isfile(file_id_or_path):
            # Upload the file first
            file_data = self.upload_file(file_id_or_path)
            
            if not file_data or 'id' not in file_data:
                logger.error(f"Failed to upload file {file_id_or_path}")
                return False
                
            file_id = file_data['id']
        else:
            # Assume file_id_or_path is a file ID
            file_id = file_id_or_path
        
        endpoint = f"/api/knowledge/{collection_id}/files"
        
        data = {
            "file_id": file_id
        }
        
        try:
            response = self._make_request("POST", endpoint, json=data)
            response.raise_for_status()
            
            return True
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding file {file_id} to collection {collection_id}: {e}")
            return False
    
    def remove_file_from_knowledge(self, collection_id: str, file_id: str) -> bool:
        """
        Remove a file from a knowledge collection.
        
        Args:
            collection_id: ID of the collection to remove the file from
            file_id: ID of the file to remove
            
        Returns:
            True if the file was removed, False otherwise
        """
        endpoint = f"/api/knowledge/{collection_id}/files/{file_id}"
        
        try:
            response = self._make_request("DELETE", endpoint)
            response.raise_for_status()
            
            return True
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error removing file {file_id} from collection {collection_id}: {e}")
            return False
