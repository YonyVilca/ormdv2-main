#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Google Cloud authentication and Vertex AI access
"""

import os
import vertexai
from google.auth import default
from google.oauth2 import service_account
import json

def test_google_cloud_auth():
    """Test Google Cloud authentication setup"""
    
    # Set up the service account key path
    key_path = "ormd-476617-de3364d6b9cb.json"
    project_id = "ormd-476617"
    location = "us-central1"
    
    print("=== Testing Google Cloud Authentication ===")
    
    # 1. Test service account key loading
    try:
        with open(key_path, 'r') as f:
            key_data = json.load(f)
        print(f"1. Service account key loaded successfully")
        print(f"   Project ID: {key_data.get('project_id')}")
        print(f"   Client email: {key_data.get('client_email')}")
    except Exception as e:
        print(f"1. Failed to load service account key: {e}")
        return False
    
    # 2. Set environment variable and test credentials
    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        credentials, detected_project = default()
        print(f"2. Default credentials loaded successfully")
        print(f"   Detected project: {detected_project}")
        print(f"   Credentials type: {type(credentials).__name__}")
    except Exception as e:
        print(f"2. Failed to load default credentials: {e}")
        return False
    
    # 3. Test explicit service account credentials
    try:
        credentials = service_account.Credentials.from_service_account_file(key_path)
        print(f"3. Service account credentials loaded successfully")
        print(f"   Service account email: {credentials.service_account_email}")
    except Exception as e:
        print(f"3. Failed to load service account credentials: {e}")
        return False
    
    # 4. Test Vertex AI initialization
    try:
        vertexai.init(project=project_id, location=location)
        print(f"4. Vertex AI initialized successfully")
        print(f"   Project: {project_id}")
        print(f"   Location: {location}")
    except Exception as e:
        print(f"4. Failed to initialize Vertex AI: {e}")
        return False
    
    # 5. Test model access (without actual generation)
    try:
        from vertexai.generative_models import GenerativeModel
        model = GenerativeModel("gemini-2.0-flash-001")
        print(f"5. Generative model instance created successfully")
        print(f"   Model name: gemini-2.0-flash-001")
    except Exception as e:
        print(f"5. Failed to create model instance: {e}")
        return False
    
    print("\nAll authentication tests passed!")
    return True

def check_permissions():
    """Check if the service account has necessary permissions"""
    print("\n=== Checking Service Account Permissions ===")
    print("Required IAM roles for Vertex AI:")
    print("- Vertex AI User (roles/aiplatform.user)")
    print("- Storage Object Viewer (for model access)")
    print("\nTo check permissions, run in Google Cloud Console:")
    print("gcloud projects get-iam-policy ormd-476617 --flatten='bindings[].members' --filter='bindings.members:sa-vertex-extractor@ormd-476617.iam.gserviceaccount.com'")

if __name__ == "__main__":
    success = test_google_cloud_auth()
    check_permissions()
    
    if not success:
        print("\nAuthentication test failed. Check the errors above.")
    else:
        print("\nAuthentication setup appears correct.")
        print("If you're still getting 401 errors, the issue is likely with IAM permissions.")