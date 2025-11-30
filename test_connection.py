#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple database connection test
"""

import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def test_direct_connection():
    try:
        database_url = os.getenv("DATABASE_URL")
        print(f"Database URL: {database_url}")
        
        # Parse the URL manually
        if database_url.startswith("postgresql://"):
            url_parts = database_url[13:]  # Remove postgresql://
            auth_and_host = url_parts.split("/")
            db_name = auth_and_host[1] if len(auth_and_host) > 1 else "postgres"
            user_pass_host = auth_and_host[0]
            
            if "@" in user_pass_host:
                user_pass, host_port = user_pass_host.split("@")
                if ":" in user_pass:
                    user, password = user_pass.split(":", 1)
                else:
                    user = user_pass
                    password = ""
            else:
                host_port = user_pass_host
                user = "postgres"
                password = ""
                
            if ":" in host_port:
                host, port = host_port.split(":")
                port = int(port)
            else:
                host = host_port
                port = 5432
                
            print(f"Parsed connection details:")
            print(f"  Host: {host}")
            print(f"  Port: {port}")
            print(f"  Database: {db_name}")
            print(f"  User: {user}")
            print(f"  Password: {'*' * len(password) if password else '(empty)'}")
            
            # Try to connect with explicit encoding
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=db_name,
                user=user,
                password=password,
                client_encoding='UTF8'
            )
            
            print("✅ Direct psycopg2 connection successful!")
            
            # Test a simple query
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"PostgreSQL version: {version[0]}")
            
            # Check database encoding
            cursor.execute("SHOW server_encoding;")
            encoding = cursor.fetchone()
            print(f"Server encoding: {encoding[0]}")
            
            cursor.execute("SHOW client_encoding;")
            client_encoding = cursor.fetchone()
            print(f"Client encoding: {client_encoding[0]}")
            
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_connection()