# What to Save - Simple Version

## Three Things Only

### 1. Chapters Selected
```
selectedChapters: ["ch_01", "ch_02"]
```

### 2. Marks Assigned to Each Chapter
```
marksAllocation: {
    "ch_01": 8,    // 8 marks for chapter 1
    "ch_02": 12    // 12 marks for chapter 2
}
```

### 3. Q1-Q9 Details

For EACH question (Q1 through Q9), save:

```
q1: {
    chapter: "ch_01",              // Which chapter?
    domain: "R/U",                 // What type? (R/U, Ap, or An/E)
    images: [...]                  // Any diagrams? (or empty)
}

q2: {
    chapter: "ch_01",
    domain: "R/U",
    images: []
}

// ... same for q3, q4, q5, q6, q7, q8, q9
```

---

## Example Data to Send to Backend

```json
{
    "selectedChapters": ["ch_01", "ch_02"],
    
    "marksAllocation": {
        "ch_01": 8,
        "ch_02": 12
    },
    
    "questionPaper": {
        "q1": {
            "chapter": "ch_01",
            "domain": "R/U",
            "images": [{id: "img_001", name: "plant.png", url: "..."}]
        },
        "q2": {
            "chapter": "ch_01",
            "domain": "R/U",
            "images": []
        },
        "q3": {
            "chapter": "ch_02",
            "domain": "R/U",
            "images": [{id: "img_002", name: "acid.png", url: "..."}]
        },
        "q4": {"chapter": "ch_01", "domain": "R/U", "images": []},
        "q5": {"chapter": "ch_02", "domain": "An/E", "images": []},
        "q6": {"chapter": "ch_01", "domain": "R/U", "images": []},
        "q7": {"chapter": "ch_01", "domain": "Ap", "images": []},
        "q8": {"chapter": "ch_02", "domain": "An/E", "images": []},
        "q9": {"chapter": "ch_01", "domain": "An/E", "images": []}
    }
}
```

---

## What Each Question Field Means

| Field | Possible Values | Example |
|-------|-----------------|---------|
| `chapter` | ch_01, ch_02, ch_03, ... | "ch_01" (Nutrition in Plants) |
| `domain` | R/U, Ap, An/E | "R/U" = Remember/Understand |
| `images` | [] or [{id, name, url}] | [] if no diagram, or [diagram] if selected |

---

## Domain/Type Meanings

```
R/U   = Remember / Understand (basic knowledge)
Ap    = Apply (use knowledge)
An/E  = Analyze / Evaluate (higher order thinking)
```

---

## That's It!

Just these 3 things:
1. ✅ Which chapters selected
2. ✅ How many marks for each
3. ✅ For each question: chapter + domain + images

**Everything else (exam type, grade, subject) is already being saved elsewhere.**

---

## Backend: What to Do

1. **Receive** this data from frontend (POST or PATCH)
2. **Store** in DynamoDB under the draftId
3. **Return** when frontend requests it (GET)
4. **Delete** when user requests (DELETE)

That's all!
