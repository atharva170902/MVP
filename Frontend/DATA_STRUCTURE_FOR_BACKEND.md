# Exact Data Structure to Save - Simple & Clear

## What Needs to be Saved

### 1. Chapters Selected & Marks Assigned
```
selectedChapters: ["ch_nutrition_plants", "ch_acids_bases"]
marksAllocation: {
    "ch_nutrition_plants": 8,
    "ch_acids_bases": 12
}
```

### 2. Question Paper Details (Q1-Q9)

Each question has:
- **Chapter**: Which chapter (dropdown from selected chapters)
- **Domain**: R/U, Ap, or An/E (learning domain/question type)
- **Images**: Diagrams/images selected from left panel (if any)

---

## Complete Data Structure

```javascript
{
    // Basic info (already working)
    draftId: "550e8400-...",
    examType: "PT",
    grade: "Grade 7",
    subject: "Science",
    
    // WHAT YOU WANT TO SAVE:
    
    // 1. Chapters & Marks
    selectedChapters: [
        "ch_01",  // Nutrition in Plants
        "ch_02"   // Acids Bases and Salts
    ],
    
    marksAllocation: {
        "ch_01": 8,
        "ch_02": 12
    },
    
    // 2. Question Paper (Q1-Q9)
    questionPaper: {
        // SECTION A: Multiple Choice (Q1-Q4)
        q1: {
            chapter: "ch_01",           // Nutrition in Plants
            domain: "R/U",              // Remember/Understand (or Ap, An/E)
            images: [                   // Diagrams/images from left panel
                {
                    id: "img_001",
                    name: "plant_diagram.png",
                    url: "https://s3.amazonaws.com/..."
                }
            ]
        },
        q2: {
            chapter: "ch_01",
            domain: "R/U",
            images: []                  // No images selected
        },
        q3: {
            chapter: "ch_02",
            domain: "R/U",
            images: [{id: "img_002", name: "acid_diagram.png", url: "..."}]
        },
        q4: {
            chapter: "ch_01",
            domain: "R/U",
            images: []
        },
        
        // SECTION B: Very Short Answer (Q5-Q6)
        q5: {
            chapter: "ch_02",
            domain: "An/E",             // Analyze/Evaluate
            images: []
        },
        q6: {
            chapter: "ch_01",
            domain: "R/U",
            images: [{id: "img_003", name: "plant_diagram2.png", url: "..."}]
        },
        
        // SECTION C: Short Answer (Q7)
        q7: {
            chapter: "ch_01",
            domain: "Ap",               // Apply
            images: []
        },
        
        // SECTION D: Long Answer (Q8)
        q8: {
            chapter: "ch_02",
            domain: "An/E",
            images: [{id: "img_004", name: "acid_diagram2.png", url: "..."}]
        },
        
        // SECTION E: Case-Based Assessment (Q9)
        q9: {
            chapter: "ch_01",
            domain: "An/E",
            images: []
        }
    }
}
```

---

## What Each Field Means

| Field | Example | Meaning |
|-------|---------|---------|
| `chapter` | `"ch_01"` | Chapter selected (from left panel dropdown) |
| `domain` | `"R/U"` | Learning domain/Question type (R/U, Ap, or An/E) |
| `images` | `[{id, name, url}]` | Diagrams/images selected from left panel, empty if none |

---

## Question Types (Taxonomy)

```
R/U     = Remember / Understand
Ap      = Apply
An/E    = Analyze / Evaluate
```

---

## Frontend to Backend Flow

### Step 1: User Selects Chapters & Marks
```
Frontend: User selects "Nutrition in Plants" + "Acids Bases and Salts"
Frontend: User assigns 8 marks to "Nutrition in Plants", 12 to "Acids Bases"

Data saved:
selectedChapters: ["ch_01", "ch_02"]
marksAllocation: {"ch_01": 8, "ch_02": 12}
```

### Step 2: User Fills Q1-Q9
```
User fills Q1:
- Selects chapter: "Nutrition in Plants" (ch_01)
- Selects type: "R/U" 
- Drags diagram: "diagram_plant_01" (or leaves empty)

Data saved:
q1: {
    chapter: "ch_01",
    questionType: "R/U",
    diagram: "diagram_plant_01"
}
```

### Step 3: Backend Receives Complete Data
```
POST /api/drafts or PATCH /api/drafts/{draftId}

{
    draftId: "550e8400-...",
    selectedChapters: ["ch_01", "ch_02"],
    marksAllocation: {"ch_01": 8, "ch_02": 12},
    questionPaper: {
        q1: {chapter: "ch_01", questionType: "R/U", diagram: "diagram_plant_01"},
        q2: {chapter: "ch_01", questionType: "R/U", diagram: null},
        ...
    }
}
```

---

## DynamoDB Item (What Gets Stored)

```javascript
{
    userId: "user123",
    draftId: "550e8400-...",
    examType: "PT",
    grade: "Grade 7",
    subject: "Science",
    
    // ← WHAT YOU WANT TO SAVE:
    selectedChapters: ["ch_01", "ch_02"],
    marksAllocation: {
        "ch_01": 8,
        "ch_02": 12
    },
    questionPaper: {
        q1: {chapter: "ch_01", questionType: "R/U", diagram: "diagram_plant_01"},
        q2: {chapter: "ch_01", questionType: "R/U", diagram: null},
        q3: {chapter: "ch_02", questionType: "R/U", diagram: "diagram_acid_01"},
        q4: {chapter: "ch_01", questionType: "R/U", diagram: null},
        q5: {chapter: "ch_02", questionType: "An/E", diagram: null},
        q6: {chapter: "ch_01", questionType: "R/U", diagram: "diagram_plant_02"},
        q7: {chapter: "ch_01", questionType: "Ap", diagram: null},
        q8: {chapter: "ch_02", questionType: "An/E", diagram: "diagram_acid_02"},
        q9: {chapter: "ch_01", questionType: "An/E", diagram: null}
    },
    
    createdAt: 1705315800,
    updatedAt: 1705316700,
    syncStatus: "synced"
}
```

---

## Backend Endpoints (Simple)

### Create Draft
```
POST /api/drafts
{
    selectedChapters: ["ch_01", "ch_02"],
    marksAllocation: {"ch_01": 8, "ch_02": 12},
    questionPaper: {q1: {...}, q2: {...}, ...}
}
→ Returns draftId
```

### Update Draft (Auto-Save)
```
PATCH /api/drafts/{draftId}
{
    selectedChapters: ["ch_01", "ch_02"],
    marksAllocation: {"ch_01": 8, "ch_02": 12},
    questionPaper: {q1: {...}, q2: {...}, ...}
}
→ Returns { syncStatus: "synced" }
```

### Get Draft (Load)
```
GET /api/drafts/{draftId}
→ Returns complete data with all chapters, marks, Q1-Q9
```

### Delete Draft
```
DELETE /api/drafts/{draftId}
→ Removes all saved data
```

---

## Important Notes

### 1. Chapters
- Must come from the left panel dropdown
- User selects which chapters to include
- Then marks are assigned to each
- Q1-Q9 can only select from these chapters

### 2. Question Types
- Must be one of: R/U, Ap, An/E
- Dropdown in UI for each question

### 3. Diagrams
- Can be null (no diagram selected)
- Or diagram ID if dragged from left panel
- Example: "diagram_plant_01", "diagram_acid_01"

### 4. Sections
- Frontend organizes into 5 sections
- Backend just stores all Q1-Q9 in questionPaper object
- No need to distinguish sections on backend

---

## Section Breakdown (For Reference)

```
SECTION A (Q1-Q4): Multiple Choice
- 4 questions
- 1 mark each

SECTION B (Q5-Q6): Very Short Answer
- 2 questions
- 2 marks each

SECTION C (Q7): Short Answer
- 1 question
- 3 marks

SECTION D (Q8): Long Answer
- 1 question
- 5 marks

SECTION E (Q9): Case-Based Assessment
- 1 question
- 4 marks
```

But on backend, all stored as:
```
questionPaper: {
    q1: {...},
    q2: {...},
    ...
    q9: {...}
}
```

---

## Example: Saving Q1

**Frontend User Action:**
1. Opens Q1
2. Clicks dropdown: Selects "Nutrition in Plants"
3. Clicks domain dropdown: Selects "R/U"
4. Drags images: Drags "plant_diagram.png" from left panel

**Data Structure Created:**
```javascript
q1: {
    chapter: "ch_01",           // Nutrition in Plants
    domain: "R/U",              // Remember/Understand
    images: [                   // Dragged images
        {
            id: "img_001",
            name: "plant_diagram.png",
            url: "https://s3.amazonaws.com/..."
        }
    ]
}
```

**Sent to Backend:**
```
PATCH /api/drafts/550e8400-...
{
    "questionPaper": {
        "q1": {
            "chapter": "ch_01",
            "domain": "R/U",
            "images": [{id: "img_001", name: "plant_diagram.png", url: "..."}]
        }
    }
}
```

**Stored in DynamoDB:**
```
Item {
    userId: "user123",
    draftId: "550e8400-...",
    questionPaper: {
        q1: {
            chapter: "ch_01",
            domain: "R/U",
            images: [{id: "img_001", name: "plant_diagram.png", url: "..."}]
        }
    }
}
```

---

## Frontend Implementation (What's Already Done)

In `craft-a-paper.js`, when user updates Q1:

```javascript
// User changes chapter
updateSessionData('questionPaper.q1.chapter', 'ch_01');

// User changes domain/question type
updateSessionData('questionPaper.q1.domain', 'R/U');

// User drags images from left panel
updateSessionData('questionPaper.q1.images', [
    {
        id: "img_001",
        name: "plant_diagram.png",
        url: "https://..."
    }
]);

// After 30 seconds, auto-save sends to backend:
// PATCH /api/drafts/{draftId}
// { 
//     questionPaper: { 
//         q1: {
//             chapter: "ch_01",
//             domain: "R/U",
//             images: [{id, name, url}]
//         }
//     }
// }
```

---

## Summary: What Gets Saved to DynamoDB

1. ✅ **Chapters Selected** - List of chapter IDs
2. ✅ **Marks Allocated** - Marks for each chapter
3. ✅ **Q1-Q9 Details** - For each question:
   - Chapter selected
   - Question type (R/U, Ap, An/E)
   - Diagram (if selected)

**That's it!** Three things, clearly structured, ready for backend to store and retrieve.

---

## Is This Correct?

Please confirm:
- ✅ Chapter field correct?
- ✅ Domain field correct? (R/U, Ap, An/E)?
- ✅ Images field correct? (array of {id, name, url})?
- ❓ Should we store anything else?
- ❓ Should we change any field names?
- ❓ Image structure correct?
