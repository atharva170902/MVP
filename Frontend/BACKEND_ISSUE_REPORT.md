# Backend Issue Report: `/diagrams` Endpoint Not Working

## Issue Summary
Frontend is trying to **fetch and preview diagram images from S3**, but the `/diagrams` endpoint is not responding.

The task is simple: **Get diagram image files from S3 and return their presigned URLs for preview.**

---

## Error Details

### Error Messages (from Browser Console):
```
Access to fetch at 'https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams?grade=Grade%207&subject=Science&folder=Ch07_Transportation_in_Animals_and_Plants' 
from origin 'http://localhost:3000' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.

Failed to load resource: net::ERR_FAILED
```

### HTTP Status
- Frontend log shows: **403 Forbidden** response from API

---

## Root Cause Analysis

### What's Happening:
1. ✅ Frontend selects chapters
2. ✅ Frontend calls `/diagrams` endpoint with chapter folder name
3. ❌ Backend should list image files from S3
4. ❌ Backend should return presigned URLs for preview
5. ❌ This is NOT working - endpoint missing/broken

### Why It's Failing:
- Backend endpoint is **not deployed** or **misconfigured**
- Endpoint should list S3 image files and generate presigned URLs
- Frontend receives 403/CORS error instead

---

## What the Backend Endpoint Should Do

### Task: `/diagrams` GET Endpoint

**Input (Query Parameters):**
```
?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants
```

**Process:**
1. Build S3 path: `s3://assessment-drafting-engine/Grade/Grade 7/Subjects/Science/Diagrams/Ch01_Nutrition_in_Plants/`
2. List all image files in that folder (`.png`, `.jpg`, `.jpeg`, etc.)
3. Generate presigned URLs for each image (valid 1 hour)
4. Return the list

**Output (JSON Response):**
```json
{
  "diagrams": [
    {
      "key": "diagram1.png",
      "name": "Diagram 1",
      "url": "https://s3.amazonaws.com/assessment-drafting-engine/...?presigned_url_params"
    },
    {
      "key": "diagram2.jpg",
      "name": "Diagram 2",
      "url": "https://s3.amazonaws.com/assessment-drafting-engine/...?presigned_url_params"
    }
  ]
}
```

---

## Frontend Details

### Frontend Call Location:
- **File:** `Frontend/lib/api.js`
- **Function:** `getDiagrams(grade, subject, folder)`
- **Line:** 98-104

### API Call Details:
```javascript
const url = `${API_URL}/diagrams?grade=${encodedGrade}&subject=${encodedSubject}&folder=${encodedFolder}`;
const response = await fetch(url);
```

### Configuration:
- **API Base URL:** `https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev`
- **Environment Variable:** `NEXT_PUBLIC_API_URL`
- **Set in:** `Frontend/.env.local`

### Example Request:
```
GET https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams?grade=Grade%207&subject=Science&folder=Ch07_Transportation_in_Animals_and_Plants
```

### Example Expected Response:
```json
{
  "diagrams": [
    {
      "key": "diagram1.png",
      "name": "Diagram 1",
      "url": "https://s3.amazonaws.com/..."
    },
    {
      "key": "diagram2.jpg",
      "name": "Diagram 2",
      "url": "https://s3.amazonaws.com/..."
    }
  ]
}
```

---

## Frontend Behavior

### Current Status:
- Frontend **gracefully handles** the error (no crash)
- If `/diagrams` endpoint fails, shows "No diagrams available"
- Error is logged as warning (not a fatal error)

### What Frontend Expects:
1. HTTP 200 response
2. Response headers:
   ```
   Access-Control-Allow-Origin: *
   Content-Type: application/json
   ```
3. JSON body with `diagrams` array

---

## Issues to Fix in Backend

### Only 1 Issue: Endpoint Not Working

The `/diagrams` endpoint needs to:

1. **Accept query params:** `grade`, `subject`, `folder` (URL-encoded)
2. **List S3 files** from: `Grade/{grade}/Subjects/{subject}/Diagrams/{folder}/`
3. **Filter images only** (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`)
4. **Generate presigned URLs** (1-hour expiry)
5. **Return JSON** with diagram list
6. **Include CORS headers** in response (for browser access)

---

## Testing Instructions for Backend

### Test 1: Check CORS Headers
```bash
curl -v "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants"
```

**Should return:**
- HTTP 200 (not 403)
- Header: `Access-Control-Allow-Origin: *`

### Test 2: Check OPTIONS Preflight
```bash
curl -X OPTIONS -v "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams"
```

**Should return:**
- HTTP 200
- Headers with CORS allow directives

### Test 3: Check Response Format
```bash
curl "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants" | jq
```

**Should return:**
```json
{
  "diagrams": [
    {
      "key": "filename.png",
      "name": "Display Name",
      "url": "https://..."
    }
  ]
}
```

---

## Frontend Test Steps

Once backend is fixed, the frontend will:

1. **Automatically load diagrams** when user:
   - Selects Grade 7 → Science → chapters
   - Clicks "Generate Paper" (Step 3)

2. **Display in Step 3 left panel:**
   - Grouped by chapter folder
   - With image previews
   - Checkboxes for selection

3. **Console should show:**
   ```
   Fetching diagrams from: https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams?grade=...
   [Array of diagram objects]  ← Success!
   ```

---

## Summary for Backend Team

| Item | Status |
|------|--------|
| Frontend calling endpoint | ✅ Yes |
| URL format | ✅ Correct |
| Parameters | ✅ Correct |
| Endpoint deployed | ❌ No (or misconfigured) |
| CORS headers | ❌ Missing |
| HTTP status | ❌ 403 (should be 200) |

**Action Required:**
1. Deploy `/diagrams` endpoint to AWS Lambda
2. Ensure CORS headers are returned in all responses
3. Verify HTTP 200 response (not 403)
4. Test with curl before notifying frontend team

---

## Files Involved (Frontend Side)

- `Frontend/lib/api.js` - API helper with `getDiagrams()` function
- `Frontend/pages/craft-a-paper.js` - Calls `getDiagrams()` in useEffect
- `Frontend/.env.local` - Contains API URL
- `Frontend/pages/craft-a-paper.js` (Line ~170-190) - Diagram fetching logic

---

## Notes for Backend Team

The **frontend is working correctly**. The issue is entirely on the backend:
1. `/diagrams` endpoint code exists but needs deployment
2. CORS headers need to be included in responses
3. The endpoint should return HTTP 200 (currently returning 403)

Once the backend endpoint is:
- ✅ Deployed
- ✅ Returning 200 status
- ✅ Including CORS headers
- ✅ Returning correct JSON format

The frontend will automatically start displaying diagrams without any changes needed.
