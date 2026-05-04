#!/usr/bin/env python3
"""
OpenWebUI Knowledge Sync Script

This script syncs files from a local directory to OpenWebUI knowledge collections.
It creates knowledge collections based on the directory structure and adds files to them.
"""

import os
import sys
import argparse
import logging
import json
import re
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from code.src.owui_api import OpenWebUIClient
from code.src.utils.file_utils import get_file_hash, is_supported_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def prettify_name(name: str) -> str:
    """
    Convert a folder name to a prettified collection name.
    
    Args:
        name: Folder name (e.g., 'career-data')
        
    Returns:
        Prettified name (e.g., 'Career Data')
    """
    # Replace hyphens and underscores with spaces
    name = name.replace('-', ' ').replace('_', ' ')
    
    # Capitalize each word
    return ' '.join(word.capitalize() for word in name.split())

def get_local_files(directory: Path) -> Dict[str, Dict]:
    """
    Get all files in the directory and its subdirectories.
    
    Args:
        directory: Path to the directory
        
    Returns:
        Dictionary mapping relative file paths to file info (hash, etc.)
    """
    files = {}
    
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = Path(root) / filename
            rel_path = file_path.relative_to(directory)
            
            # Skip unsupported files
            if not is_supported_file(file_path):
                logger.debug(f"Skipping unsupported file: {rel_path}")
                continue
            
            files[str(rel_path)] = {
                'path': str(file_path),
                'hash': get_file_hash(file_path)
            }
    
    return files

def get_remote_files(client: OpenWebUIClient) -> Dict[str, Dict]:
    """
    Get all files from the remote server.
    
    Args:
        client: OpenWebUI API client
        
    Returns:
        Dictionary of files by ID
    """
    try:
        files = client.get_files()
        logger.info(f"Found {len(files)} remote files")
        
        # Create a dictionary of files by ID
        file_dict = {}
        for file in files:
            # Check if the file has a name field, if not use filename or id
            file_id = file.get('id')
            if file_id:
                file_dict[file_id] = file
        
        logger.info(f"Processed {len(file_dict)} remote files")
        return file_dict
    except Exception as e:
        logger.error(f"Failed to get remote files: {e}")
        return {}

def get_remote_collections(client: OpenWebUIClient) -> Dict[str, Dict]:
    """
    Get all knowledge collections from OpenWebUI.
    
    Args:
        client: OpenWebUI API client
        
    Returns:
        Dictionary mapping collection names to collection info
    """
    collections = {}
    
    try:
        response = client.get_knowledge_collections()
        logger.info(f"Found {len(response)} remote collections")
        for collection in response:
            collections[collection['name']] = collection
    except Exception as e:
        logger.error(f"Failed to get remote collections: {e}")
    
    return collections

def sync_file(client: OpenWebUIClient, collection_id: str, file_path: str, remote_files: Dict[str, Dict]) -> None:
    """
    Sync a file to OpenWebUI.
    
    Args:
        client: OpenWebUI API client
        collection_id: ID of the collection to add the file to
        file_path: Path to the file to upload
        remote_files: Dictionary of remote files by ID
    """
    file_name = os.path.basename(file_path)
    logger.info(f"Syncing file: {file_name}")
    
    # Check if the file already exists on the server
    existing_file_id = None
    for file_id, file_info in remote_files.items():
        if (file_info.get('filename') == file_name or 
            file_info.get('file_name') == file_name):
            existing_file_id = file_id
            logger.info(f"File {file_name} already exists with ID {existing_file_id}")
            break
    
    try:
        if existing_file_id:
            # File already exists, add it to the collection
            logger.info(f"Adding existing file {file_name} to collection {collection_id}")
            client.add_file_to_knowledge(collection_id, existing_file_id)
        else:
            # File doesn't exist yet, use the enhanced add_file_to_knowledge method
            # which will handle the upload and adding to the collection in one step
            logger.info(f"Uploading and adding new file {file_name} to collection {collection_id}")
            client.add_file_to_knowledge(collection_id, file_path)
    except Exception as e:
        logger.error(f"Failed to sync file {file_name}: {e}")

def sync_collection(client: OpenWebUIClient, collection_name: str, 
                   local_files: Dict[str, Dict], 
                   remote_files: Dict[str, Dict], 
                   remote_collections: Dict[str, Dict],
                   base_dir: Path, collection_dir: Path) -> None:
    """
    Sync a single collection with its local directory.
    
    Args:
        client: OpenWebUI API client
        collection_name: Name of the collection
        local_files: Dictionary of local files
        remote_files: Dictionary of remote files
        remote_collections: Dictionary of remote collections
        base_dir: Base directory path
        collection_dir: Collection directory path
    """
    # Create collection if it doesn't exist
    if collection_name not in remote_collections:
        logger.info(f"Creating collection: {collection_name}")
        description = f"Auto-created by sync script from {collection_dir.name}"
        collection = client.create_knowledge_collection(collection_name, description)
        remote_collections[collection_name] = collection
    
    collection_id = remote_collections[collection_name]['id']
    collection_info = client.get_knowledge_collection(collection_id)
    
    # Get files currently in the collection
    collection_file_ids = set()
    if 'files' in collection_info:
        collection_file_ids = {file['id'] for file in collection_info['files']}
    elif 'data' in collection_info and 'file_ids' in collection_info['data']:
        collection_file_ids = set(collection_info['data']['file_ids'])
    
    # Get local files for this collection
    collection_local_files = {}
    rel_collection_dir = collection_dir.relative_to(base_dir)
    prefix = str(rel_collection_dir) + os.sep
    
    for rel_path, file_info in local_files.items():
        if rel_path.startswith(prefix):
            # Store with path relative to the collection directory
            collection_local_files[rel_path] = file_info
    
    logger.info(f"Found {len(collection_local_files)} local files for collection {collection_name}")
    
    # Sync local files to the collection
    for rel_path, file_info in collection_local_files.items():
        sync_file(client, collection_id, file_info['path'], remote_files)
    
    # TODO: Remove files from the collection that no longer exist locally
    # This is left as an exercise for the reader as it requires mapping
    # between local files and remote files, which can be complex.

def sync_knowledge(client: OpenWebUIClient, base_dir: Path) -> None:
    """
    Sync the local directory structure with OpenWebUI knowledge collections.
    
    Args:
        client: OpenWebUI API client
        base_dir: Base directory path
    """
    # Get all local files
    logger.info(f"Scanning local directory: {base_dir}")
    local_files = get_local_files(base_dir)
    logger.info(f"Found {len(local_files)} local files")
    
    # Get all remote files
    logger.info("Getting remote files")
    remote_files = get_remote_files(client)
    
    # Get all remote collections
    logger.info("Getting remote collections")
    remote_collections = get_remote_collections(client)
    
    # Process each subdirectory as a collection
    for item in base_dir.iterdir():
        if item.is_dir():
            collection_name = prettify_name(item.name)
            logger.info(f"Processing collection: {collection_name}")
            
            sync_collection(
                client=client,
                collection_name=collection_name,
                local_files=local_files,
                remote_files=remote_files,
                remote_collections=remote_collections,
                base_dir=base_dir,
                collection_dir=item
            )

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Sync files to OpenWebUI knowledge collections')
    parser.add_argument('--base-dir', type=str, required=True,
                        help='Base directory containing knowledge collections')
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
    
    # Sync knowledge
    base_dir = Path(args.base_dir)
    if not base_dir.exists() or not base_dir.is_dir():
        logger.error(f"Base directory does not exist: {base_dir}")
        sys.exit(1)
    
    sync_knowledge(client, base_dir)

if __name__ == '__main__':
    main()
