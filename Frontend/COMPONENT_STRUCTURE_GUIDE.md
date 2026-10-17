# Craft-a-Paper Page Component Structure Guide

## Overview
The `craft-a-paper.js` page is a **multi-step form** for creating question papers. It has 3 main views and uses a **session-based architecture**.

---

## High-Level Architecture

```
CraftAPaper Page (craft-a-paper.js)
│
├── Imports & Setup
│   ├── React Hooks (useState, useEffect)
│   ├── Next.js (useRouter, Link, Head)
│   ├── Session Management (useSessionManagement)
│   └── API Functions (getGrades, getChapters, etc.)
│
├── State Management
│   ├── showHome: boolean (toggle between home and form)
│   ├── currentSession: object (all form data)
│   ├── drafts: array (list of saved drafts)
│   └── Derived states (step, selectedGrade, etc.)
│
└── Main UI (showHome ? HomeView : WorkspaceView)
    ├── HomeView (Show saved drafts)
    └── WorkspaceView (3-Step Form)
```

---

## Page Views

### 1️⃣ **HOME VIEW** (showHome === true)

**Location:** Top of page when you first load `http://localhost:3000/craft-a-paper`

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│                    Craft a Paper                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Left Column                    Right Column                │
│  ┌────────────────────────┐    ┌─────────────────────────┐ │
│  │ Create New Paper       │    │ Previously Drafted      │ │
│  │                        │    │ Papers                  │ │
│  │ [+ New Paper] Button   │    │                         │ │
│  │                        │    │ ├─ PT • Grade 7 • Sci  │ │
│  │ (Click to start)       │    │ ├─ PT • Grade 8 • Math │ │
│  │                        │    │ └─ PT • Grade 9 • Eng  │ │
│  └────────────────────────┘    └─────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Components Used:**
- **Left Column**: Card with "Create New Paper" heading
  - Button: `+ New Paper` → Calls `handleCreateNewPaper()`
  
- **Right Column**: Previously Drafted Papers Card
  - **List Component**: Maps over `drafts` array
    - Each draft item shows:
      - Exam type + Grade + Subject (PT • Grade 7 • Science)
      - Step number (Step 3)
      - Chapter count (2 chapters selected)
      - Last saved time (Last saved 3 min ago)
      - **Delete Button** (appears on hover) → `handleDeleteDraft()`

---

### 2️⃣ **WORKSPACE VIEW** (showHome === false)

When you click "New Paper" or resume a draft, you enter the **3-step form**.

#### **Step 1: Exam Type, Grade & Subject**
```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  Global Header Section                                      │
│  ├─ "Craft a Paper" title with Home button                 │
│  ├─ Save indicator (Saving… / Draft saved / Error)         │
│  └─ Current draft info: PT • Grade 7 • Science             │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Step 1: Exam Type, Grade & Subject                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                                                        │ │
│  │  Select Exam Type                                     │ │
│  │  ├─ [PT] [Midterm] [Preboard] [Final] Buttons        │ │
│  │  └─ PT selected (blue highlight)                     │ │
│  │                                                        │ │
│  │  Select Grade                                         │ │
│  │  ├─ Dropdown: Grade 7, Grade 8, Grade 9             │ │
│  │  └─ Grade 7 selected                                 │ │
│  │                                                        │ │
│  │  Select Subject                                       │ │
│  │  ├─ Dropdown: Science, Math, English (depends on gr) │ │
│  │  └─ Science selected                                 │ │
│  │                                                        │ │
│  │  [Back] [Continue to Step 2]                         │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Components/Elements:**
- **Exam Type Selector**: Button group
  - 4 buttons: PT, Midterm, Preboard, Final
  - Selected exam highlighted in blue
  - Handler: `handleExamChange(examType)`

- **Grade Dropdown**: Native select
  - Populated by `getGrades()` API
  - Handler: `handleGradeChange(grade)`
  - Cascades: Resets subject & chapters

- **Subject Dropdown**: Native select
  - Populated by `getSubjects(grade)` API (cascades from grade)
  - Handler: `handleSubjectChange(subject)`
  - Cascades: Resets chapters

- **Navigation Buttons**:
  - "Back" → `handleBackToHome()`
  - "Continue to Step 2" → `handleStepChange(2)`

---

#### **Step 2: Chapter Selection & Marks Allocation**
```
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Chapter Selection & Marks Allocation              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                                                        │ │
│  │  Available Chapters (Grade 7 • Science)              │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │                                                  │ │ │
│  │  │  Chapter Selection Section:                     │ │ │
│  │  │  ├─ [☑] Ch 1: Nutrition in Plants       [5]    │ │ │
│  │  │  ├─ [☑] Ch 2: Nutrition in Animals     [3]    │ │ │
│  │  │  ├─ [☐] Ch 3: Heat & Transfer          [    ]  │ │ │
│  │  │  ├─ [☐] Ch 4: Light & Shadow           [    ]  │ │ │
│  │  │  └─ [☐] Ch 5: Acids & Bases            [    ]  │ │ │
│  │  │                                                  │ │ │
│  │  │  Total Marks Allocated: 8 / 20                 │ │ │
│  │  │                                                  │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  [Back] [Continue to Step 3]                         │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Components/Elements:**
- **Chapter Grid**: Displays available chapters
  - Populated by `getChapters(grade, subject)` API
  - Each chapter row:
    - Checkbox: `☑` checked / `☐` unchecked
    - Chapter title: "Ch 1: Nutrition in Plants"
    - Marks input field: Number input [5]
    - Handler: `toggleChapter(chapterId)`
    - Handler: `handleMarksChange(chapterId, value)`

- **Total Marks Display**:
  - Shows: "8 / 20" (allocated / total)
  - Calculated from `marksAllocation` object

- **Navigation**:
  - "Back" → `handleStepChange(1)`
  - "Continue to Step 3" → `handleStepChange(3)`
  - Disabled if no chapters selected

---

#### **Step 3: Question Paper with Q1-Q9**
```
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Question Paper                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                                                        │ │
│  │  PT • Grade 7 • Science • 20 Marks • 60 Minutes      │ │
│  │                                                        │ │
│  │  SECTION A: Multiple Choice (Q1-Q4)                  │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ Q1. [Chapter: Nutrition in Plants ▼]            │ │ │
│  │  │     Domain: [R/U ▼]                             │ │ │
│  │  │     [Drag images here]                          │ │ │
│  │  │                                                  │ │ │
│  │  │ Q2. [Chapter: Nutrition in Animals ▼]           │ │ │
│  │  │     Domain: [R/U ▼]                             │ │ │
│  │  │     [Drag images here]                          │ │ │
│  │  │                                                  │ │ │
│  │  │ ... (Q3, Q4 similar)                            │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  SECTION B: Very Short Answer (Q5-Q6)               │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ Q5. [Chapter ▼] [Domain ▼] [Images...]         │ │ │
│  │  │ Q6. [Chapter ▼] [Domain ▼] [Images...]         │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  SECTION C: Short Answer (Q7)                        │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ Q7. [Chapter ▼] [Domain ▼] [Images...]         │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  SECTION D: Long Answer (Q8)                         │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ Q8. [Chapter ▼] [Domain ▼] [Images...]         │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  SECTION E: Case-Based Assessment (Q9)              │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ Q9. [Chapter ▼] [Domain ▼] [Images...]         │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  [Back] [Save Draft]                                │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Components/Elements:**

1. **Paper Header**:
   - Title: "PT • Grade 7 • Science • 20 Marks • 60 Minutes"
   - Calculated from currentSession

2. **Question Sections** (5 total):
   - **Section A**: Multiple Choice (Q1-Q4) - 4 questions
   - **Section B**: Very Short Answer (Q5-Q6) - 2 questions
   - **Section C**: Short Answer (Q7) - 1 question
   - **Section D**: Long Answer (Q8) - 1 question
   - **Section E**: Case-Based Assessment (Q9) - 1 question

3. **Question Item** (repeated for Q1-Q9):
   ```
   Q1. [Chapter Dropdown ▼] [Domain Dropdown ▼]
       [Drag Images Here] or [Image1] [x] [Image2] [x]
   ```
   
   Each question has:
   - **Chapter Dropdown**: 
     - Populated by `selectedChapters`
     - Handler: `updateQuestionChapter(questionId, chapter)`
   
   - **Domain Dropdown**: 
     - Options: R/U (Remember/Understand), An/E (Analyze/Evaluate), Ap (Apply)
     - Handler: `updateQuestionDomain(questionId, domain)`
   
   - **Image Drop Zone**:
     - Drag and drop images
     - Handler: `handleDropDiagram(e, questionId)`
     - Shows dropped images with delete button [x]
     - Handler: `removeImageFromQuestion(questionId, index)`

4. **Navigation**:
   - "Back" → `handleStepChange(2)`
   - "Save Draft" → `handleSaveDraft()`

---

## State Flow Diagram

```
User Actions → Event Handler → updateSessionData() → currentSession updated
                                                    ↓
                                          UI re-renders with new data
                                                    ↓
                                          Auto-save every 30s
                                                    ↓
                                          Save to localStorage + Backend
```

### Example: Selecting a Grade

```
1. User clicks "Grade 7" dropdown
   ↓
2. handleGradeChange('Grade 7') called
   ↓
3. updateSessionData('grade', 'Grade 7')
   ↓
4. currentSession.grade = 'Grade 7'
   ↓
5. Component re-renders
   ↓
6. getSubjects('Grade 7') API called
   ↓
7. Subject dropdown populated with Science, Math, English
```

---

## Key Functions

### Session Management
- `createSession(initialData)` - Create new empty session
- `loadSession(draftId)` - Load existing draft into session
- `updateSessionData(path, value)` - Update any session field
- `saveSession()` - Save session to backend/localStorage

### Handlers
- `handleCreateNewPaper()` - Start new draft
- `handleResumeDraft(draftSummary)` - Open existing draft
- `handleDeleteDraft(draftId, e)` - Delete draft with confirmation
- `handleStepChange(newStep)` - Navigate between steps
- `handleGradeChange(grade)` - Select grade (cascades)
- `handleSubjectChange(subject)` - Select subject (cascades)
- `toggleChapter(chapterId)` - Check/uncheck chapter
- `handleMarksChange(chapterId, value)` - Update marks for chapter
- `updateQuestionChapter(questionId, chapter)` - Set Q1-Q9 chapter
- `updateQuestionDomain(questionId, domain)` - Set Q1-Q9 domain
- `handleDropDiagram(e, questionId)` - Add image to question
- `removeImageFromQuestion(questionId, index)` - Delete image from question

---

## Data Structure in Session

```javascript
{
  draftId: "uuid",
  userId: "user123",
  
  // Step 1: Basic Info
  step: 1,
  examType: "PT",
  grade: "Grade 7",
  subject: "Science",
  
  // Step 2: Chapters & Marks
  selectedChapters: ["ch_01", "ch_02"],
  marksAllocation: {
    "ch_01": 5,
    "ch_02": 3
  },
  selectedDiagrams: ["diagram_1", "diagram_2"],
  
  // Step 3: Question Paper (Q1-Q9)
  questionPaper: {
    q1: {
      chapter: "Nutrition in Plants",
      domain: "R/U",
      images: [
        { id: "img1", name: "plant_diagram.png", url: "..." }
      ]
    },
    q2: {
      chapter: "Nutrition in Animals",
      domain: "R/U",
      images: []
    },
    // ... q3 through q9
  },
  
  // Metadata
  createdAt: "2024-01-15T10:30:00Z",
  updatedAt: "2024-01-15T10:45:00Z",
  syncStatus: "synced"
}
```

---

## Component Tree

```
CraftAPaper (Main Component)
│
├── SaveIndicator (Mini component - shows save status)
│
├── HomeView (if showHome === true)
│   ├── "Create New Paper" Card
│   │   └── Button: + New Paper
│   │
│   └── "Previously Drafted Papers" Card
│       └── DraftList (maps over drafts)
│           └── DraftItem (each draft)
│               ├── Title (exam • grade • subject)
│               ├── Step badge
│               └── Delete Button (on hover)
│
└── WorkspaceView (if showHome === false)
    │
    ├── GlobalHeader
    │   ├── "Craft a Paper" title
    │   ├── Home button
    │   └── SaveIndicator
    │
    └── Step-based Rendering
        │
        ├── Step 1 (if step === 1)
        │   ├── Exam Type Buttons (PT, Midterm, Preboard, Final)
        │   ├── Grade Dropdown
        │   ├── Subject Dropdown
        │   └── Navigation Buttons
        │
        ├── Step 2 (if step === 2)
        │   ├── Chapter Selection List
        │   │   └── ChapterRow (for each chapter)
        │   │       ├── Checkbox
        │   │       ├── Chapter name
        │   │       └── Marks input
        │   ├── Total Marks Display
        │   └── Navigation Buttons
        │
        └── Step 3 (if step === 3)
            ├── Paper Header (title, marks, time)
            ├── SectionA (Q1-Q4)
            │   └── QuestionItem × 4
            ├── SectionB (Q5-Q6)
            │   └── QuestionItem × 2
            ├── SectionC (Q7)
            │   └── QuestionItem × 1
            ├── SectionD (Q8)
            │   └── QuestionItem × 1
            ├── SectionE (Q9)
            │   └── QuestionItem × 1
            │       ├── Chapter Dropdown
            │       ├── Domain Dropdown
            │       ├── Image Drop Zone
            │       └── Image List with Delete
            └── Navigation Buttons (Back, Save Draft)
```

---

## Summary

**craft-a-paper.js** is a **multi-step form page** that:

1. **Shows home view** with drafts list + create new button
2. **Guides users through 3 steps**:
   - Step 1: Select exam type, grade, subject
   - Step 2: Select chapters and allocate marks
   - Step 3: Build question paper (Q1-Q9) with chapter, domain, images
3. **Uses session management** to persist all data
4. **Auto-saves every 30 seconds** to localStorage + backend
5. **Allows editing** each question with chapter, domain, and image selection
6. **Supports delete** of duplicate drafts safely

---

## Next Steps for Understanding

- **See it live**: Open `http://localhost:3000/craft-a-paper`
- **Test Step 1**: Select grade and subject
- **Test Step 2**: Select chapters and marks
- **Test Step 3**: Fill Q1-Q9 with chapters and domains
- **Test Persistence**: Refresh page - data should remain
- **Test Multi-draft**: Create 2 drafts and switch between them
