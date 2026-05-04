#!/usr/bin/env python3
"""
Test script for uploading files to OpenWebUI.
"""

import os
import sys
import argparse
import json
import logging

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from code.src.owui_api import OpenWebUIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Test file upload to OpenWebUI')
    parser.add_argument('--file', type=str, required=True,
                        help='Path to file to upload')
    parser.add_argument('--config', type=str, default='config.json',
                        help='Path to config file')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Load config
    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load config file: {e}")
        sys.exit(1)
    
    # Create client
    client = OpenWebUIClient(
        base_url=config['base_url'],
        api_key=config['api_key'],
        jwt_token=config['jwt_token'],
        cf_client_id=config.get('cf_client_id'),
        cf_client_secret=config.get('cf_client_secret')
    )
    
    # Upload file
    file_path = args.file
    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        sys.exit(1)
    
    logger.info(f"Uploading file: {file_path}")
    result = client.upload_file(file_path)
    
    if result and 'id' in result:
        logger.info(f"File uploaded successfully with ID: {result['id']}")
        logger.info(f"File details: {json.dumps(result, indent=2)}")
    else:
        logger.error("Failed to upload file")
        sys.exit(1)

if __name__ == '__main__':
    main()
