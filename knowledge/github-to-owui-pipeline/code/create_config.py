#!/usr/bin/env python3
"""
Create a config.json file from the template and environment variables.
"""

import os
import json
import argparse

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Create config.json from template')
    parser.add_argument('--template', type=str, default='config.template.json',
                        help='Path to template file')
    parser.add_argument('--output', type=str, default='config.json',
                        help='Path to output file')
    
    args = parser.parse_args()
    
    # Load template
    with open(args.template, 'r') as f:
        config = json.load(f)
    
    # Update with environment variables
    config['base_url'] = os.environ.get('OWUI_BASE_URL', config['base_url'])
    config['api_key'] = os.environ.get('OWUI_API_KEY', config['api_key'])
    config['jwt_token'] = os.environ.get('OWUI_JWT_TOKEN', config['jwt_token'])
    config['cf_client_id'] = os.environ.get('CF_ACCESS_CLIENT_ID', config['cf_client_id'])
    config['cf_client_secret'] = os.environ.get('CF_ACCESS_CLIENT_SECRET', config['cf_client_secret'])
    
    # Write output
    with open(args.output, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Config file created: {args.output}")

if __name__ == '__main__':
    main()
