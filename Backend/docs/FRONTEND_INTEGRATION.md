# Frontend Integration Guide

## 🎯 Quick Start

Your Lambda API is **live and ready to use**!

### API Base URL
```
https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev
```

---

## 📡 API Endpoints

### 1. Get All Grades
```
GET /grades
```

**Response:**
```json
{
  "grades": ["Grade 7"]
}
```

**JavaScript:**
```javascript
const response = await fetch('https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades');
const data = await response.json();
console.log(data.grades); // ["Grade 7"]
```

---

### 2. Get Subjects for a Grade
```
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

**JavaScript:**
```javascript
const grade = "Grade 7";
const encoded = encodeURIComponent(grade);
const response = await fetch(`https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades/${encoded}/subjects`);
const data = await response.json();
console.log(data.subjects); // ["Science"]
```

---

### 3. Get Chapters for a Subject
```
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

**JavaScript:**
```javascript
const grade = "Grade 7";
const subject = "Science";
const encodedGrade = encodeURIComponent(grade);
const encodedSubject = encodeURIComponent(subject);

const response = await fetch(
  `https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades/${encodedGrade}/subjects/${encodedSubject}/chapters`
);
const data = await response.json();
console.log(data.chapters); // Array of 13 chapters
```

---

## 🔑 Lambda Function Details

| Property | Value |
|----------|-------|
| **Name** | `question-paper-catalog-listing-dev` |
| **ARN** | `arn:aws:lambda:ap-south-1:622158567844:function:question-paper-catalog-listing-dev` |
| **Runtime** | Python 3.11 |
| **Handler** | `app.lambda_handler` |
| **Memory** | 256 MB |
| **Timeout** | 30 seconds |
| **Region** | ap-south-1 (Mumbai) |

---

## 🛠️ Example: React Component

```jsx
import { useState, useEffect } from 'react';

const API_BASE_URL = 'https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev';

export function CatalogListing() {
  const [grades, setGrades] = useState([]);
  const [selectedGrade, setSelectedGrade] = useState('');
  const [subjects, setSubjects] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState('');
  const [chapters, setChapters] = useState([]);
  const [loading, setLoading] = useState(false);

  // Fetch grades on mount
  useEffect(() => {
    fetchGrades();
  }, []);

  const fetchGrades = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/grades`);
      const data = await response.json();
      setGrades(data.grades);
    } catch (error) {
      console.error('Error fetching grades:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSubjects = async (grade) => {
    setLoading(true);
    setSelectedGrade(grade);
    setSelectedSubject('');
    setChapters([]);
    
    try {
      const encoded = encodeURIComponent(grade);
      const response = await fetch(`${API_BASE_URL}/grades/${encoded}/subjects`);
      const data = await response.json();
      setSubjects(data.subjects);
    } catch (error) {
      console.error('Error fetching subjects:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchChapters = async (grade, subject) => {
    setLoading(true);
    setSelectedSubject(subject);
    
    try {
      const encodedGrade = encodeURIComponent(grade);
      const encodedSubject = encodeURIComponent(subject);
      const response = await fetch(
        `${API_BASE_URL}/grades/${encodedGrade}/subjects/${encodedSubject}/chapters`
      );
      const data = await response.json();
      setChapters(data.chapters);
    } catch (error) {
      console.error('Error fetching chapters:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Question Paper Catalog</h1>

      {/* Grade Selection */}
      <div>
        <h2>Select Grade</h2>
        {grades.map(grade => (
          <button
            key={grade}
            onClick={() => fetchSubjects(grade)}
            style={{ fontWeight: selectedGrade === grade ? 'bold' : 'normal' }}
          >
            {grade}
          </button>
        ))}
      </div>

      {/* Subject Selection */}
      {subjects.length > 0 && (
        <div>
          <h2>Select Subject</h2>
          {subjects.map(subject => (
            <button
              key={subject}
              onClick={() => fetchChapters(selectedGrade, subject)}
              style={{ fontWeight: selectedSubject === subject ? 'bold' : 'normal' }}
            >
              {subject}
            </button>
          ))}
        </div>
      )}

      {/* Chapters List */}
      {chapters.length > 0 && (
        <div>
          <h2>Chapters</h2>
          <ul>
            {chapters.map(chapter => (
              <li key={chapter.id}>
                <strong>{chapter.title}</strong>
                <p>Folder: {chapter.folder}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {loading && <p>Loading...</p>}
    </div>
  );
}
```

---

## 🛠️ Example: Vue Component

```vue
<template>
  <div>
    <h1>Question Paper Catalog</h1>

    <!-- Grades -->
    <div>
      <h2>Select Grade</h2>
      <button
        v-for="grade in grades"
        :key="grade"
        @click="selectGrade(grade)"
        :style="{ fontWeight: selectedGrade === grade ? 'bold' : 'normal' }"
      >
        {{ grade }}
      </button>
    </div>

    <!-- Subjects -->
    <div v-if="subjects.length > 0">
      <h2>Select Subject</h2>
      <button
        v-for="subject in subjects"
        :key="subject"
        @click="selectSubject(subject)"
        :style="{ fontWeight: selectedSubject === subject ? 'bold' : 'normal' }"
      >
        {{ subject }}
      </button>
    </div>

    <!-- Chapters -->
    <div v-if="chapters.length > 0">
      <h2>Chapters</h2>
      <ul>
        <li v-for="chapter in chapters" :key="chapter.id">
          <strong>{{ chapter.title }}</strong>
          <p>Folder: {{ chapter.folder }}</p>
        </li>
      </ul>
    </div>

    <p v-if="loading">Loading...</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      apiBaseUrl: 'https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev',
      grades: [],
      subjects: [],
      chapters: [],
      selectedGrade: '',
      selectedSubject: '',
      loading: false,
    };
  },
  mounted() {
    this.fetchGrades();
  },
  methods: {
    async fetchGrades() {
      this.loading = true;
      try {
        const response = await fetch(`${this.apiBaseUrl}/grades`);
        const data = await response.json();
        this.grades = data.grades;
      } catch (error) {
        console.error('Error fetching grades:', error);
      } finally {
        this.loading = false;
      }
    },
    async selectGrade(grade) {
      this.selectedGrade = grade;
      this.selectedSubject = '';
      this.chapters = [];
      this.loading = true;
      try {
        const encoded = encodeURIComponent(grade);
        const response = await fetch(`${this.apiBaseUrl}/grades/${encoded}/subjects`);
        const data = await response.json();
        this.subjects = data.subjects;
      } catch (error) {
        console.error('Error fetching subjects:', error);
      } finally {
        this.loading = false;
      }
    },
    async selectSubject(subject) {
      this.selectedSubject = subject;
      this.loading = true;
      try {
        const encodedGrade = encodeURIComponent(this.selectedGrade);
        const encodedSubject = encodeURIComponent(subject);
        const response = await fetch(
          `${this.apiBaseUrl}/grades/${encodedGrade}/subjects/${encodedSubject}/chapters`
        );
        const data = await response.json();
        this.chapters = data.chapters;
      } catch (error) {
        console.error('Error fetching chapters:', error);
      } finally {
        this.loading = false;
      }
    },
  },
};
</script>
```

---

## 🛠️ Example: Plain JavaScript

```javascript
const API_BASE_URL = 'https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev';

// Initialize UI
async function initializeCatalog() {
  const grades = await fetchGrades();
  displayGrades(grades);
}

async function fetchGrades() {
  const response = await fetch(`${API_BASE_URL}/grades`);
  return await response.json();
}

async function fetchSubjects(grade) {
  const encoded = encodeURIComponent(grade);
  const response = await fetch(`${API_BASE_URL}/grades/${encoded}/subjects`);
  return await response.json();
}

async function fetchChapters(grade, subject) {
  const encodedGrade = encodeURIComponent(grade);
  const encodedSubject = encodeURIComponent(subject);
  const response = await fetch(
    `${API_BASE_URL}/grades/${encodedGrade}/subjects/${encodedSubject}/chapters`
  );
  return await response.json();
}

function displayGrades(data) {
  const container = document.getElementById('grades-container');
  data.grades.forEach(grade => {
    const button = document.createElement('button');
    button.textContent = grade;
    button.onclick = () => handleGradeSelect(grade);
    container.appendChild(button);
  });
}

async function handleGradeSelect(grade) {
  const data = await fetchSubjects(grade);
  displaySubjects(data.subjects, grade);
}

function displaySubjects(subjects, grade) {
  const container = document.getElementById('subjects-container');
  container.innerHTML = '';
  subjects.forEach(subject => {
    const button = document.createElement('button');
    button.textContent = subject;
    button.onclick = () => handleSubjectSelect(grade, subject);
    container.appendChild(button);
  });
}

async function handleSubjectSelect(grade, subject) {
  const data = await fetchChapters(grade, subject);
  displayChapters(data.chapters);
}

function displayChapters(chapters) {
  const container = document.getElementById('chapters-container');
  container.innerHTML = '';
  chapters.forEach(chapter => {
    const item = document.createElement('div');
    item.innerHTML = `
      <h3>${chapter.title}</h3>
      <p>ID: ${chapter.id}</p>
      <p>Order: ${chapter.order}</p>
      <p>Folder: ${chapter.folder}</p>
    `;
    container.appendChild(item);
  });
}

// Start
initializeCatalog();
```

---

## 📌 Important Notes

### URL Encoding
Grades and subjects with spaces must be URL-encoded:
- `Grade 7` → `Grade%207`
- `Science` → `Science` (no spaces, no encoding needed)

**JavaScript `encodeURIComponent()` handles this automatically.**

### Response Fields
Each chapter object has:
- `id` - Chapter identifier (e.g., "ch01")
- `order` - Chapter number (e.g., 1)
- `title` - Chapter title (e.g., "Nutrition in Plants")
- `folder` - S3 folder name (e.g., "Ch01_Nutrition_in_Plants")

⚠️ **Note**: Old response had `file` field. This has changed to `folder`.

### CORS
API has CORS enabled for all origins (`*`)

---

## 🚀 Environment Setup (Frontend)

Add to `.env.local`:
```
REACT_APP_API_URL=https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev
```

Or use directly in code:
```javascript
const API_URL = 'https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev';
```

---

## ✅ Testing

### Using cURL
```bash
# Get grades
curl https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades

# Get subjects
curl "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades/Grade%207/subjects"

# Get chapters
curl "https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades/Grade%207/subjects/Science/chapters"
```

### Using Postman
1. Set URL: `https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev/grades`
2. Set Method: `GET`
3. Send

---

## 📊 Data Structure

### Grade 7 / Science Curriculum

The API currently returns data for Grade 7 / Science with 13 chapters:

1. Nutrition in Plants
2. Nutrition in Animals
3. Photosynthesis
4. Respiration
5. Transportation
6. Excretion
7. Control and Coordination
8. Reproduction
9. Food Production
10. Heredity and Evolution
11. Light Reflection and Refraction
12. Electricity and Its Effects
13. Wastewater Story

---

## 🔗 Cloud Infrastructure

| Component | Details |
|-----------|---------|
| **API Gateway** | `https://ah3gmfnv87.execute-api.ap-south-1.amazonaws.com/dev` |
| **Lambda** | `question-paper-catalog-listing-dev` |
| **Region** | ap-south-1 (Mumbai) |
| **S3 Bucket** | assessment-drafting-engine |
| **Status** | ✅ Live and Running |

---

## 📞 Support

For issues or questions:
1. Check CloudWatch logs: https://ap-south-1.console.aws.amazon.com/cloudwatch/
2. View Lambda: https://ap-south-1.console.aws.amazon.com/lambda/
3. Check API status: Test with curl command above

---

**Ready to integrate! 🚀**

