#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to debug the password hash encoding issue
"""

from database.connection import SessionLocal
from database.models import Usuario
import traceback

def debug_users():
    db = SessionLocal()
    try:
        print("=== Debugging Users and Password Hashes ===")
        users = db.query(Usuario).all()
        
        for i, user in enumerate(users):
            print(f"\nUser {i+1}:")
            print(f"  ID: {user.id_usuario}")
            print(f"  Username: {user.nombre_usuario}")
            print(f"  Hash type: {type(user.contrasena_hash)}")
            print(f"  Hash length: {len(user.contrasena_hash) if user.contrasena_hash else 'None'}")
            
            if user.contrasena_hash:
                try:
                    # Try to display the first 50 characters safely
                    if isinstance(user.contrasena_hash, str):
                        print(f"  Hash preview (str): {repr(user.contrasena_hash[:50])}")
                    elif isinstance(user.contrasena_hash, bytes):
                        print(f"  Hash preview (bytes): {repr(user.contrasena_hash[:50])}")
                    elif hasattr(user.contrasena_hash, '__bytes__'):
                        print(f"  Hash preview (memoryview): {repr(bytes(user.contrasena_hash)[:50])}")
                    else:
                        print(f"  Hash preview: {repr(str(user.contrasena_hash)[:50])}")
                        
                except Exception as e:
                    print(f"  Error displaying hash: {e}")
                    print(f"  Raw hash object: {user.contrasena_hash}")
                    
    except Exception as e:
        print(f"Error querying users: {e}")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug_users()