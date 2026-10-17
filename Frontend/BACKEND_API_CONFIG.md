# Backend API Configuration for Frontend

## 🎯 API Endpoint

```
https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev
```

## 📡 Three Endpoints

### 1. List All Grades
```http
GET /grades
```

**Response:**
```json
{
  "grades": ["Grade 7"]
}
```

### 2. List Subjects for Grade
```http
GET /grades/{grade}/subjects
```

**Example:**
```
GET /grades/Grade%207/subjects
```

**Response:**
```json
{
  "grade": "Grade 7",
  "subjects": ["Science"]
}
```

### 3. List Chapters for Subject
```http
GET /grades/{grade}/subjects/{subject}/chapters
```

**Example:**
```
GET /grades/Grade%207/subjects/Science/chapters
```

**Response:**
```json
{
  "grade": "Grade 7",
  "subject": "Science",
  "chapters": [
    {
      "id": "ch01",
      "order": 1,
      "title": "Nutrition in Plants",
      "folder": "Ch01_Nutrition_in_Plants"
    },
    {
      "id": "ch02",
      "order": 2,
      "title": "Nutrition in Animals",
      "folder": "Ch02_Nutrition_in_Animals"
    },
    {
      "id": "ch03",
      "order": 3,
      "title": "Photosynthesis",
      "folder": "Ch03_Photosynthesis"
    },
    {
      "id": "ch04",
      "order": 4,
      "title": "Respiration",
      "folder": "Ch04_Respiration"
    },
    {
      "id": "ch05",
      "order": 5,
      "title": "Transportation",
      "folder": "Ch05_Transportation"
    },
    {
      "id": "ch06",
      "order": 6,
      "title": "Excretion",
      "folder": "Ch06_Excretion"
    },
    {
      "id": "ch07",
      "order": 7,
      "title": "Control and Coordination",
      "folder": "Ch07_Control_and_Coordination"
    },
    {
      "id": "ch08",
      "order": 8,
      "title": "Reproduction",
      "folder": "Ch08_Reproduction"
    },
    {
      "id": "ch09",
      "order": 9,
      "title": "Food Production",
      "folder": "Ch09_Food_Production"
    },
    {
      "id": "ch10",
      "order": 10,
      "title": "Heredity and Evolution",
      "folder": "Ch10_Heredity_and_Evolution"
    },
    {
      "id": "ch11",
      "order": 11,
      "title": "Light Reflection and Refraction",
      "folder": "Ch11_Light_Reflection_and_Refraction"
    },
    {
      "id": "ch12",
      "order": 12,
      "title": "Electricity and Its Effects",
      "folder": "Ch12_Electricity_and_Its_Effects"
    },
    {
      "id": "ch13",
      "order": 13,
      "title": "Wastewater Story",
      "folder": "Ch13_Wastewater_Story"
    }
  ]
}
```

## 🔑 Lambda Function

| Property | Value |
|----------|-------|
| **Name** | `question-paper-catalog-listing-dev` |
| **ARN** | `arn:aws:lambda:ap-south-1:622158567844:function:question-paper-catalog-listing-dev` |
| **Region** | ap-south-1 (Mumbai) |
| **Runtime** | Python 3.11 |

## 📝 Environment Setup

Add to `.env.local`:

```env
VITE_API_URL=https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev
```

Or for React:

```env
REACT_APP_API_URL=https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev
```

## 💻 Usage Example (JavaScript/Fetch)

```javascript
const API_URL = 'https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev';

// Get grades
async function getGrades() {
  const response = await fetch(`${API_URL}/grades`);
  return response.json();
}

// Get subjects
async function getSubjects(grade) {
  const encoded = encodeURIComponent(grade);
  const response = await fetch(`${API_URL}/grades/${encoded}/subjects`);
  return response.json();
}

// Get chapters
async function getChapters(grade, subject) {
  const encodedGrade = encodeURIComponent(grade);
  const encodedSubject = encodeURIComponent(subject);
  const response = await fetch(
    `${API_URL}/grades/${encodedGrade}/subjects/${encodedSubject}/chapters`
  );
  return response.json();
}
```

## ⚠️ Important Notes

### URL Encoding
- Grades/subjects with spaces must be URL-encoded
- Use JavaScript `encodeURIComponent()` to handle this
- Example: `"Grade 7"` becomes `"Grade%207"`

### Response Fields
- `id`: Chapter identifier (e.g., "ch01")
- `order`: Chapter order/number (e.g., 1)
- `title`: Chapter title
- `folder`: S3 folder name (NOT a downloadable file)

### CORS
- API has CORS enabled for all origins
- No authentication required

## 🧪 Testing

### With cURL

```bash
curl https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades

curl "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades/Grade%207/subjects"

curl "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades/Grade%207/subjects/Science/chapters"
```

### With Postman
1. URL: `https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades`
2. Method: `GET`
3. Send

## 📊 Current Data

**Available:**
- Grade: 7 only
- Subject: Science only
- Chapters: 13 chapters (Nutrition in Plants through Wastewater Story)

## 🔗 Resources

- **Full Integration Guide**: `../Backend/Development/FRONTEND_INTEGRATION.md`
- **AWS Lambda**: https://ap-south-1.console.aws.amazon.com/lambda/
- **API Gateway**: https://ap-south-1.console.aws.amazon.com/apigateway/

## Status

✅ API is live and ready to use!
