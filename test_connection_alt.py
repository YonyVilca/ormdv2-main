#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test with multiple connection approaches
"""

import psycopg2
import os
import sys
from pathlib import Path

def test_simple_connection():
    """Test with hardcoded credentials to isolate the issue"""
    try:
        print("=== Testing with hardcoded credentials ===")
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="ormd",
            user="postgres",
            password="282090",
            client_encoding='UTF8'
        )
        
        print("✅ Hardcoded connection successful!")
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"PostgreSQL version: {version[0]}")
        
        cursor.execute("SHOW server_encoding;")
        encoding = cursor.fetchone()
        print(f"Server encoding: {encoding[0]}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Hardcoded connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_alternative_database():
    """Test connecting to a different database to see if the issue is database-specific"""
    try:
        print("\n=== Testing connection to postgres database ===")
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",  # Connect to default postgres database
            user="postgres",
            password="282090",
            client_encoding='UTF8'
        )
        
        print("✅ Connection to postgres database successful!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT datname FROM pg_database WHERE datname = 'ormd';")
        result = cursor.fetchone()
        if result:
            print(f"✅ Database 'ormd' exists")
        else:
            print("❌ Database 'ormd' does not exist")
            
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection to postgres database failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_simple_connection()
    success2 = test_alternative_database()
    
    if success1:
        print("\n✅ The issue is likely with environment variable loading or SQLAlchemy configuration")
    elif success2:
        print("\n⚠️  The issue seems specific to the 'ormd' database")
    else:
        print("\n❌ There's a fundamental PostgreSQL connection issue")