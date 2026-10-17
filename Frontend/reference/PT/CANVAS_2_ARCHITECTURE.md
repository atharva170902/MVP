# Canvas 2 Assessment Architecture
## Based on Podar International School Periodic Test Structure

---

## 1. ASSESSMENT CONTAINER HIERARCHY

### Level 0: Assessment Master Record
```
Assessment {
  id: "PT1-CB-VII-Science"
  title: "Periodic Test 1 - Nutrition"
  institution: "Podar International School"
  code: "CB/VII/2425"
  subject: "Science"
  standard: "VII"
  duration_minutes: 60
  total_marks: 20
  exam_date: "2024-12-XX"
  time_slot: "9:00 AM - 10:00 AM"
  
  linked_resources: {
    chapters: ["Nutrition in Plants", "Nutrition in Animals"],
    curriculum_map: "CB-VII-Science-CH01-CH02",
    marking_scheme: "PT1-MS.pdf"
  }
  
  sections: [Section_A, Section_B, Section_C, Section_D, Section_E]
}
```

### Level 1: Section Container
```
Section {
  section_code: "A"
  section_name: "Multiple Choice Questions"
  order: 1
  marks_total: 4
  marks_weightage: 20%
  
  section_properties: {
    question_type: "Objective",
    marks_per_question: 1,
    total_questions: 4,
    answer_format: "single_selection",
    scoring_type: "auto"
  }
  
  instructions: {
    student_facing: "Select and write the most appropriate option...",
    answering_time_estimate: "8 minutes",
    special_rules: "Q4 is Assertion-Reason format"
  }
  
  questions: [Question_1, Question_2, Question_3, Question_4]
}
```

### Level 2: Question Record
```
Question {
  q_id: 1
  section: "A"
  question_number: 1
  marks: 1
  
  metadata: {
    chapter: 1,
    learning_domain: "R/U",
    difficulty_level: "Basic",
    content_tags: ["plant_nutrition", "adaptations"],
    blooms_level: "Remember"
  }
  
  question_content: {
    type: "mcq",
    stem: "Which of the following plants have numerous tentacles...",
    image: "url_to_sundew_plant.jpg",
    image_credit: "© Educational Images"
  }
  
  options: [
    {label: "(a)", text: "Pitcher plant", is_correct: false},
    {label: "(b)", text: "Cuscuta", is_correct: false},
    {label: "(c)", text: "Venus flytrap", is_correct: false},
    {label: "(d)", text: "Sundew plant", is_correct: true}
  ],
  
  answer_key: {
    correct_option: "(d)",
    explanation: "Sundew plants have tentacles with sticky drops...",
    marks_full: 1,
    marks_partial: 0,
    marks_incorrect: 0
  }
}
```

### Level 2 (Variant): Question - Assertion-Reason
```
Question {
  q_id: 4
  section: "A"
  question_number: 4
  marks: 1
  question_type: "assertion_reason"
  
  question_content: {
    assertion: "Earthworms are detritivores.",
    reason: "Earthworms ingest dead organic matter, digest and break it down..."
  },
  
  meta_options: [
    {code: "(a)", text: "Both A and R are true, and R is the correct explanation of A"},
    {code: "(b)", text: "Both A and R are true, and R is NOT the correct explanation of A"},
    {code: "(c)", text: "A is true but R is false"},
    {code: "(d)", text: "A is false but R is true"}
  ],
  
  answer_key: {
    correct_option: "(a)",
    why_assertion_true: "Earthworms feed on dead organic matter...",
    why_reason_true: "The process involves ingestion and internal digestion...",
    why_reason_explains: "The reason correctly explains why earthworms are detritivores"
  }
}
```

### Level 2 (Variant): Question - Very Short Answer
```
Question {
  q_id: 5
  section: "B"
  question_number: 5
  marks: 2
  question_type: "vsa"
  
  question_content: {
    main_stem: "The mucous lining of the small intestine has millions of finger-like projections.",
    sub_questions: [
      {
        label: "(a)",
        text: "What are these finger-like projections called?"
      },
      {
        label: "(b)",
        text: "Mention its main function."
      }
    ]
  },
  
  answer_requirements: {
    word_limit: {min: 30, max: 50},
    format: "text",
    sub_part_count: 2
  },
  
  answer_key: {
    model_answer_a: "Villi (singular: villus)",
    model_answer_b: "Absorption of digested food/nutrients",
    marks_rubric: {
      marks_2: "Both parts correct and complete",
      marks_1: "One part correct or both partially correct",
      marks_0: "Both incorrect or no answer"
    }
  }
}
```

### Level 2 (Variant): Question - Short Answer with Diagram
```
Question {
  q_id: 7
  section: "C"
  question_number: 7
  marks: 3
  question_type: "sa_with_diagram"
  
  question_content: {
    main_stem: "The given picture is of an amoeba.",
    image: "amoeba_labeled.jpg",
    image_labels: ["A", "B", "C", "D"],
    sub_questions: [
      {
        label: "(a)",
        text: "Which labelled part helps in the excretion of undigested food?"
      },
      {
        label: "(b)",
        text: "Identify the labelled part that contains hydrolytic enzymes."
      },
      {
        label: "(c)",
        text: "Which labelled part changes its shape to form finger-like projections?"
      }
    ]
  },
  
  answer_requirements: {
    word_limit: {min: 50, max: 80},
    format: "text_with_labels",
    requires_diagram_reference: true
  },
  
  answer_key: {
    model_answer_a: "A (Anal pore/Cytopore)",
    model_answer_b: "B (Food vacuole)",
    model_answer_c: "C (Pseudopodia)",
    marks_rubric: {
      marks_3: "All three parts correct with brief explanation",
      marks_2: "Two parts correct",
      marks_1: "One part correct",
      marks_0: "No correct answer"
    }
  }
}
```

### Level 2 (Variant): Question - Long Answer
```
Question {
  q_id: 8
  section: "D"
  question_number: 8
  marks: 5
  question_type: "long_answer"
  
  question_content: {
    opening_stem: "Green plants make their food from carbon dioxide and water in the presence of chlorophyll by using light energy from the Sun.",
    sub_questions: [
      {
        label: "(a)",
        text: "What is this process called? Write the end products of this process."
      },
      {
        label: "(b)",
        text: "How is carbon dioxide taken up by plants from the atmosphere for this process?"
      },
      {
        label: "(c)",
        text: "Name the mode of nutrition in green plants."
      }
    ]
  },
  
  answer_requirements: {
    word_limit: {min: 80, max: 120},
    format: "extended_text",
    structure_guidance: "Should cover all three sub-parts in comprehensive manner"
  },
  
  answer_key: {
    model_answer_a: "Photosynthesis. End products: Glucose and Oxygen",
    model_answer_b: "Through stomata (pores) on leaves",
    model_answer_c: "Autotrophic (autotrophy)",
    detailed_explanation: "Full explanation with chemical equation...",
    marks_rubric: {
      marks_5: "Comprehensive, accurate, all parts covered (80-120 words)",
      marks_4: "Most parts correct, minor gaps",
      marks_3: "Basic understanding, some incomplete parts",
      marks_2: "Partial understanding, significant gaps",
      marks_1: "Minimal understanding",
      marks_0: "No response or completely incorrect"
    }
  }
}
```

### Level 2 (Variant): Question - Case-Based
```
Question {
  q_id: 9
  section: "E"
  question_number: 9
  marks: 4
  question_type: "case_based"
  
  question_content: {
    scenario_title: "Quiz Hints - Body Parts Identification",
    case_table: {
      serial_i: "A human tooth is made up of a bone-like hard structure called 'X'.",
      serial_ii: "Structure 'X' is covered with a hard, shiny covering known as 'Y', which is the hardest substance in our body.",
      serial_iii: "A sticky yellowish layer of 'Z' forms on our teeth due to poor oral hygiene and produce acids.",
      serial_iv: "These acids corrode structure 'Y' and may cause tooth decay and cavities."
    },
    sub_questions: [
      {
        label: "(a)",
        text: "Name structures 'X' and 'Y'."
      },
      {
        label: "(b)",
        text: "Identify 'Z'. How does it form on our teeth?"
      }
    ]
  },
  
  answer_requirements: {
    format: "text_identifications_plus_explanations",
    case_comprehension_required: true
  },
  
  answer_key: {
    x_identification: "Dentin",
    y_identification: "Enamel",
    z_identification: "Plaque",
    z_formation: "Forms due to accumulation of bacteria and food particles due to poor oral hygiene",
    marks_rubric: {
      marks_4: "All three identifications correct + proper explanation",
      marks_3: "All identifications correct, explanation incomplete",
      marks_2: "Two identifications correct",
      marks_1: "One identification correct",
      marks_0: "No correct identifications"
    }
  }
}
```

---

## 2. STUDENT INTERFACE FLOW

### Stage 1: Pre-Assessment (Instruction Screen)
```
┌─────────────────────────────────────────────┐
│  PERIODIC TEST 1 - SCIENCE VII              │
│  CB/VII/2425                                │
│  Duration: 1 Hour | Total Marks: 20        │
├─────────────────────────────────────────────┤
│                                             │
│  GENERAL INSTRUCTIONS:                      │
│  • 9 compulsory questions                  │
│  • 5 sections (A, B, C, D, E)              │
│  • No overall choice                       │
│  • Marks: A(4) B(4) C(3) D(5) E(4)        │
│                                             │
│  Section A: MCQ - 4 questions (1 mark each)│
│  Section B: VSA - 2 questions (2 marks)    │
│  Section C: SA - 1 question (3 marks)      │
│  Section D: LA - 1 question (5 marks)      │
│  Section E: Case-Based - 1 question (4m)   │
│                                             │
│           [START ASSESSMENT →]              │
└─────────────────────────────────────────────┘
```

### Stage 2: Section A (MCQ Auto-scoring)
```
┌──────────────────────────────────────────────────────┐
│ Question 1/4 | Section A - MCQ      [Timer: 52:30]   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Which of the following plants have numerous        │
│ tentacles with drops of sticky substance at        │
│ their ends?                         [1 mark]       │
│                                                      │
│ [Sundew Plant Image]                                │
│                                                      │
│ ○ (a) Pitcher plant                                │
│ ○ (b) Cuscuta                                      │
│ ○ (c) Venus flytrap                                │
│ ◉ (d) Sundew plant          [SELECTED]             │
│                                                      │
│ [← Previous] [Submit Q] [Next →]                   │
│ Progress: ████░░░ (Q1-4 Complete)                 │
└──────────────────────────────────────────────────────┘

[After Selection]
└──────────────────────────────────────────────────────┐
│ ✓ CORRECT! [1/1 marks]                             │
│ Explanation: Sundew plants have tentacles with     │
│ sticky drops to trap insects...                     │
│ [Next Question →]                                  │
└──────────────────────────────────────────────────────┘
```

### Stage 3: Section B (VSA Manual Grading)
```
┌──────────────────────────────────────────────────────┐
│ Question 5/9 | Section B - VSA      [Timer: 42:15]   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ The mucous lining of the small intestine has      │
│ millions of finger-like projections.    [2 marks]  │
│                                                      │
│ (a) What are these finger-like projections        │
│     called?                                        │
│ ┌──────────────────────────────────────────────┐  │
│ │ villi                                         │  │
│ │ (Word count: 1/50)                           │  │
│ └──────────────────────────────────────────────┘  │
│                                                      │
│ (b) Mention its main function.                     │
│ ┌──────────────────────────────────────────────┐  │
│ │ absorption of digested nutrients             │  │
│ │ (Word count: 4/50)                           │  │
│ └──────────────────────────────────────────────┘  │
│                                                      │
│ [← Back] [Save Draft] [Next →]                     │
│ Status: AUTO-SAVED                                 │
└──────────────────────────────────────────────────────┘
```

### Stage 4: Section C (SA with Diagram)
```
┌──────────────────────────────────────────────────────┐
│ Question 7/9 | Section C - SA      [Timer: 28:42]    │
├──────────────────────────────────────────────────────┤
│                                                      │
│ The given picture is of an amoeba.    [3 marks]    │
│                                                      │
│ ┌──────────────────────────────────────────────┐   │
│ │           [AMOEBA DIAGRAM]                  │   │
│ │      with labels: A, B, C, D                │   │
│ │      (Anal pore, Food vacuole,             │   │
│ │       Pseudopodia, Nucleus)                │   │
│ └──────────────────────────────────────────────┘   │
│                                                      │
│ (a) Which labelled part helps in the excretion   │
│     of undigested food?                           │
│ ┌──────────────────────────────────────────────┐  │
│ │ A (Anal pore)                               │  │
│ │ (Word count: 2/80)                          │  │
│ └──────────────────────────────────────────────┘  │
│                                                      │
│ [Show remaining sub-parts] [← Back] [Next →]       │
│ (Word counter: 0-80 words required)                │
└──────────────────────────────────────────────────────┘
```

### Stage 5: Section D (Long Answer)
```
┌──────────────────────────────────────────────────────┐
│ Question 8/9 | Section D - LA       [Timer: 15:30]   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Green plants make their food from carbon         │
│ dioxide and water in the presence of chlorophyll...  │
│                                                  [5 marks]│
│                                                      │
│ (a) What is this process called? Write the end  │
│     products of this process.                    │
│ (b) How is carbon dioxide taken up by plants    │
│     from the atmosphere for this process?        │
│ (c) Name the mode of nutrition in green plants.   │
│                                                      │
│ ┌──────────────────────────────────────────────┐  │
│ │ The process is called photosynthesis...     │  │
│ │ It takes place in the chloroplasts...       │  │
│ │ Carbon dioxide enters through stomata...    │  │
│ │                                             │  │
│ │ (Word count: 45/120)                        │  │
│ └──────────────────────────────────────────────┘  │
│                                                      │
│ STRUCTURE GUIDE:                                    │
│ • Define process (part a)                          │
│ • Explain CO2 uptake (part b)                      │
│ • State nutrition mode (part c)                    │
│                                                      │
│ [← Back] [Save Draft] [Next →]                     │
└──────────────────────────────────────────────────────┘
```

### Stage 6: Section E (Case-Based)
```
┌──────────────────────────────────────────────────────┐
│ Question 9/9 | Section E - Case-Based [Timer: 05:30] │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Read the case carefully:              [4 marks]    │
│                                                      │
│ QUIZ HINTS TABLE:                                   │
│ ┌─────────────────────────────────────────────────┐│
│ │ (i)   A human tooth is made up of a bone-like  ││
│ │       hard structure called 'X'.               ││
│ │                                               ││
│ │ (ii)  Structure 'X' is covered with a hard,   ││
│ │       shiny covering known as 'Y', which is   ││
│ │       the hardest substance in our body.      ││
│ │                                               ││
│ │ (iii) A sticky yellowish layer of 'Z' forms   ││
│ │       on our teeth due to poor oral hygiene.. ││
│ │                                               ││
│ │ (iv)  These acids corrode structure 'Y' and   ││
│ │       may cause tooth decay and cavities.     ││
│ └─────────────────────────────────────────────────┘│
│                                                      │
│ Based on the above hints, answer:                  │
│                                                      │
│ (a) Name structures 'X' and 'Y'.                   │
│ ┌──────────────────────────────────────────────┐  │
│ │ X = Dentin, Y = Enamel                      │  │
│ └──────────────────────────────────────────────┘  │
│                                                      │
│ (b) Identify 'Z'. How does it form on our teeth?  │
│ ┌──────────────────────────────────────────────┐  │
│ │ Z is plaque, which forms from accumulation  │  │
│ │ of bacteria and food particles...            │  │
│ └──────────────────────────────────────────────┘  │
│                                                      │
│ [← Back] [Review All] [SUBMIT ASSESSMENT]          │
└──────────────────────────────────────────────────────┘
```

### Stage 7: Review Before Submit
```
┌────────────────────────────────────────────────────────┐
│           REVIEW YOUR ANSWERS                          │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Section A - MCQ (Auto-scored)                         │
│ ✓ Q1: (d) [1/1] ✓ Q2: (d) [1/1] ✓ Q3: (b) [1/1]    │
│ ✓ Q4: (a) [1/1]                       Total: 4/4      │
│                                                        │
│ Section B - VSA (Pending Manual Grading)              │
│ • Q5: (a) villi (b) absorption...        Submitted    │
│ • Q6: Haustoria justification...         Submitted    │
│                                                        │
│ Section C - SA (Pending Manual Grading)               │
│ • Q7: Amoeba identification...           Submitted    │
│                                                        │
│ Section D - LA (Pending Manual Grading)               │
│ • Q8: Photosynthesis explanation...      Submitted    │
│                                                        │
│ Section E - Case-Based (Pending Manual Grading)       │
│ • Q9: Tooth structure identification...  Submitted    │
│                                                        │
│ SUMMARY: 9/9 questions answered                       │
│ AUTO-MARKED: 4/4 marks (Section A)                    │
│ PENDING: 16 marks (Sections B-E) → Teacher Review    │
│                                                        │
│      [← Edit Answers] [FINAL SUBMIT →]                │
└────────────────────────────────────────────────────────┘
```

---

## 3. TEACHER GRADING INTERFACE

### Teacher Dashboard - Pending Submissions
```
┌─────────────────────────────────────────────────────────┐
│ PERIODIC TEST 1 - GRADING QUEUE                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Pending Submissions: 45 students                       │
│ Graded: 12 | Pending: 33                             │
│                                                         │
│ STUDENT LIST:                                          │
│ ┌───┬─────────────┬─────────┬──────────┬────────────┐ │
│ │ # │ Name        │ Std     │ Paper    │ Auto-Score│ │
│ ├───┼─────────────┼─────────┼──────────┼────────────┤ │
│ │ 1 │ Aarjav      │ VII-A   │ QP-A     │ 4/4 ✓    │ │
│ │ 2 │ Aditi       │ VII-A   │ QP-B     │ 4/4 ✓    │ │
│ │ 3 │ Akshara     │ VII-A   │ QP-C     │ 3/4 ✗    │ │
│ │ 4 │ Anika       │ VII-A   │ QP-D     │ 4/4 ✓    │ │
│ ...                                                   │
│ │45 │ Yash        │ VII-B   │ QP-A     │ 2/4 ✗    │ │
│ └───┴─────────────┴─────────┴──────────┴────────────┘ │
│                                                         │
│ Filter: [All] [Graded] [Pending] [Need Review]        │
│ Sort by: [Name] [Auto-Score] [Date Submitted]         │
│                                                         │
│ [Select student →]                                     │
└─────────────────────────────────────────────────────────┘
```

### Teacher Grading Screen - Single Student
```
┌──────────────────────────────────────────────────────────┐
│ GRADING: Aarjav Singh | VII-A | QP-A                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ SECTION A - AUTO SCORED: 4/4 ✓                          │
│ Q1 ✓ (d) | Q2 ✓ (d) | Q3 ✓ (b) | Q4 ✓ (a)            │
│                                                          │
│ ─────────────────────────────────────────────────────── │
│                                                          │
│ SECTION B - Q5 (2 marks) - MANUAL GRADING              │
│                                                          │
│ Question:                                              │
│ The mucous lining of the small intestine has          │
│ millions of finger-like projections.                  │
│                                                          │
│ Student Response:                                       │
│ (a) These are called villi. They help in             │
│     absorption of nutrients from digested food.      │
│                                                          │
│ (b) The main function is to increase the surface    │
│     area for absorption of nutrients.                │
│                                                          │
│ Assessment:                                            │
│ Model Answer:                                          │
│ (a) Villi                                             │
│ (b) Absorption of digested nutrients                 │
│                                                          │
│ SCORING RUBRIC:                                        │
│ ┌────────────────────────────────────────────────┐   │
│ │ ◉ 2/2 Both parts correct and complete         │   │
│ │ ○ 1/2 One part correct or incomplete          │   │
│ │ ○ 0/2 Both incorrect or no answer             │   │
│ └────────────────────────────────────────────────┘   │
│                                                          │
│ Teacher Feedback:                                      │
│ ┌────────────────────────────────────────────────┐   │
│ │ Excellent answer. Correctly identified villi  │   │
│ │ and explained both structure and function.    │   │
│ │ Well explained within word limit.             │   │
│ └────────────────────────────────────────────────┘   │
│                                                          │
│ [Save] [Next Student] [Print Marked Answer]           │
│ Progress: Q5(2/2) Q6(?) Q7(?) Q8(?) Q9(?)            │
└──────────────────────────────────────────────────────────┘
```

### Grading Summary View
```
┌─────────────────────────────────────────────────────────┐
│ FINAL MARKS CALCULATION                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Student: Aarjav Singh                                  │
│ Standard: VII-A | Question Paper: A                   │
│                                                         │
│ SECTION-WISE BREAKDOWN:                               │
│                                                         │
│ Section A (MCQ)              4/4  [Auto-scored]       │
│ Section B (VSA)              4/4  [Teacher Graded]    │
│ Section C (SA)               3/3  [Teacher Graded]    │
│ Section D (LA)               5/5  [Teacher Graded]    │
│ Section E (Case-Based)       4/4  [Teacher Graded]    │
│                                                         │
│ ════════════════════════════════════════════════════  │
│ TOTAL MARKS OBTAINED:       20/20 ★★★★★              │
│ ════════════════════════════════════════════════════  │
│                                                         │
│ PERFORMANCE ANALYSIS:                                  │
│ • Attempted all questions: ✓                          │
│ • Auto-score: Perfect 4/4                            │
│ • Manual grading: Excellent across all sections       │
│ • Word count compliance: All sections within limits   │
│ • Response quality: Comprehensive and accurate        │
│                                                         │
│ RECOMMENDATION:                                        │
│ ✓ Outstanding performance                             │
│                                                         │
│ [Save Final Marks] [Print Report] [Export Result]     │
└─────────────────────────────────────────────────────────┘
```

---

## 4. RESULT GENERATION & ANALYTICS

### Individual Result Report
```
┌────────────────────────────────────────────────────────┐
│     PODAR INTERNATIONAL SCHOOL                         │
│     PERIODIC TEST 1 - RESULT REPORT                    │
│     Academic Year 2024-25                              │
│────────────────────────────────────────────────────────┤
│                                                        │
│ Student Name: Aarjav Singh                            │
│ Roll No: 07-A-01 | Standard: VII-A                    │
│ Subject: Science | Date: 15-12-2024                   │
│ Question Paper: A (CB/VII/2425)                       │
│                                                        │
│────────────────────────────────────────────────────────│
│ MARKS DISTRIBUTION:                                   │
│                                                        │
│ Section A: MCQ (Objective)          4/4  ┃ 20%      │
│ Section B: Very Short Answer        4/4  ┃ 20%      │
│ Section C: Short Answer             3/3  ┃ 15%      │
│ Section D: Long Answer              5/5  ┃ 25%      │
│ Section E: Case-Based               4/4  ┃ 20%      │
│                                                        │
│ TOTAL MARKS OBTAINED:              20/20 ┃ 100%     │
│                                                        │
│────────────────────────────────────────────────────────│
│ PERFORMANCE METRICS:                                   │
│                                                        │
│ Percentage:           100%   [Outstanding]            │
│ Grade:                A+                              │
│ Class Rank:           1/45 students                   │
│ Class Average:        65%                             │
│                                                        │
│────────────────────────────────────────────────────────│
│ STRENGTHS:                                             │
│ ✓ Perfect conceptual understanding                    │
│ ✓ Excellent application of knowledge                 │
│ ✓ Well-organized long answers                        │
│ ✓ Strong case-based reasoning                        │
│                                                        │
│ AREAS FOR IMPROVEMENT:                                │
│ (None observed)                                        │
│                                                        │
│────────────────────────────────────────────────────────│
│ Teacher Signature: _____________  Date: 15-12-2024   │
│ Principal Signature: ___________                      │
└────────────────────────────────────────────────────────┘
```

### Class Performance Analytics
```
┌──────────────────────────────────────────────────────┐
│ CLASS ANALYTICS - PERIODIC TEST 1                    │
│ Standard VII-A | Total Students: 45                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│ MARKS DISTRIBUTION (Histogram):                     │
│                                                      │
│ 20 │                          ▓                     │
│ 18 │                    ▓     ▓                     │
│ 16 │              ▓     ▓     ▓      ▓              │
│ 14 │        ▓     ▓     ▓     ▓      ▓     ▓        │
│ 12 │  ▓     ▓     ▓     ▓     ▓      ▓     ▓   ▓    │
│ 10 │  ▓     ▓     ▓     ▓     ▓      ▓     ▓   ▓    │
│  8 │  ▓     ▓     ▓     ▓     ▓      ▓     ▓   ▓    │
│  6 │  ▓     ▓     ▓     ▓     ▓      ▓     ▓   ▓    │
│  4 │  ▓     ▓     ▓     ▓     ▓      ▓     ▓   ▓    │
│  2 │  ▓     ▓     ▓     ▓     ▓      ▓     ▓   ▓    │
│    └──┴─────┴─────┴─────┴─────┴──────┴─────┴───┴──  │
│      0-4   5-8   9-12  13-16  17-19  20      Avg    │
│
│ GRADE DISTRIBUTION:                                  │
│ A+  (18-20):  5 students (11%)                      │
│ A   (17-17):  8 students (18%)                      │
│ B+  (15-16):  12 students (27%)                     │
│ B   (13-14):  15 students (33%)                     │
│ C+  (11-12):  4 students (9%)                       │
│ C   (9-10):   1 student (2%)                        │
│                                                      │
│ CLASS STATISTICS:                                    │
│ Average Score: 13.8/20 (69%)                        │
│ Highest Score: 20/20 (100%)                         │
│ Lowest Score: 9/20 (45%)                            │
│ Standard Dev: 3.2                                    │
│                                                      │
│ SECTION-WISE CLASS PERFORMANCE:                      │
│ Section A: 3.8/4 (95%) - Excellent                  │
│ Section B: 2.9/4 (72%) - Good                       │
│ Section C: 2.2/3 (73%) - Good                       │
│ Section D: 3.4/5 (68%) - Fair                       │
│ Section E: 2.8/4 (70%) - Good                       │
│                                                      │
│ QUESTION-WISE DIFFICULTY INDEX:                      │
│ Q1 (Plant adaptation): 96% - Very Easy              │
│ Q2 (Lichen symbiosis): 89% - Easy                   │
│ Q3 (Digestion): 82% - Medium                        │
│ Q4 (Assertion-Reason): 64% - Difficult              │
│ Q5 (Villi): 71% - Medium                            │
│ Q6 (Haustoria): 68% - Medium                        │
│ Q7 (Amoeba): 73% - Medium                           │
│ Q8 (Photosynthesis): 68% - Medium                   │
│ Q9 (Tooth structure): 70% - Medium                  │
│                                                      │
│ LEARNING DOMAIN PERFORMANCE:                         │
│ Remember/Understand: 95% [R/U = 40% of exam]       │
│ Application: 72% [Ap = 40% of exam]                │
│ Analysis/Evaluation: 64% [An/E = 20% of exam]      │
│                                                      │
│ KEY OBSERVATIONS:                                    │
│ • Class strong in recall & MCQ                       │
│ • Struggles with analysis-level questions           │
│ • Q4 Assertion-Reason needs more practice           │
│ • Long answer explanations need improvement         │
│                                                      │
│ RECOMMENDATIONS:                                     │
│ • Focus on application-level thinking               │
│ • Practice assertion-reason format                   │
│ • Improve word-limited answer structure             │
│ • Use case studies for analysis training            │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 5. DATA PERSISTENCE & API STRUCTURE

### Assessment Storage Schema
```
ASSESSMENTS
├── id (primary key)
├── title
├── code (CB/VII/2425)
├── total_marks
├── duration_minutes
└── created_at

SECTIONS
├── id (primary key)
├── assessment_id (foreign key)
├── section_code (A-E)
├── marks_total
├── order
└── section_type

QUESTIONS
├── id (primary key)
├── section_id (foreign key)
├── question_number
├── question_type (MCQ, VSA, SA, LA, CBA)
├── marks
├── question_stem
├── image_urls[] (optional)
├── content_json (full question structure)
├── learning_domain (R/U, Ap, An/E)
├── chapter_id (1, 2)
└── answer_key_json

ANSWER_OPTIONS (for MCQ)
├── id (primary key)
├── question_id (foreign key)
├── option_label (a, b, c, d)
├── option_text
├── is_correct_answer
└── explanation

STUDENT_SUBMISSIONS
├── id (primary key)
├── assessment_id (foreign key)
├── student_id (foreign key)
├── paper_variant (A, B, C, D)
├── submission_timestamp
├── time_taken_seconds
└── submission_status (submitted, draft)

STUDENT_RESPONSES
├── id (primary key)
├── submission_id (foreign key)
├── question_id (foreign key)
├── response_text
├── response_option (for MCQ)
├── response_images[] (optional)
└── response_timestamp

STUDENT_MARKS
├── id (primary key)
├── submission_id (foreign key)
├── question_id (foreign key)
├── marks_obtained
├── marks_total
├── grader_id (for manual grading)
├── grading_timestamp
├── rubric_level_applied (full/partial/zero)
├── teacher_feedback
└── auto_scored (true/false)

GRADING_RUBRICS
├── id (primary key)
├── question_id (foreign key)
├── rubric_level (0, 1, 2, 3, 4, 5)
├── marks
├── criteria_description
└── example_response
```

### API Endpoints
```
GET  /api/assessments/{assessment_id}
GET  /api/assessments/{assessment_id}/sections
GET  /api/assessments/{assessment_id}/sections/{section_code}/questions
GET  /api/questions/{question_id}
GET  /api/questions/{question_id}/answer_key

POST /api/submissions
POST /api/submissions/{submission_id}/responses
GET  /api/submissions/{submission_id}
GET  /api/submissions/{submission_id}/status

POST /api/submissions/{submission_id}/grade
GET  /api/submissions/{submission_id}/marks
GET  /api/students/{student_id}/assessment_results

GET  /api/analytics/class/{class_id}/performance
GET  /api/analytics/assessment/{assessment_id}/statistics
```

---

## 6. IMPLEMENTATION ROADMAP

### Phase 1: Core Assessment Engine
- [ ] Database schema setup
- [ ] Question & Section data models
- [ ] Student submission mechanism
- [ ] Auto-scoring for MCQ (Section A)

### Phase 2: Grading Infrastructure
- [ ] Rubric template system
- [ ] Teacher grading interface
- [ ] Manual mark entry & validation
- [ ] Marks compilation logic

### Phase 3: Student Interface
- [ ] Assessment display components
- [ ] Response capture for all question types
- [ ] Word count validators
- [ ] Draft save mechanism
- [ ] Timer & navigation

### Phase 4: Reporting & Analytics
- [ ] Individual result generation
- [ ] Class performance analytics
- [ ] Question-wise difficulty analysis
- [ ] PDF report generation

### Phase 5: Advanced Features
- [ ] Answer key comparison
- [ ] Performance insights
- [ ] Comparative analytics
- [ ] Mobile responsiveness

