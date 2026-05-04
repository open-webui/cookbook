#!/usr/bin/env python3
"""
File utility functions for the OpenWebUI knowledge sync script.
"""

import os
import hashlib
from pathlib import Path
from typing import Set

# List of supported file extensions
SUPPORTED_EXTENSIONS = {
    # Text files
    '.txt', '.md', '.markdown', '.rst', '.rtf',
    # Document files
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    # Code files
    '.py', '.js', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.php', '.rb', '.go',
    '.html', '.htm', '.css', '.xml', '.json', '.yaml', '.yml',
    # Data files
    '.csv', '.tsv',
}

def get_file_hash(file_path: Path) -> str:
    """
    Calculate the SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA-256 hash of the file
    """
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def is_supported_file(file_path: Path) -> bool:
    """
    Check if a file is supported for upload to OpenWebUI.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is supported, False otherwise
    """
    # Skip hidden files
    if file_path.name.startswith('.'):
        return False
    
    # Check file extension
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return False
    
    # Skip empty files
    if file_path.stat().st_size == 0:
        return False
    
    return True
