# S3 Diagrams Backend Requirements - For Backend Team

## Problem Statement

Frontend needs to display diagram images from S3 for each chapter. Currently:
- Frontend tries to fetch S3 XML listing directly (fails with 404)
- S3 doesn't support directory listing via GET requests
- Frontend can't use AWS SDK directly (no credentials in browser)
- CORS blocks direct S3 bucket access

## Why Backend is Required

### The Technical Reason:

**Frontend Limitation:**
```
GET https://s3.amazonaws.com/bucket/Grade/Grade%207/Subjects/Science/Diagrams/Ch01_Nutrition_in_Plants/
→ Returns 404 (S3 doesn't support directory listing this way)
```

**Backend Solution:**
```
Backend has AWS credentials → Can use AWS SDK → ListObjectsV2 API → Works!
Backend returns presigned URLs → Frontend displays images → No CORS issues
```

---

## What Backend Needs to Build

### **Endpoint: GET /diagrams**

#### **Purpose:**
List all diagram images from a chapter folder in S3 and return them with presigned URLs

#### **Request:**
```
GET /diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants

Query Parameters:
- grade (required): URL-encoded grade name, e.g., "Grade 7"
- subject (required): URL-encoded subject name, e.g., "Science"
- folder (required): URL-encoded chapter folder name, e.g., "Ch01_Nutrition_in_Plants"
```

#### **Backend Logic (Step by Step):**

1. **Receive parameters from frontend**
   - `grade="Grade 7"`, `subject="Science"`, `folder="Ch01_Nutrition_in_Plants"`

2. **Build S3 path**
   ```
   s3://assessment-drafting-engine/Grade/Grade 7/Subjects/Science/Diagrams/Ch01_Nutrition_in_Plants/
   ```

3. **Use AWS SDK to list objects** (NOT XML listing)
   ```python
   # Use boto3 (Python) or AWS SDK for your language
   s3_client = boto3.client('s3')
   response = s3_client.list_objects_v2(
       Bucket='assessment-drafting-engine',
       Prefix='Grade/Grade 7/Subjects/Science/Diagrams/Ch01_Nutrition_in_Plants/'
   )
   ```

4. **Filter for image files only**
   - Include: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`
   - Exclude: folders, `.json`, `.txt`, other files

5. **Generate presigned URLs for each image**
   ```python
   # Each image gets a presigned URL valid for 1 hour
   presigned_url = s3_client.generate_presigned_url(
       'get_object',
       Params={'Bucket': 'assessment-drafting-engine', 'Key': 'Grade/Grade 7/Subjects/Science/Diagrams/Ch01_Nutrition_in_Plants/image.png'},
       ExpiresIn=3600  # 1 hour
   )
   ```

6. **Return JSON response**
   ```json
   {
     "diagrams": [
       {
         "key": "ch01_p001_img00.png",
         "name": "ch01 p001 img00",
         "url": "https://s3.amazonaws.com/assessment-drafting-engine/...?presigned-params"
       },
       {
         "key": "ch01_p002_img00.png",
         "name": "ch01 p002 img00",
         "url": "https://s3.amazonaws.com/assessment-drafting-engine/...?presigned-params"
       }
     ]
   }
   ```

---

## Response Format Details

### **Success Response (200 OK)**
```json
{
  "diagrams": [
    {
      "key": "filename.png",
      "name": "Display Name",
      "url": "https://s3.amazonaws.com/...?X-Amz-Signature=..."
    },
    {
      "key": "filename2.jpg",
      "name": "Display Name 2",
      "url": "https://s3.amazonaws.com/...?X-Amz-Signature=..."
    }
  ]
}
```

### **Empty Result (200 OK)**
If no diagrams in folder:
```json
{
  "diagrams": []
}
```

### **Error Response (400/500)**
- Missing query params → 400 Bad Request
- S3 access denied → 500 Internal Server Error
- Invalid grade/subject → 200 with empty diagrams array

---

## Why This Architecture

### **1. Frontend Can't Do This Directly**
❌ **Why not frontend?**
- No AWS credentials in browser (security risk)
- S3 XML listing returns 404
- CORS blocks direct S3 access
- Image URLs would be unsigned → expire immediately

✅ **Why backend?**
- Backend has AWS credentials securely
- AWS SDK ListObjectsV2 works reliably
- Presigned URLs valid for 1 hour
- Backend controls CORS headers

### **2. Presigned URLs**
- **What they are:** Temporary URLs that grant access to S3 objects
- **Why needed:** Secure way to let frontend display images
- **Duration:** 1 hour (long enough for user to see them)
- **Advantage:** No need for public bucket access

### **3. Security Benefits**
- Credentials never exposed to frontend
- S3 bucket stays private (no public access needed)
- URLs expire automatically
- Backend controls access permissions

---

## Implementation Reference

### Backend Stack Already Has This
```
Backend/Development/src/functions/diagrams_listing/app.py
```
This Python Lambda function is **already created** with:
- S3 ListObjectsV2 integration
- Presigned URL generation
- Image filtering logic
- CORS headers
- Error handling

### What's Left to Do
1. **Deploy** the Lambda function using SAM CLI:
   ```bash
   cd Backend/Development
   sam build
   sam deploy --guided
   ```

2. **Verify deployment:**
   ```bash
   curl "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants"
   ```

3. **Should return 200 with diagrams array**

---

## Frontend Expectations

### **What Frontend Will Do**
1. User selects chapters: "Grade 7 → Science → Ch01, Ch02"
2. Frontend calls backend for each selected chapter:
   ```
   GET /diagrams?grade=Grade 7&subject=Science&folder=Ch01_Nutrition_in_Plants
   GET /diagrams?grade=Grade 7&subject=Science&folder=Ch02_Nutrition_in_Animals
   ```
3. Backend returns diagrams list with presigned URLs
4. Frontend displays images in left panel with previews
5. User can select/deselect diagrams to include in paper

### **Frontend Code Ready**
```javascript
// lib/api.js - getDiagrams() function
export async function getDiagrams(grade, subject, folder) {
  const s3Path = `Grade/${grade}/Subjects/${subject}/Diagrams/${folder}/`;
  const s3Url = `https://assessment-drafting-engine.s3.ap-south-1.amazonaws.com/${s3Path}`;
  
  const response = await fetch(s3Url);
  // Expects JSON: { diagrams: [ { key, name, url }, ... ] }
}
```

---

## Testing Checklist for Backend

✅ **Before deploying, verify:**

1. **Endpoint responds to requests**
   ```bash
   curl "https://your-api/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants"
   ```

2. **Returns 200 status code** (not 404, 403, 500)

3. **Response format is correct JSON**
   ```json
   {
     "diagrams": [ ... ]
   }
   ```

4. **Presigned URLs are valid**
   - Can open them in browser
   - Images display correctly
   - URLs contain `?X-Amz-Signature=`

5. **Handles empty folders gracefully**
   - Returns `{ "diagrams": [] }` not error

6. **CORS headers present**
   - Response includes `Access-Control-Allow-Origin: *`
   - Allows frontend to fetch from `http://localhost:3000`

---

## Why Frontend Alone Can't Work

### **Attempted Approaches & Why They Failed**

#### ❌ **Approach 1: Direct S3 XML Listing**
```javascript
const response = await fetch('https://s3.amazonaws.com/bucket/folder/');
// Error: 404 Not Found
```
**Why:** S3 doesn't support directory listing via GET requests

#### ❌ **Approach 2: AWS SDK in Browser**
```javascript
import AWS from 'aws-sdk';
// Error: No credentials in browser (security risk)
```
**Why:** Credentials can't be in frontend code (exposed to users)

#### ❌ **Approach 3: Hardcoded Image URLs**
```javascript
const images = [
  'https://s3.amazonaws.com/bucket/ch01_p001.png',
  'https://s3.amazonaws.com/bucket/ch01_p002.png'
];
// Problem: Maintenance nightmare, doesn't scale
```
**Why:** New images require code changes

#### ✅ **Solution: Backend Endpoint**
```javascript
const response = await fetch('/diagrams?grade=Grade%207&subject=Science&folder=Ch01...');
const { diagrams } = await response.json();
// Works: Dynamic, secure, scalable
```
**Why:** Backend has credentials, AWS SDK works, presigned URLs handle security

---

## Summary for Backend Team

| Aspect | Details |
|--------|---------|
| **Endpoint** | `GET /diagrams?grade=...&subject=...&folder=...` |
| **S3 Operation** | `ListObjectsV2` to list image files |
| **URL Generation** | Generate presigned URLs (1 hour expiry) |
| **Response Format** | JSON: `{ diagrams: [ { key, name, url }, ... ] }` |
| **CORS Required** | Yes, include `Access-Control-Allow-Origin: *` |
| **Existing Code** | Already in `Backend/Development/src/functions/diagrams_listing/` |
| **Deploy Command** | `sam build && sam deploy` |
| **Test URL** | `https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/diagrams?...` |

---

## Questions for Backend Team?

1. **Is the Lambda function deployed?** 
   - Check AWS Lambda console or run: `aws lambda list-functions`

2. **Does it have S3 permissions?**
   - Check IAM role allows `s3:ListBucket` and `s3:GetObject`

3. **Is API Gateway configured?**
   - Check route `/diagrams` exists in API Gateway

4. **Are CORS headers returned?**
   - Test with: `curl -v https://your-api/diagrams?...`

---

## Next Steps

1. ✅ Frontend is ready (code complete)
2. ⏳ **Backend deploys `/diagrams` endpoint**
3. ✅ Frontend tests integration
4. ✅ Diagrams load and display in UI
5. ✅ Users can select diagrams to include in papers

**Frontend is blocked waiting for backend deployment.**
