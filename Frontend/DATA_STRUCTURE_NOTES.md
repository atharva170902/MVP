# Question Paper Data Structure - Backend Integration Notes

## Overview
The Question Paper Editor (Step 3, Canvas 1) saves structured data for each question. This document outlines the format for backend storage and processing.

## Complete Data Structure

```json
{
  "exam_type": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "selected_chapters": [
    {
      "id": "ch_02",
      "title": "Nutrition in Plants",
      "folder": "Ch02_Nutrition_in_Plants"
    },
    {
      "id": "ch_08",
      "title": "Nutrition in Animals",
      "folder": "Ch08_Nutrition_in_Animals"
    }
  ],
  "marks_allocation": {
    "ch_02": 8,
    "ch_08": 12
  },
  "total_marks": 20,
  "sections": {
    "A": {
      "title": "Multiple Choice Questions",
      "type": "MCQ",
      "marks_per_question": 1,
      "total_questions": 4,
      "total_marks": 4,
      "questions": [
        {
          "question_number": 1,
          "section": "A",
          "chapter": "Nutrition in Plants",
          "learning_domain": "R/U",
          "marks": 1,
          "diagrams": []
        },
        {
          "question_number": 2,
          "section": "A",
          "chapter": "Nutrition in Animals",
          "learning_domain": "Ap",
          "marks": 1,
          "diagrams": [
            {
              "key": "diagram_1",
              "name": "Leaf Structure",
              "url": "s3://bucket/diagrams/leaf.jpg",
              "folder": "Ch02_Nutrition_in_Plants"
            }
          ]
        }
      ]
    },
    "B": {
      "title": "Very Short Answer",
      "type": "VSA",
      "marks_per_question": 2,
      "total_questions": 2,
      "total_marks": 4,
      "questions": [
        {
          "question_number": 5,
          "section": "B",
          "chapter": "Nutrition in Plants",
          "learning_domain": "An/E",
          "marks": 2,
          "diagrams": []
        },
        {
          "question_number": 6,
          "section": "B",
          "chapter": "Nutrition in Animals",
          "learning_domain": "R/U",
          "marks": 2,
          "diagrams": []
        }
      ]
    },
    "C": {
      "title": "Short Answer",
      "type": "SA",
      "marks_per_question": 3,
      "total_questions": 1,
      "total_marks": 3,
      "questions": [
        {
          "question_number": 7,
          "section": "C",
          "chapter": "Nutrition in Animals",
          "learning_domain": "An/E",
          "marks": 3,
          "diagrams": [
            {
              "key": "diagram_2",
              "name": "Digestive System",
              "url": "s3://bucket/diagrams/digestive.jpg",
              "folder": "Ch08_Nutrition_in_Animals"
            }
          ]
        }
      ]
    },
    "D": {
      "title": "Long Answer",
      "type": "LA",
      "marks_per_question": 5,
      "total_questions": 1,
      "total_marks": 5,
      "questions": [
        {
          "question_number": 8,
          "section": "D",
          "chapter": "Nutrition in Plants",
          "learning_domain": "Ap",
          "marks": 5,
          "diagrams": []
        }
      ]
    },
    "E": {
      "title": "Case-Based Assessment",
      "type": "CBA",
      "marks_per_question": 4,
      "total_questions": 1,
      "total_marks": 4,
      "questions": [
        {
          "question_number": 9,
          "section": "E",
          "chapter": "Nutrition in Animals",
          "learning_domain": "R/U",
          "marks": 4,
          "diagrams": []
        }
      ]
    }
  },
  "metadata": {
    "total_questions": 9,
    "total_marks": 20,
    "created_at": "2026-09-11T10:30:00Z"
  }
}
```

## Per-Question Structure (Most Important for Backend)

For each question in each section, store:

```json
{
  "question_number": 1,        // 1-9
  "section": "A",              // A, B, C, D, E
  "chapter": "Nutrition in Plants",  // Chapter name (selected from Step 2)
  "learning_domain": "R/U",    // R/U, Ap, An/E (Learning Taxonomy)
  "marks": 1,                  // Marks for this question
  "diagrams": [                // Array of diagrams (can be empty)
    {
      "key": "unique_id",
      "name": "Diagram Name",
      "url": "s3://path/to/diagram",
      "folder": "Chapter_Folder"
    }
  ]
}
```

## Section Breakdown

| Section | Type | Questions | Marks/Q | Total |
|---------|------|-----------|---------|-------|
| A | MCQ | 1-4 | 1 | 4 |
| B | VSA | 5-6 | 2 | 4 |
| C | SA | 7 | 3 | 3 |
| D | LA | 8 | 5 | 5 |
| E | CBA | 9 | 4 | 4 |

## Learning Domains (Bloom's Taxonomy)

- **R/U**: Remembering/Understanding
- **Ap**: Application
- **An/E**: Analysis/Evaluation

## Frontend Function

The `buildQuestionPaperData()` function in `craft-a-paper.js` generates this complete structure for API submission.

### Usage in Backend:

1. **API Endpoint**: Save to `/api/drafts/{draftId}/step3` or similar
2. **Validation**: 
   - All 9 questions must have `chapter` and `learning_domain` set
   - Diagrams array is optional (can be empty)
   - Total marks must equal 20
3. **Storage**: Store entire `sections` object hierarchically
4. **Retrieval**: Load and restore all question data when resuming draft

## Example Backend Save Call (Future Implementation)

```javascript
// Frontend (craft-a-paper.js)
const paperData = buildQuestionPaperData();
await saveDraft(draftId, {
  step: 3,
  canvas1_data: paperData
});

// Backend receives:
{
  "step": 3,
  "canvas1_data": {
    "sections": { /* full structure above */ },
    ...
  }
}
```

## Notes for Backend Developer

- Diagram objects contain full S3 URLs for direct access
- Chapter folder names are preserved for reference
- All questions default to 'R/U' if not explicitly set (frontend default)
- Diagrams are mutable (user can add/remove via UI)
- Learning domain can be changed per question independently
- No question text stored (diagrams + chapter context only)
