#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug environment variable loading
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def debug_env_loading():
    BASE_DIR = Path(__file__).resolve().parent
    env_file = BASE_DIR / ".env"
    
    print(f"=== Environment Variable Debug ===")
    print(f"Base directory: {BASE_DIR}")
    print(f"Env file path: {env_file}")
    print(f"Env file exists: {env_file.exists()}")
    
    if env_file.exists():
        print(f"Env file size: {env_file.stat().st_size} bytes")
        
        # Read the file directly
        print("\n=== Raw .env file contents ===")
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(repr(content))
    
    # Check current environment before loading
    print(f"\n=== Environment BEFORE loading .env ===")
    print(f"DATABASE_URL: {repr(os.getenv('DATABASE_URL'))}")
    print(f"SECRET_KEY: {repr(os.getenv('SECRET_KEY'))}")
    
    # Load environment variables
    print(f"\n=== Loading .env file ===")
    result = load_dotenv(env_file)
    print(f"load_dotenv result: {result}")
    
    # Check environment after loading
    print(f"\n=== Environment AFTER loading .env ===")
    database_url = os.getenv('DATABASE_URL')
    secret_key = os.getenv('SECRET_KEY')
    print(f"DATABASE_URL: {repr(database_url)}")
    print(f"SECRET_KEY: {repr(secret_key)}")
    
    if database_url:
        print(f"\n=== DATABASE_URL Analysis ===")
        print(f"Length: {len(database_url)}")
        print(f"Contains non-ASCII chars: {any(ord(c) > 127 for c in database_url)}")
        
        # Check for problematic characters around position 85
        if len(database_url) > 85:
            print(f"Character at position 85: {repr(database_url[85])}")
            print(f"Bytes around position 85: {repr(database_url[80:90].encode('utf-8', errors='replace'))}")

if __name__ == "__main__":
    debug_env_loading()