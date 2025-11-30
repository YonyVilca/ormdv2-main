#!/bin/bash
# Commands to grant required IAM permissions

# 1. Grant Vertex AI User role
gcloud projects add-iam-policy-binding ormd-476617 \
    --member="serviceAccount:sa-vertex-extractor@ormd-476617.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# 2. Grant Storage Object Viewer role
gcloud projects add-iam-policy-binding ormd-476617 \
    --member="serviceAccount:sa-vertex-extractor@ormd-476617.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# 3. Verify permissions
gcloud projects get-iam-policy ormd-476617 \
    --flatten="bindings[].members" \
    --filter="bindings.members:sa-vertex-extractor@ormd-476617.iam.gserviceaccount.com"