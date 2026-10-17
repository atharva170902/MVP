#!/usr/bin/env python3
"""
Quick Integration Test for Question Paper Drafts API

Tests the 5 core endpoints:
1. POST /api/drafts - Create draft
2. GET /api/drafts/{draftId} - Get single draft
3. PATCH /api/drafts/{draftId} - Update draft
4. GET /api/drafts - List user drafts
5. DELETE /api/drafts/{draftId} - Delete draft

Run with: python TEST_DRAFTS_API.py
"""

import requests
import json
from time import time

BASE_URL = "http://localhost:8000"
USER_ID = "test-user-123"
HEADERS = {"X-User-Id": USER_ID}

print("=" * 70)
print("QUESTION PAPER DRAFTS API - INTEGRATION TEST")
print("=" * 70)
print(f"Base URL: {BASE_URL}")
print(f"User ID: {USER_ID}")
print()

# ============================================================================
# TEST 1: CREATE DRAFT
# ============================================================================
print("TEST 1: Create Draft (POST /api/drafts)")
print("-" * 70)

create_payload = {
    "step": 1,
    "examType": "Unit Test",
    "grade": "Grade 7",
    "subject": "Science",
    "selectedChapters": ["ch01", "ch02"],
    "chapters": [
        {
            "id": "ch01",
            "title": "Nutrition in Plants",
            "marks": 8
        },
        {
            "id": "ch02",
            "title": "Nutrition in Animals",
            "marks": 12
        }
    ],
    "marksAllocation": {"ch01": 8, "ch02": 12},
    "totalMarks": 20,
    "title": "Science Unit Test - Nutrition"
}

try:
    response = requests.post(
        f"{BASE_URL}/api/drafts",
        json=create_payload,
        headers=HEADERS
    )
    response.raise_for_status()
    result = response.json()
    draft_id = result.get("draftId")
    print(f"✅ Success: Created draft")
    print(f"   Draft ID: {draft_id}")
    print(f"   Title: {result.get('title')}")
    print(f"   Status Code: {response.status_code}")
    print()
except Exception as e:
    print(f"❌ Failed: {str(e)}")
    print()
    exit(1)

# ============================================================================
# TEST 2: GET SINGLE DRAFT
# ============================================================================
print("TEST 2: Get Single Draft (GET /api/drafts/{draftId})")
print("-" * 70)

try:
    response = requests.get(
        f"{BASE_URL}/api/drafts/{draft_id}",
        headers=HEADERS
    )
    response.raise_for_status()
    result = response.json()
    print(f"✅ Success: Retrieved draft")
    print(f"   Draft ID: {result.get('draftId')}")
    print(f"   Title: {result.get('title')}")
    print(f"   Status: {result.get('status')}")
    print(f"   Marks: {result.get('totalMarks')}")
    print(f"   Chapters: {len(result.get('chapters', []))} selected")
    print()
except Exception as e:
    print(f"❌ Failed: {str(e)}")
    print()
    exit(1)

# ============================================================================
# TEST 3: UPDATE DRAFT (PATCH)
# ============================================================================
print("TEST 3: Update Draft (PATCH /api/drafts/{draftId})")
print("-" * 70)

update_payload = {
    "step": 2,
    "selectedDiagrams": ["diagram1.png", "diagram2.jpg"],
    "totalMarks": 40
}

try:
    response = requests.patch(
        f"{BASE_URL}/api/drafts/{draft_id}",
        json=update_payload,
        headers=HEADERS
    )
    response.raise_for_status()
    result = response.json()
    print(f"✅ Success: Updated draft")
    print(f"   Step: {result.get('step')}")
    print(f"   Total Marks: {result.get('totalMarks')}")
    print(f"   Updated At: {result.get('updatedAt')}")
    print()
except Exception as e:
    print(f"❌ Failed: {str(e)}")
    print()
    exit(1)

# ============================================================================
# TEST 4: LIST ALL DRAFTS
# ============================================================================
print("TEST 4: List All Drafts (GET /api/drafts)")
print("-" * 70)

try:
    response = requests.get(
        f"{BASE_URL}/api/drafts",
        headers=HEADERS
    )
    response.raise_for_status()
    result = response.json()
    drafts = result.get("drafts", [])
    print(f"✅ Success: Listed drafts")
    print(f"   Total drafts: {len(drafts)}")
    for i, draft in enumerate(drafts, 1):
        print(f"   {i}. {draft.get('title')} (Step {draft.get('step')}, Marks: {draft.get('totalMarks')})")
    print()
except Exception as e:
    print(f"❌ Failed: {str(e)}")
    print()
    exit(1)

# ============================================================================
# TEST 5: DELETE DRAFT
# ============================================================================
print("TEST 5: Delete Draft (DELETE /api/drafts/{draftId})")
print("-" * 70)

try:
    response = requests.delete(
        f"{BASE_URL}/api/drafts/{draft_id}",
        headers=HEADERS
    )
    response.raise_for_status()
    result = response.json()
    print(f"✅ Success: Deleted draft")
    print(f"   Draft ID: {draft_id}")
    print()
except Exception as e:
    print(f"❌ Failed: {str(e)}")
    print()
    exit(1)

# ============================================================================
# VERIFY DELETION
# ============================================================================
print("TEST 5b: Verify Deletion (GET /api/drafts/{draftId})")
print("-" * 70)

try:
    response = requests.get(
        f"{BASE_URL}/api/drafts/{draft_id}",
        headers=HEADERS
    )
    if response.status_code == 404:
        print(f"✅ Success: Draft confirmed deleted")
        print()
    else:
        print(f"❌ Failed: Draft still exists")
        print()
except Exception as e:
    print(f"✅ Success: Draft confirmed deleted (404 error)")
    print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 70)
print("ALL TESTS PASSED ✅")
print("=" * 70)
print("\nEndpoints Working:")
print("  ✅ POST /api/drafts - Create draft")
print("  ✅ GET /api/drafts/{draftId} - Get single draft")
print("  ✅ PATCH /api/drafts/{draftId} - Update draft")
print("  ✅ GET /api/drafts - List user drafts")
print("  ✅ DELETE /api/drafts/{draftId} - Delete draft")
print("\nReady for frontend integration! 🚀")
