#!/usr/bin/env python3
"""Test if the diagrams endpoint is deployed and working."""
import requests
import urllib.parse

# The API endpoint from the error message
api_url = "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev"

endpoints = [
    "/grades",
    "/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants",
]

print("Testing API endpoints...\n")
for endpoint in endpoints:
    url = api_url + endpoint
    print(f"GET {url}")
    try:
        resp = requests.get(url, timeout=10)
        print(f"  Status: {resp.status_code}")
        print(f"  Headers: {dict(resp.headers)}")
        if resp.text:
            print(f"  Body: {resp.text[:200]}")
        print()
    except Exception as e:
        print(f"  Error: {e}\n")
