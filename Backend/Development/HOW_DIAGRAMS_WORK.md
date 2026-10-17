# How Backend Returns Diagrams from S3

## Short Answer

**The backend returns PRESIGNED URLs, not image files.**

Frontend uses these URLs to download images directly from S3.

---

## Why Presigned URLs?

| Approach | Size | Speed | Scalability | Security |
|----------|------|-------|-------------|----------|
| **Presigned URLs (Used)** | ~1 KB response | ⚡⚡⚡ Fast | ✅ Excellent | ✅ Secure |
| Direct Image Files | 100 KB - 1 MB | ❌ Slow | ❌ Poor | ❌ Risky |
| Backend Proxy | 100 KB - 1 MB | ❌ Slow | ⚠️ Medium | ✅ Secure |

---

## How It Works

### 1. Frontend Request
```javascript
fetch('/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants')
```

### 2. Backend Processing
```python
@app.get("/diagrams")
async def get_diagrams(grade, subject, folder):
    # Connect to S3
    # Build path: Grade/{grade}/Subjects/{subject}/Diagrams/{folder}/
    # List all image files in folder
    # Generate presigned URLs for each image
    # Return JSON response
```

### 3. Backend Response
```json
{
  "diagrams": [
    {
      "key": "ch01_p001_img01.png",
      "name": "ch01 p001 img01",
      "url": "https://s3.amazonaws.com/assessment-drafting-engine/Grade/Grade%207/Subjects/Science/Diagrams/ch01__nutrition_in_plants/ch01_p001_img01.png?AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Signature=wJalrXUtnFEMI%2FK7MDENG%2FJ41EXAMPLE&Expires=1695123456"
    },
    {
      "key": "ch01_p002_img02.jpg",
      "name": "ch01 p002 img02",
      "url": "https://s3.amazonaws.com/assessment-drafting-engine/Grade/Grade%207/Subjects/Science/Diagrams/ch01__nutrition_in_plants/ch01_p002_img02.jpg?AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Signature=wJalrXUtnFEMI%2FK7MDENG%2FJ41EXAMPLE&Expires=1695123456"
    }
  ]
}
```

### 4. Frontend Display
```javascript
// React component
data.diagrams.forEach(diagram => {
  return <img src={diagram.url} alt={diagram.name} />
})
```

### 5. Browser Downloads
```
Browser fetches image directly from S3 using presigned URL
↓
Image displays in browser
```

---

## Presigned URL Details

### What Is It?
- Special S3 URL with built-in authentication
- Signed with your AWS access key
- Contains timestamp and permissions
- Temporary access token

### Example Format
```
https://s3.amazonaws.com/bucket/path/file.png?
  AWSAccessKeyId=YOUR_KEY&
  Signature=ENCODED_SIGNATURE&
  Expires=1695123456
```

### Expiry: 1 Hour
- URL is valid for 1 hour (3600 seconds)
- After 1 hour, URL becomes invalid
- Frontend must re-fetch to get new URL
- This provides security without exposing S3 credentials

### Why Presigned URLs Are Better
✅ **Secure** - No direct S3 bucket exposure
✅ **Fast** - Browser downloads directly from S3
✅ **Scalable** - Backend doesn't serve image data
✅ **Efficient** - Reduces backend load
✅ **Temporary** - URLs expire automatically

---

## Backend Code Logic

```python
# Step 1: Connect to S3
s3_client = boto3.client('s3')

# Step 2: List files in S3 folder
paginator = s3_client.get_paginator('list_objects_v2')
pages = paginator.paginate(
    Bucket='assessment-drafting-engine',
    Prefix='Grade/Grade 7/Subjects/Science/Diagrams/ch01__nutrition_in_plants/'
)

# Step 3: Process each file
diagrams = []
for page in pages:
    for obj in page['Contents']:
        key = obj['Key']
        
        # Only include image files
        if key.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            
            # Generate presigned URL (1 hour validity)
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': 'assessment-drafting-engine', 'Key': key},
                ExpiresIn=3600  # 1 hour
            )
            
            diagrams.append({
                'key': filename,
                'name': display_name,
                'url': presigned_url
            })

# Step 4: Return JSON
return {'diagrams': diagrams}
```

---

## Data Flow

```
Frontend
  ↓
  GET /diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants
  ↓
Backend (FastAPI)
  ↓
  Connect to S3
  List images in folder
  Generate presigned URLs (1 hour expiry)
  ↓
  Return JSON with URLs
  ↓
Frontend receives JSON
  ↓
  <img src={presigned_url} />
  ↓
Browser
  ↓
  Downloads image directly from S3
  ↓
Image displays
```

---

## Frontend Integration

### Using the URLs in React
```javascript
// Fetch diagrams
const response = await fetch(
  `${API_URL}/diagrams?grade=${grade}&subject=${subject}&folder=${folder}`
);
const data = await response.json();

// Display images
return (
  <div>
    {data.diagrams.map(diagram => (
      <img 
        key={diagram.key}
        src={diagram.url}  // Use presigned URL
        alt={diagram.name}
      />
    ))}
  </div>
);
```

### What's Passed to Frontend
```javascript
{
  diagrams: [
    {
      key: "ch01_p001_img01.png",      // Filename
      name: "ch01 p001 img01",          // Display name
      url: "https://s3.amazonaws..."   // Presigned URL (use this!)
    }
  ]
}
```

---

## Error Cases Handled

### 1. Folder Not Found
- Backend returns: `{"diagrams": []}`
- Frontend displays: Empty list

### 2. No Images in Folder
- Backend returns: `{"diagrams": []}`
- Frontend displays: Empty list

### 3. S3 Connection Error
- Backend returns: HTTP 500 error
- Frontend handles: Error message

### 4. Missing Parameters
- Backend returns: HTTP 400 error (missing grade, subject, or folder)
- Frontend should pass all three parameters

---

## S3 Folder Structure

```
s3://assessment-drafting-engine/
├── Grade/
│   ├── Grade 7/
│   │   ├── Subjects/
│   │   │   ├── Science/
│   │   │   │   ├── Diagrams/
│   │   │   │   │   ├── ch01__nutrition_in_plants/
│   │   │   │   │   │   ├── ch01_p001_img01.png
│   │   │   │   │   │   ├── ch01_p001_img02.jpg
│   │   │   │   │   │   └── ... (more images)
│   │   │   │   │   ├── ch02__nutrition_in_animals/
│   │   │   │   │   │   ├── ch02_p001_img01.png
│   │   │   │   │   │   └── ... (more images)
│   │   │   │   │   └── ... (more chapters)
```

---

## Testing the Endpoint

### Using cURL
```bash
curl "http://localhost:8000/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants"
```

### Using Browser
```
http://localhost:8000/docs
# Click on GET /diagrams
# Enter parameters
# Click "Execute"
```

### In Frontend .env
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Key Points

✅ **Backend does NOT send image files**
✅ **Backend returns JSON with S3 presigned URLs**
✅ **Frontend downloads images directly from S3**
✅ **URLs expire after 1 hour**
✅ **This is the industry standard approach**
✅ **Efficient, fast, and secure**

---

## Summary

| Component | Role |
|-----------|------|
| **Frontend** | Calls backend API, displays images using URLs |
| **Backend** | Lists S3 files, generates presigned URLs, returns JSON |
| **S3** | Stores images, serves images using presigned URLs |
| **Browser** | Downloads images directly from S3 using URLs |

All working together efficiently! 🚀
