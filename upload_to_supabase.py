import requests
import json
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

SUPABASE_URL = "https://gvdkkvxkqadplvvlpmiw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd2ZGtrdnhrcWFkcGx2dmxwbWl3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTE0NDYzNCwiZXhwIjoyMDkwNzIwNjM0fQ.HQ-aw4S3wjV3dK8KWmpK0ErHBj0_KAQZhQkYIf4gHHM"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

# List existing buckets
r = requests.get(f"{SUPABASE_URL}/storage/v1/bucket", headers=headers)
print("Storage buckets:", r.status_code, r.text)

# Create a public bucket 'deploy' if not exists
requests.post(f"{SUPABASE_URL}/storage/v1/bucket", headers=headers, json={"id": "deploy", "name": "deploy", "public": True})

# Upload deploy_on_server.sh
deploy_script = Path("deploy_on_server.sh").read_bytes()
up_headers = {**headers, "Content-Type": "text/x-shellscript", "x-upsert": "true"}
r_up = requests.post(f"{SUPABASE_URL}/storage/v1/object/deploy/run.sh", headers=up_headers, data=deploy_script)
print("Upload status:", r_up.status_code, r_up.text)

# Public URL
public_url = f"{SUPABASE_URL}/storage/v1/object/public/deploy/run.sh"
print("Public URL:", public_url)

# Test fetch public URL
r_get = requests.get(public_url)
print(f"Fetch test: {r_get.status_code}, length: {len(r_get.text)} bytes")
