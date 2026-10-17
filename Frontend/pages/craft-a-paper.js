import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';

import { withAuth } from '../lib/withAuth';
import { getGrades, getSubjects, getChapters, getDiagrams, listDrafts, getDraft, isBackendRunning, createDraft, updateDraft, deleteDraft, startGeneration, getGenerationStatus } from '../lib/api';
import { useAutoSave } from '../lib/useAutoSave';
import { loadDraftForResume, clearLocalDraft, writeLocalDraft, readLocalDraft } from '../lib/draftService';
import { useSessionManagement } from '../lib/useSessionManagement';
import { timeAgo } from '../lib/formatTime';

export const getServerSideProps = withAuth(async () => {
  return { props: {} };
});

// How often (ms) step-3 polls the generation job snapshot.
const GEN_POLL_MS = 2500;

// Save Status Indicator Component
function SaveIndicator({ status }) {
  if (status === 'idle') return null;

  const config = {
    saving: { text: 'Savingâ€¦', className: 'text-gray-500' },
    saved: { text: 'Draft saved', className: 'text-green-600' },
    error: { text: 'Not saved â€” will retry', className: 'text-red-600' },
  }[status];

  if (!config) return null;

  return (
    <span className={`flex items-center gap-1.5 text-xs font-medium ${config.className}`}>
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          status === 'saving'
            ? 'bg-gray-400 animate-pulse'
            : status === 'saved'
            ? 'bg-green-500'
            : 'bg-red-500'
        }`}
      />
      {config.text}
    </span>
  );
}

// Canvas 2 = AI Assistance: renders the live generation snapshot (per-section
// progress, 5 questions per slot as they arrive, and running/total tokens).
const SECTION_ORDER = ['A', 'B', 'C', 'D', 'E'];

// Section-scoped drag-and-drop model for assembling the central Question Paper.
// These are the fixed q1..q9 -> section mappings (confirmed from buildQuestionPaperData).
const SECTION_SLOTS = { A: ['q1', 'q2', 'q3', 'q4'], B: ['q5', 'q6'], C: ['q7'], D: ['q8'], E: ['q9'] };
const SLOT_SECTION = { q1: 'A', q2: 'A', q3: 'A', q4: 'A', q5: 'B', q6: 'B', q7: 'C', q8: 'D', q9: 'E' };
const SLOT_MARKS = { q1: 1, q2: 1, q3: 1, q4: 1, q5: 2, q6: 2, q7: 3, q8: 5, q9: 4 };
const SLOT_NUMBER = { q1: 1, q2: 2, q3: 3, q4: 4, q5: 5, q6: 6, q7: 7, q8: 8, q9: 9 };

// Per-section exam-paper copy (header title + sub-line), reused in palette and canvas.
const SECTION_META = {
  A: { title: 'Multiple Choice Questions', note: '4 Questions Ã— 1 Mark = 4 Marks (Objective Type)' },
  B: { title: 'Very Short Answer', note: '2 Questions Ã— 2 Marks = 4 Marks (30-50 words)' },
  C: { title: 'Short Answer', note: '1 Question Ã— 3 Marks = 3 Marks (50-80 words)' },
  D: { title: 'Long Answer', note: '1 Question Ã— 5 Marks = 5 Marks (80-120 words, 3 sub-parts)' },
  E: { title: 'Case-Based Assessment', note: '1 Question Ã— 4 Marks = 4 Marks (Table with hints + sub-questions)' },
};

// Drag payload key â€” native HTML5 DnD, same pattern as the diagram drag in this file.
const QP_SLOT_MIME = 'application/x-qp-slot';

// One reusable per-slot editor card. Renders identically to the old inline Qn. row
// (chapter select, domain select, marks label, diagram drop zone + thumbnails) and is
// draggable so it can move between the section palette and the central paper.
function QuestionSlotCard({
  slot,
  placed,
  chapterValue,
  domainValue,
  images,
  chapterOptions,
  onDragStartCard,
  onDragEndCard,
  onChapterChange,
  onDomainChange,
  onDropDiagram,
  onDragOverDiagram,
  onDragLeaveDiagram,
  onRemoveImage,
  onRemovePlacement,
}) {
  const marks = SLOT_MARKS[slot];
  return (
    <div
      draggable
      onDragStart={(e) => onDragStartCard(e, slot)}
      onDragEnd={onDragEndCard}
      onDragOver={onDragOverDiagram}
      onDragLeave={onDragLeaveDiagram}
      onDrop={(e) => onDropDiagram(e, slot)}
      className={`flex gap-3 rounded-lg border border-gray-200 bg-white p-3 cursor-move transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-400 hover:shadow-md ${
        placed ? 'qp-card-in' : ''
      }`}
    >
      <span className="min-w-fit select-none font-semibold text-gray-900">Q{SLOT_NUMBER[slot]}.</span>
      <div className="flex-1">
        <select
          value={chapterValue}
          onChange={(e) => onChapterChange(slot, e.target.value)}
          onDragStart={(e) => e.stopPropagation()}
          className="w-full rounded border border-gray-300 px-2 py-1 text-sm transition focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select Chapter</option>
          {chapterOptions}
        </select>
        <select
          value={domainValue}
          onChange={(e) => onDomainChange(slot, e.target.value)}
          onDragStart={(e) => e.stopPropagation()}
          className="mt-1 rounded border border-gray-300 px-2 py-1 text-xs transition focus:ring-2 focus:ring-blue-500"
        >
          <option>R/U</option>
          <option>Ap</option>
          <option>An/E</option>
        </select>
        <span className="ml-2 text-xs text-gray-600">
          [{marks} mark{marks === 1 ? '' : 's'}]
        </span>
        <div className="mt-2 flex flex-wrap gap-2">
          {images?.map((img, idx) => (
            <div key={idx} className="group relative">
              <img
                src={img.url}
                alt={img.name}
                className="h-16 w-16 rounded border border-gray-300 object-cover"
              />
              <button
                onClick={() => onRemoveImage(slot, idx)}
                className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white opacity-0 transition hover:bg-red-600 group-hover:opacity-100"
              >
                Ã—
              </button>
            </div>
          ))}
        </div>
      </div>
      {placed && (
        <button
          onClick={() => onRemovePlacement(slot)}
          title="Remove from paper"
          className="h-6 w-6 shrink-0 self-start rounded-full bg-gray-200 text-sm font-bold text-gray-600 transition hover:bg-red-100 hover:text-red-600"
        >
          Ã—
        </button>
      )}
    </div>
  );
}

function TokenUsage({ tokenUsage }) {
  if (!tokenUsage) return null;
  const byModel = tokenUsage.by_model || {};
  const modelKeys = Object.keys(byModel);
  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">
      <p className="font-semibold text-gray-900">
        Tokens used: {Number(tokenUsage.total_tokens || 0).toLocaleString()}
      </p>
      <p className="text-gray-500">
        input {Number(tokenUsage.input_tokens || 0).toLocaleString()} Â· output{' '}
        {Number(tokenUsage.output_tokens || 0).toLocaleString()}
      </p>
      {modelKeys.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {modelKeys.map((model) => (
            <li key={model} className="text-gray-600">
              {model}: {Number(byModel[model]?.total_tokens || 0).toLocaleString()} tokens
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function GeneratedQuestion({ question, index }) {
  const isMcq = Array.isArray(question.options) && question.options.length > 0;
  return (
    <div className="rounded-md border border-gray-200 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-gray-900">
          {index + 1}. {question.question_text}
        </p>
        <span className="shrink-0 rounded bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
          {question.generation_model}
        </span>
      </div>
      <p className="mt-1 text-[11px] text-gray-400">
        {question.chapter} Â· {question.domain} Â· {question.marks} mark
        {Number(question.marks) === 1 ? '' : 's'}
      </p>

      {isMcq ? (
        <div className="mt-2 space-y-1">
          <ul className="space-y-0.5 text-sm text-gray-700">
            {question.options.map((opt, i) => (
              <li key={i}>
                {String.fromCharCode(65 + i)}. {opt}
              </li>
            ))}
          </ul>
          <p className="text-xs font-semibold text-green-700">
            Correct: {question.correct_answer}
          </p>
          {question.explanation && (
            <p className="text-xs text-gray-500">{question.explanation}</p>
          )}
        </div>
      ) : (
        <div className="mt-2 space-y-1">
          {question.model_answer && (
            <p className="text-sm text-gray-700">
              <span className="font-semibold">Answer: </span>
              {question.model_answer}
            </p>
          )}
          {Array.isArray(question.marking_scheme) && question.marking_scheme.length > 0 && (
            <div className="text-xs text-gray-600">
              <p className="font-semibold">Marking scheme:</p>
              <ul className="ml-4 list-disc space-y-0.5">
                {question.marking_scheme.map((point, i) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GenerationResults({ snapshot, error }) {
  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <p className="font-semibold">Generation couldn&apos;t start</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="flex min-h-[200px] items-center justify-center py-10">
        <div className="text-center text-gray-500">
          <div className="mb-4 text-6xl">ðŸ‘ï¸</div>
          <p className="text-lg font-medium">AI Assistance</p>
          <p className="mt-2 text-sm text-gray-400">
            Click Generate Paper to start creating questions.
          </p>
        </div>
      </div>
    );
  }

  const status = snapshot.status;
  const progress = snapshot.progress || {};
  const questions = snapshot.questions || {};
  const errors = snapshot.errors || {};
  const warnings = snapshot.warnings || {};

  return (
    <div className="space-y-4">
      {/* Overall banner */}
      {status === 'generating' && (
        <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700">
          <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-blue-500" />
          Generating questionsâ€¦
        </div>
      )}
      {status === 'completed' && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm font-semibold text-green-700">
          Generation complete
        </div>
      )}
      {status === 'failed' && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <p className="font-semibold">Generation failed</p>
          {snapshot.error && <p className="mt-1">{snapshot.error}</p>}
        </div>
      )}

      {/* Per-section progress */}
      <div className="flex flex-wrap gap-2">
        {SECTION_ORDER.map((section) => {
          const p = progress[section];
          if (!p) return null;
          return (
            <span
              key={section}
              className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700"
            >
              {section}: {p.done}/{p.total}
            </span>
          );
        })}
      </div>

      {/* Questions grouped by section -> slot */}
      {SECTION_ORDER.map((section) => {
        const slots = questions[section];
        if (!slots || Object.keys(slots).length === 0) return null;
        const slotKeys = Object.keys(slots).sort();
        return (
          <div key={section} className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-900">Section {section}</h3>
            {slotKeys.map((slotKey) => (
              <div key={slotKey} className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                  {slotKey}
                </p>
                {errors[slotKey] && (
                  <p className="rounded bg-red-50 px-2 py-1 text-xs text-red-600">
                    {errors[slotKey]}
                  </p>
                )}
                {Array.isArray(warnings[slotKey]) &&
                  warnings[slotKey].map((w, i) => (
                    <p
                      key={i}
                      className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-700"
                    >
                      {w}
                    </p>
                  ))}
                {(slots[slotKey] || []).map((q, i) => (
                  <GeneratedQuestion key={i} question={q} index={i} />
                ))}
              </div>
            ))}
          </div>
        );
      })}

      {/* Per-slot errors for slots that produced no questions */}
      {Object.keys(errors)
        .filter((slotKey) => {
          // errors already shown inline above belong to sections that have questions;
          // surface any remaining slot errors here too.
          return !SECTION_ORDER.some((section) => questions[section]?.[slotKey]);
        })
        .map((slotKey) => (
          <p
            key={slotKey}
            className="rounded bg-red-50 px-2 py-1 text-xs text-red-600"
          >
            {slotKey}: {errors[slotKey]}
          </p>
        ))}

      {/* Tokens used (running then final) */}
      <TokenUsage tokenUsage={snapshot.token_usage} />
    </div>
  );
}

export default function CraftAPaper({ user }) {
  const router = useRouter();
  const userId = user?.sub || user?.username || 'dev-user';

  // Session Management
  const {
    currentSessionId,
    currentSession,
    loadSession,
    createSession,
    switchSession,
    updateSessionData,
    saveSession
  } = useSessionManagement({ userId });

  // Home view state
  const [showHome, setShowHome] = useState(true);
  // Drafts list state
  const [drafts, setDrafts] = useState([]);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [draftsError, setDraftsError] = useState('');
  const [deletingDraftId, setDeletingDraftId] = useState(null);

  // Session-derived state (these all come from currentSession now)
  const step = currentSession?.step || 1;
  const selectedExam = currentSession?.examType || 'PT';
  const selectedGrade = currentSession?.grade || '';
  const selectedSubject = currentSession?.subject || '';
  const selectedChapters = currentSession?.selectedChapters || [];
  const marksAllocation = currentSession?.marksAllocation || {};
  const selectedDiagrams = currentSession?.selectedDiagrams || [];
  const questionChapters = currentSession?.questionPaper ? {
    q1: currentSession.questionPaper.q1?.chapter || '',
    q2: currentSession.questionPaper.q2?.chapter || '',
    q3: currentSession.questionPaper.q3?.chapter || '',
    q4: currentSession.questionPaper.q4?.chapter || '',
    q5: currentSession.questionPaper.q5?.chapter || '',
    q6: currentSession.questionPaper.q6?.chapter || '',
    q7: currentSession.questionPaper.q7?.chapter || '',
    q8: currentSession.questionPaper.q8?.chapter || '',
    q9: currentSession.questionPaper.q9?.chapter || '',
  } : {};
  const questionDomains = currentSession?.questionPaper ? {
    q1: currentSession.questionPaper.q1?.domain || '',
    q2: currentSession.questionPaper.q2?.domain || '',
    q3: currentSession.questionPaper.q3?.domain || '',
    q4: currentSession.questionPaper.q4?.domain || '',
    q5: currentSession.questionPaper.q5?.domain || '',
    q6: currentSession.questionPaper.q6?.domain || '',
    q7: currentSession.questionPaper.q7?.domain || '',
    q8: currentSession.questionPaper.q8?.domain || '',
    q9: currentSession.questionPaper.q9?.domain || '',
  } : {};
  const questionImages = currentSession?.questionPaper ? {
    q1: currentSession.questionPaper.q1?.images || [],
    q2: currentSession.questionPaper.q2?.images || [],
    q3: currentSession.questionPaper.q3?.images || [],
    q4: currentSession.questionPaper.q4?.images || [],
    q5: currentSession.questionPaper.q5?.images || [],
    q6: currentSession.questionPaper.q6?.images || [],
    q7: currentSession.questionPaper.q7?.images || [],
    q8: currentSession.questionPaper.q8?.images || [],
    q9: currentSession.questionPaper.q9?.images || [],
  } : {};

  // API state
  const [grades, setGrades] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [loadingGrades, setLoadingGrades] = useState(false);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [s3Diagrams, setS3Diagrams] = useState({});
  const [loadingDiagrams, setLoadingDiagrams] = useState({});
  const [error, setError] = useState('');
  const [backendStatus, setBackendStatus] = useState('checking'); // 'checking', 'online', 'offline'
  const [saveStatus, setSaveStatus] = useState('idle'); // 'idle', 'saving', 'saved', 'error'

  // AI question-paper generation (Canvas 2 = AI Assistance)
  const [genJobId, setGenJobId] = useState(null);
  const [genStatus, setGenStatus] = useState(null); // latest polled snapshot
  const [genError, setGenError] = useState('');

  // ============================================================
  // SECTION-SCOPED DRAG & DROP (UI-only; NOT persisted into questionPaper)
  // ============================================================
  // Which slots are currently placed in the central paper. Resets to none on
  // load/resume so the user assembles the paper by dragging. Keeping this purely
  // in React state (not in questionPaper) preserves the draft round-trip byte-for-byte.
  const [placedSlots, setPlacedSlots] = useState({
    q1: false, q2: false, q3: false, q4: false, q5: false, q6: false, q7: false, q8: false, q9: false,
  });
  const [dragSlot, setDragSlot] = useState(null);     // slot id currently being dragged
  const [dropHover, setDropHover] = useState(null);   // section letter being hovered as a VALID target
  const [rejectHover, setRejectHover] = useState(null); // section letter showing "not allowed" feedback

  // Placed count for a section's live summary chip.
  const placedCount = (sec) => SECTION_SLOTS[sec].filter((s) => placedSlots[s]).length;

  // Drag handlers â€” native HTML5 DnD, mirroring the diagram drag pattern in this file.
  const handleCardDragStart = (e, slot) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData(QP_SLOT_MIME, slot);
    e.dataTransfer.setData('text/plain', slot);
    setDragSlot(slot);
  };

  const handleCardDragEnd = () => {
    setDragSlot(null);
    setDropHover(null);
    setRejectHover(null);
  };

  const handleSectionDragOver = (e, sec) => {
    e.preventDefault();
    const slot = dragSlot;
    const valid = slot && SLOT_SECTION[slot] === sec;
    e.dataTransfer.dropEffect = valid ? 'move' : 'none';
    if (valid) {
      setDropHover(sec);
      setRejectHover(null);
    } else if (slot) {
      setRejectHover(sec);
      setDropHover(null);
    }
  };

  const handleSectionDragLeave = (e, sec) => {
    e.preventDefault();
    setDropHover((prev) => (prev === sec ? null : prev));
    setRejectHover((prev) => (prev === sec ? null : prev));
  };

  const handleSectionDrop = (e, sec) => {
    e.preventDefault();
    const slot = e.dataTransfer.getData(QP_SLOT_MIME) || e.dataTransfer.getData('text/plain');
    setDropHover(null);
    setRejectHover(null);
    setDragSlot(null);
    // Section-lock: only accept a slot whose home section matches this drop zone.
    if (!slot || SLOT_SECTION[slot] !== sec) return;
    setPlacedSlots((prev) => ({ ...prev, [slot]: true }));
  };

  const removeSlot = (slot) => {
    setPlacedSlots((prev) => ({ ...prev, [slot]: false }));
  };

  const exams = [
    { code: 'PT', name: 'Periodic Test', marks: 20 },
    { code: 'HYE', name: 'Half Yearly', marks: 50 },
    { code: 'AE', name: 'Annual Exam', marks: 80 },
  ];

  const selectedExamData = exams.find((e) => e.code === selectedExam);
  const totalMarks = selectedExamData?.marks || 0;

  // ============================================================
  // DRAFT RECOVERY (AUTO - handled by session manager now)
  // ============================================================
  // Session is loaded via loadSession() when user clicks "Resume"
  // No need for separate hydration logic anymore

  // ============================================================
  // AUTO-SAVE (handled by session manager - 30s debounce)
  // ============================================================
  // Session auto-saves every 30 seconds if changes detected
  // No need for separate auto-save hook anymore

  const startNewPaper = () => {
    clearLocalDraft();
    setResumeDraftId(null);
    setStep(1);
    setSelectedExam('PT');
    setSelectedGrade('');
    setSelectedSubject('');
    setSelectedChapters([]);
    setMarksAllocation({});
    setSelectedDiagrams([]);
    setQuestionChapters({});
    setQuestionDomains({});
    setQuestionImages({});
    router.replace('/craft-a-paper', undefined, { shallow: true });
  };

  // Handle page unload (refresh, navigation, browser close)
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Ensure localStorage has the latest data before leaving
      const currentDraft = {
        step,
        examType: selectedExam,
        grade: selectedGrade,
        subject: selectedSubject,
        selectedChapters,
        marksAllocation,
        selectedDiagrams,
        questionChapters,
        questionDomains,
        questionImages,
        totalMarks,
        updatedAt: new Date().toISOString(),
      };
      writeLocalDraft(currentDraft);
      console.log('Saved draft before unload:', Object.keys(currentDraft));
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [step, selectedExam, selectedGrade, selectedSubject, selectedChapters, marksAllocation, selectedDiagrams, questionChapters, questionDomains, questionImages, totalMarks]);

  // Load drafts when home view is shown
  const loadDraftsData = async () => {
    setLoadingDrafts(true);
    setDraftsError('');
    try {
      // Try to fetch from backend (source of truth for draft list)
      const backendDrafts = await listDrafts(userId);
      
      // Show backend drafts if available
      if (backendDrafts && backendDrafts.length > 0) {
        setDrafts(backendDrafts);
        console.log('Loaded drafts from backend:', backendDrafts.length);
      } else {
        // Backend has no drafts - don't show localStorage draft in the list
        // (localStorage is only a fallback for resuming current draft, not for listing)
        setDrafts([]);
        console.log('No drafts found in backend');
      }
    } catch (err) {
      console.error('Failed to load drafts:', err);
      setDraftsError(`Failed to load drafts: ${err.message}`);
      setDrafts([]);
    } finally {
      setLoadingDrafts(false);
    }
  };

  // Fetch drafts when showing home view
  useEffect(() => {
    if (showHome) {
      loadDraftsData();
    }
  }, [showHome]);

  // Handler to start a new paper from home view
  const handleCreateNewPaper = async () => {
    clearLocalDraft();
    const session = await createSession({
      examType: 'PT',
      grade: '',
      subject: '',
      step: 1
    });
    setShowHome(false);
  };

  // Handler to resume a draft.
  const handleResumeDraft = async (draftSummary) => {
    if (!draftSummary?.draftId) return;
    
    // Load entire session
    await loadSession(draftSummary.draftId);
    setShowHome(false);
  };

  // Delete a draft safely
  const handleDeleteDraft = async (draftId, e) => {
    e.stopPropagation();
    
    // Confirm deletion
    if (!window.confirm('Are you sure you want to delete this draft? This action cannot be undone.')) {
      return;
    }
    
    setDeletingDraftId(draftId);
    try {
      const deleted = await deleteDraft(draftId, userId);
      if (deleted) {
        // Remove from list
        setDrafts(drafts.filter(d => d.draftId !== draftId));
        console.log('Draft deleted:', draftId);
      } else {
        setDraftsError('Failed to delete draft');
      }
    } catch (err) {
      console.error('Error deleting draft:', err);
      setDraftsError(`Failed to delete draft: ${err.message}`);
    } finally {
      setDeletingDraftId(null);
    }
  };

  // Handler to go back to home from step
  // Go back to home view
  const handleBackToHome = () => {
    setShowHome(true);
  };

  // Update step in session
  const handleStepChange = (newStep) => {
    updateSessionData('step', newStep);
  };

  // Kick off AI generation: persist the session, start the job, then navigate to
  // step 3 and begin polling. Even on error we still reach step 3 to show it.
  const handleGeneratePaper = async () => {
    try {
      setGenError('');
      setGenStatus(null);
      await saveSession(); // (a) persist latest questionPaper
      const { jobId } = await startGeneration(currentSessionId, userId); // (b)
      setGenJobId(jobId);
      handleStepChange(3); // (c) keep step-3 nav
    } catch (e) {
      setGenError(e.message);
      handleStepChange(3); // still show step 3 with the error
    }
  };

  // Poll the generation job while one is active; stop on completed/failed.
  useEffect(() => {
    if (!genJobId) return undefined;

    let cancelled = false;

    const poll = async () => {
      try {
        const snapshot = await getGenerationStatus(genJobId, userId);
        if (cancelled || !snapshot) return;
        setGenStatus(snapshot);
        if (snapshot.status === 'completed' || snapshot.status === 'failed') {
          clearInterval(intervalId);
        }
      } catch (e) {
        if (!cancelled) setGenError(e.message);
      }
    };

    poll(); // immediate first fetch
    const intervalId = setInterval(poll, GEN_POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [genJobId, userId]);

  // Update exam type in session
  const handleExamChange = (examType) => {
    updateSessionData('examType', examType);
  };

  // Load grades on mount
  useEffect(() => {
    const loadGradesData = async () => {
      setLoadingGrades(true);
      setError('');
      try {
        // Check backend status first
        const backendRunning = await isBackendRunning();
        setBackendStatus(backendRunning ? 'online' : 'offline');
        
        const data = await getGrades();
        setGrades(data);
        if (data.length === 0) {
          setError('No grades available yet.');
        }
      } catch (err) {
        setBackendStatus('offline');
        setError(`Failed to load grades: ${err.message}`);
      } finally {
        setLoadingGrades(false);
      }
    };
    loadGradesData();
  }, []);

  // Load subject OPTIONS when grade changes.
  // This effect only populates the dropdown; it never clears selections, so it
  // is safe during a draft restore. Selection resets happen in handleGradeChange.
  useEffect(() => {
    if (!selectedGrade) {
      setSubjects([]);
      return;
    }

    const loadSubjectsData = async () => {
      setLoadingSubjects(true);
      setError('');
      try {
        const data = await getSubjects(selectedGrade);
        setSubjects(data);
        if (data.length === 0) {
          setError(`No subjects available for ${selectedGrade} yet.`);
        }
      } catch (err) {
        setError(`Failed to load subjects: ${err.message}`);
      } finally {
        setLoadingSubjects(false);
      }
    };
    loadSubjectsData();
  }, [selectedGrade]);

  // Load chapter OPTIONS when subject changes.
  // Only populates the dropdown; never clears selections. Selection resets
  // happen in handleSubjectChange.
  useEffect(() => {
    if (!selectedGrade || !selectedSubject) {
      setChapters([]);
      return;
    }

    const loadChaptersData = async () => {
      setLoadingChapters(true);
      setError('');
      try {
        const data = await getChapters(selectedGrade, selectedSubject);
        setChapters(data);
        if (data.length === 0) {
          setError(`No chapters available for ${selectedSubject} yet.`);
        }
      } catch (err) {
        setError(`Failed to load chapters: ${err.message}`);
      } finally {
        setLoadingChapters(false);
      }
    };
    loadChaptersData();
  }, [selectedGrade, selectedSubject]);

  // Explicit user change of grade: reset the dependent selections.
  // Update grade - cascades to reset subject and chapters
  const handleGradeChange = (value) => {
    updateSessionData('grade', value);
    updateSessionData('subject', '');
    updateSessionData('selectedChapters', []);
    updateSessionData('marksAllocation', {});
  };

  // Update subject - cascades to reset chapters
  const handleSubjectChange = (value) => {
    updateSessionData('subject', value);
    updateSessionData('selectedChapters', []);
    updateSessionData('marksAllocation', {});
  };

  const toggleChapter = (chapterId) => {
    const isSelected = selectedChapters.includes(chapterId);
    
    if (isSelected) {
      // Deselecting: remove from chapters and clear marks for this chapter
      const newChapters = selectedChapters.filter((id) => id !== chapterId);
      const newMarks = { ...marksAllocation };
      delete newMarks[chapterId];
      
      updateSessionData('selectedChapters', newChapters);
      updateSessionData('marksAllocation', newMarks);
    } else {
      // Selecting: add to chapters
      updateSessionData('selectedChapters', [...selectedChapters, chapterId]);
    }
  };

  const handleMarksChange = (chapterId, value) => {
    const newMarks = {
      ...marksAllocation,
      [chapterId]: parseInt(value) || 0,
    };
    updateSessionData('marksAllocation', newMarks);
  };

  const toggleDiagram = (diagramId) => {
    const isSelected = selectedDiagrams.includes(diagramId);
    const newDiagrams = isSelected
      ? selectedDiagrams.filter((id) => id !== diagramId)
      : [...selectedDiagrams, diagramId];
    updateSessionData('selectedDiagrams', newDiagrams);
  };

  // Only count marks for chapters that are currently selected. This guards
  // against stale entries left in marksAllocation from chapters that were
  // deselected (or removed) after marks were entered.
  const totalAllocated = selectedChapters.reduce(
    (sum, chapterId) => sum + (marksAllocation[chapterId] || 0),
    0
  );

  const getChapterById = (id) => chapters.find((c) => c.id === id);

  // Question image drag-drop handlers
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDropDiagram = (e, questionId) => {
    e.preventDefault();
    e.stopPropagation();

    // Get dragged diagram data
    const diagramData = e.dataTransfer.getData('application/json');
    if (!diagramData) return;

    try {
      const diagram = JSON.parse(diagramData);
      const images = [...(questionImages[questionId] || []), diagram];
      updateSessionData(`questionPaper.${questionId}.images`, images);
    } catch (err) {
      console.error('Error parsing dragged diagram:', err);
    }
  };

  const removeImageFromQuestion = (questionId, index) => {
    const images = [...(questionImages[questionId] || [])];
    images.splice(index, 1);
    updateSessionData(`questionPaper.${questionId}.images`, images);
  };

  const updateQuestionChapter = (questionId, chapter) => {
    updateSessionData(`questionPaper.${questionId}.chapter`, chapter);
  };

  const updateQuestionDomain = (questionId, domain) => {
    updateSessionData(`questionPaper.${questionId}.domain`, domain);
  };

  // Helper to render chapter options for dropdowns
  const renderChapterOptions = () => {
    return selectedChapters.map((chId) => {
      const chapter = chapters.find(c => c.id === chId);
      return chapter ? <option key={chId} value={chapter.title}>{chapter.title}</option> : null;
    });
  };

  // Explicit save handler for the Save Draft button
  const handleSaveDraft = async () => {
    try {
      setSaveStatus('saving');
      
      // Save current session
      await saveSession();
      
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (err) {
      console.error('Error saving draft:', err);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  // Build structured question paper data for backend storage
  const buildQuestionPaperData = () => {
    const sections = {
      A: {
        title: "Multiple Choice Questions",
        type: "MCQ",
        marks_per_question: 1,
        total_questions: 4,
        total_marks: 4,
        questions: [
          {
            question_number: 1,
            section: 'A',
            chapter: questionChapters.q1 || '',
            learning_domain: questionDomains.q1 || 'R/U',
            marks: 1,
            diagrams: questionImages.q1 || []
          },
          {
            question_number: 2,
            section: 'A',
            chapter: questionChapters.q2 || '',
            learning_domain: questionDomains.q2 || 'R/U',
            marks: 1,
            diagrams: questionImages.q2 || []
          },
          {
            question_number: 3,
            section: 'A',
            chapter: questionChapters.q3 || '',
            learning_domain: questionDomains.q3 || 'R/U',
            marks: 1,
            diagrams: questionImages.q3 || []
          },
          {
            question_number: 4,
            section: 'A',
            chapter: questionChapters.q4 || '',
            learning_domain: questionDomains.q4 || 'R/U',
            marks: 1,
            diagrams: questionImages.q4 || []
          }
        ]
      },
      B: {
        title: "Very Short Answer",
        type: "VSA",
        marks_per_question: 2,
        total_questions: 2,
        total_marks: 4,
        questions: [
          {
            question_number: 5,
            section: 'B',
            chapter: questionChapters.q5 || '',
            learning_domain: questionDomains.q5 || 'R/U',
            marks: 2,
            diagrams: questionImages.q5 || []
          },
          {
            question_number: 6,
            section: 'B',
            chapter: questionChapters.q6 || '',
            learning_domain: questionDomains.q6 || 'R/U',
            marks: 2,
            diagrams: questionImages.q6 || []
          }
        ]
      },
      C: {
        title: "Short Answer",
        type: "SA",
        marks_per_question: 3,
        total_questions: 1,
        total_marks: 3,
        questions: [
          {
            question_number: 7,
            section: 'C',
            chapter: questionChapters.q7 || '',
            learning_domain: questionDomains.q7 || 'R/U',
            marks: 3,
            diagrams: questionImages.q7 || []
          }
        ]
      },
      D: {
        title: "Long Answer",
        type: "LA",
        marks_per_question: 5,
        total_questions: 1,
        total_marks: 5,
        questions: [
          {
            question_number: 8,
            section: 'D',
            chapter: questionChapters.q8 || '',
            learning_domain: questionDomains.q8 || 'R/U',
            marks: 5,
            diagrams: questionImages.q8 || []
          }
        ]
      },
      E: {
        title: "Case-Based Assessment",
        type: "CBA",
        marks_per_question: 4,
        total_questions: 1,
        total_marks: 4,
        questions: [
          {
            question_number: 9,
            section: 'E',
            chapter: questionChapters.q9 || '',
            learning_domain: questionDomains.q9 || 'R/U',
            marks: 4,
            diagrams: questionImages.q9 || []
          }
        ]
      }
    };

    return {
      exam_type: selectedExam,
      grade: selectedGrade,
      subject: selectedSubject,
      selected_chapters: selectedChapters.map(id => {
        const chapter = chapters.find(c => c.id === id);
        return chapter ? { id, title: chapter.title, folder: chapter.folder } : null;
      }).filter(Boolean),
      marks_allocation: marksAllocation,
      total_marks: totalMarks,
      sections: sections,
      metadata: {
        total_questions: 9,
        total_marks: 20,
        created_at: new Date().toISOString()
      }
    };
  };

  // Fetch diagrams from S3 when chapters are selected.
  //
  // IMPORTANT (refresh/resume fix): fetching a chapter's diagrams needs
  // `chapter.folder`, which only exists on the loaded `chapters` options array
  // (populated asynchronously by getChapters). On a refresh/resume, `selectedChapters`
  // (just ids) is restored instantly but `chapters` is still loading. If we ran now,
  // `chapters.find(...)` would return undefined for every id and we'd fetch nothing
  // ("No diagrams available"). So we wait until `chapters` has loaded. Because
  // `chapters` is in the dependency array, this effect re-runs automatically once
  // the options arrive.
  useEffect(() => {
    if (selectedChapters.length === 0 || !selectedGrade || !selectedSubject) {
      setS3Diagrams({});
      return;
    }

    // Chapter options not loaded yet â€” wait for the re-run once they are.
    if (chapters.length === 0) {
      return;
    }

    // Only proceed once every selected id can be resolved to a chapter object.
    // (Guards against a transient state where chapters are for a different subject.)
    const resolvable = selectedChapters.filter((id) =>
      chapters.some((c) => c.id === id)
    );
    if (resolvable.length === 0) {
      return;
    }

    let cancelled = false;

    const fetchDiagramsForChapters = async () => {
      const newS3Diagrams = {};

      for (const chapterId of resolvable) {
        const chapter = chapters.find((c) => c.id === chapterId);
        if (!chapter) continue;

        const diagKey = chapter.folder;
        if (newS3Diagrams[diagKey]) continue; // Already fetched

        setLoadingDiagrams((prev) => ({ ...prev, [diagKey]: true }));
        try {
          const diagrams = await getDiagrams(
            selectedGrade,
            selectedSubject,
            chapter.folder
          );
          newS3Diagrams[diagKey] = diagrams;
        } catch (err) {
          console.error(`Failed to fetch diagrams for ${chapter.title}:`, err);
          newS3Diagrams[diagKey] = [];
        } finally {
          setLoadingDiagrams((prev) => ({ ...prev, [diagKey]: false }));
        }
      }

      if (!cancelled) {
        setS3Diagrams(newS3Diagrams);
      }
    };

    fetchDiagramsForChapters();

    return () => {
      cancelled = true;
    };
  }, [selectedChapters, selectedGrade, selectedSubject, chapters]);

  // Get diagrams for selected chapters grouped by folder
  const getDiagramsForSelectedChapters = () => {
    const grouped = {};
    
    selectedChapters.forEach((chapterId) => {
      const chapter = chapters.find((c) => c.id === chapterId);
      if (chapter && s3Diagrams[chapter.folder]) {
        grouped[chapter.folder] = {
          chapter,
          diagrams: s3Diagrams[chapter.folder],
        };
      }
    });
    
    return grouped;
  };

  // If showHome is true, render the home view with 2 columns
  if (showHome) {
    return (
      <>
        <Head>
          <title>Craft a Paper</title>
        </Head>
        <div
          className="min-h-screen bg-gray-50 flex flex-col"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.75)), url("/craft-paper-icon.png")',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat',
            backgroundAttachment: 'fixed',
          }}
        >
          {/* Header */}
          <div className="mx-auto max-w-7xl px-4 py-10 w-full flex items-center justify-between">
            <Link href="/" className="text-sm text-gray-500 hover:text-gray-700">
              &larr; Back to Home
            </Link>
            <div className="flex items-center gap-4">
              {backendStatus === 'offline' && (
                <span className="text-xs text-yellow-600 font-medium">Backend Offline</span>
              )}
              {backendStatus === 'online' && (
                <span className="text-xs text-green-600 font-medium flex items-center gap-1">
                  <span className="inline-block w-2 h-2 bg-green-500 rounded-full"></span>
                  Connected
                </span>
              )}
              <Link
                href="/my-drafts"
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                My Drafts
              </Link>
            </div>
          </div>

          {/* Main Content: 2-Column Layout */}
          <div className="flex-1 flex items-center justify-center px-4 pb-10">
            <div className="w-full max-w-6xl grid grid-cols-2 gap-8">
              {/* Left Column: Create a New Paper */}
              <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl shadow-lg p-12 flex flex-col justify-center h-96">
                <div className="text-white">
                  <h2 className="text-3xl font-bold mb-4">
                    Create a New Paper
                  </h2>
                  <p className="text-blue-100 mb-8 leading-relaxed text-lg">
                    Start crafting your question paper by selecting an exam type, grade, and subject. Our guided workflow will help you complete it efficiently.
                  </p>
                  <button
                    onClick={handleCreateNewPaper}
                    className="bg-white hover:bg-gray-50 text-blue-600 font-semibold py-3 px-8 rounded-lg transition shadow-md hover:shadow-lg duration-200 text-lg"
                  >
                    Create New Paper
                  </button>
                </div>
              </div>

              {/* Right Column: View Previously Drafted Papers */}
              <div className="bg-white rounded-xl shadow-lg p-8 overflow-hidden flex flex-col h-96">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">
                  Previously Drafted Papers
                </h2>

                {draftsError && (
                  <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-700">{draftsError}</p>
                  </div>
                )}

                {loadingDrafts ? (
                  <div className="flex items-center justify-center flex-1">
                    <div className="text-center">
                      <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600 mb-3" />
                      <p className="text-sm text-gray-600">Loading drafts...</p>
                    </div>
                  </div>
                ) : drafts.length === 0 ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center py-8">
                      <p className="text-gray-500 mb-2 font-medium">No drafts yet</p>
                      <p className="text-sm text-gray-400">
                        Your saved papers will appear here
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                    {drafts.map((draft) => (
                      <div
                        key={draft.draftId}
                        className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all cursor-pointer group"
                        onClick={() => handleResumeDraft(draft)}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition flex-1">
                            {draft.examType && `${draft.examType}`}
                            {draft.grade && ` â€¢ ${draft.grade}`}
                            {draft.subject && ` â€¢ ${draft.subject}`}
                          </h3>
                          <div className="flex items-center gap-2">
                            <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded font-medium">
                              Step {draft.step || 1}
                            </span>
                            <button
                              onClick={(e) => handleDeleteDraft(draft.draftId, e)}
                              disabled={deletingDraftId === draft.draftId}
                              className="text-xs px-2 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded font-medium transition opacity-0 group-hover:opacity-100 disabled:opacity-50"
                              title="Delete draft"
                            >
                              {deletingDraftId === draft.draftId ? 'Deleting...' : 'âœ• Delete'}
                            </button>
                          </div>
                        </div>
                        <p className="text-sm text-gray-600">
                          {draft.chapterCount || 0} chapters selected
                        </p>
                        <p className="text-xs text-gray-400 mt-1">
                          {draft.updatedAt
                            ? `Last saved ${timeAgo(draft.updatedAt)}`
                            : 'Not synced'}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  if (step === 3) {
    return (
      <>
        <Head>
          <title>Generate Paper - Craft a Paper</title>
        </Head>
        <div className="w-full h-screen flex flex-col bg-white overflow-hidden">
          {/* Backend Status Banner */}
          {backendStatus === 'offline' && (
            <div className="bg-yellow-50 border-b border-yellow-200 px-6 py-3">
              <div className="flex items-center gap-2 text-sm text-yellow-800">
                <span className="text-lg">âš ï¸</span>
                <span>
                  <strong>Backend Offline:</strong> Using mock data for development. Real diagrams and data will sync when backend is running at <code className="bg-yellow-100 px-2 py-1 rounded font-mono text-xs">http://localhost:8000</code>
                </span>
              </div>
            </div>
          )}
          {backendStatus === 'online' && (
            <div className="bg-green-50 border-b border-green-200 px-6 py-2">
              <div className="flex items-center gap-2 text-xs text-green-700">
                <span className="inline-block w-2 h-2 bg-green-500 rounded-full"></span>
                Backend Connected
              </div>
            </div>
          )}
          
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white shadow-sm">
            <h1 className="text-2xl font-bold text-gray-900">
              Generate Question Paper
            </h1>
            <div className="flex items-center gap-4">
              <SaveIndicator status={saveStatus} />
              <button
                onClick={handleSaveDraft}
                disabled={saveStatus === 'saving'}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white text-sm font-medium rounded transition"
              >
                {saveStatus === 'saving' ? 'Saving...' : 'Save Draft'}
              </button>
              <button
                onClick={() => handleStepChange(2)}
                className="text-sm text-gray-500 hover:text-gray-700 font-medium px-4 py-2"
              >
                â† Back
              </button>
              <button
                onClick={handleBackToHome}
                className="text-sm text-gray-500 hover:text-gray-700 font-medium px-4 py-2"
              >
                Home
              </button>
            </div>
          </div>

          {/* 4-Region Grid - Full Height: Diagrams | Section Palette | Question Paper | AI Assistance */}
          <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden">
            {/* Left Panel: Diagram Selection */}
            <div className="col-span-2 bg-gray-50 border-r border-gray-200 overflow-hidden flex flex-col">
              <div className="p-6 border-b border-gray-200 bg-white">
                <h2 className="text-lg font-semibold text-gray-900">
                  Diagrams
                </h2>
              </div>
              <div className="flex-1 overflow-y-auto p-6">
                {(() => {
                  const groupedDiagrams = getDiagramsForSelectedChapters();
                  const diagramEntries = Object.entries(groupedDiagrams);
                  
                  if (diagramEntries.length === 0) {
                    return (
                      <div className="flex items-center justify-center h-full">
                        <div className="p-6 bg-white rounded-lg text-center">
                          <p className="text-sm text-gray-600">
                            No diagrams available for selected chapters
                          </p>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div className="space-y-6">
                      {diagramEntries.map(([folder, { chapter, diagrams }]) => (
                        <div key={folder} className="border-b pb-4">
                          <h3 className="text-sm font-semibold text-gray-900 mb-3">
                            {chapter.order}. {chapter.title}
                          </h3>
                          {loadingDiagrams[folder] ? (
                            <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
                              Loading diagrams...
                            </div>
                          ) : diagrams.length > 0 ? (
                            <div className="grid grid-cols-2 gap-3">
                              {diagrams.map((diagram) => (
                                <div
                                  key={diagram.key}
                                  draggable
                                  onDragStart={(e) => {
                                    e.dataTransfer.effectAllowed = 'copy';
                                    // Carry the diagram's own source chapter folder so the
                                    // backend can ground a diagram slot in the right chapter.
                                    e.dataTransfer.setData('application/json', JSON.stringify({ ...diagram, folder }));
                                  }}
                                  className="flex flex-col items-center gap-2 p-2 rounded-lg border border-gray-200 hover:border-blue-500 hover:shadow-md hover:bg-blue-50 transition-all duration-200 cursor-move"
                                >
                                  {diagram.url && (
                                    <div className="w-full h-24 overflow-hidden rounded-md border border-gray-300 bg-gray-100">
                                      <img
                                        src={diagram.url}
                                        alt={diagram.name}
                                        className="w-full h-full object-cover"
                                        onError={(e) => {
                                          e.target.style.display = 'none';
                                        }}
                                      />
                                    </div>
                                  )}
                                  <p className="block text-xs font-medium text-gray-700 text-center line-clamp-2">
                                    {diagram.name}
                                  </p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="p-2 text-xs text-gray-500">
                              No diagrams found
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Section Palette: each section shows ONLY its own UNPLACED questions. */}
            <div className="col-span-3 bg-gray-50 border-r border-gray-200 overflow-hidden flex flex-col">
              <div className="p-6 border-b border-gray-200 bg-white">
                <h2 className="text-lg font-semibold text-gray-900">Question Bank</h2>
                <p className="text-xs text-gray-500 mt-1">
                  Drag each question into its matching section of the paper.
                </p>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {SECTION_ORDER.map((sec) => {
                  const unplaced = SECTION_SLOTS[sec].filter((s) => !placedSlots[s]);
                  return (
                    <div key={sec}>
                      <div className="mb-2 flex items-baseline justify-between">
                        <h3 className="text-sm font-bold text-gray-900">Section {sec}</h3>
                        <span className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                          {SECTION_META[sec].title}
                        </span>
                      </div>
                      <div className="space-y-3">
                        {unplaced.length === 0 ? (
                          <p className="rounded-md border border-dashed border-gray-300 bg-white px-3 py-2 text-xs text-gray-400">
                            All questions placed
                          </p>
                        ) : (
                          unplaced.map((slot) => (
                            <QuestionSlotCard
                              key={slot}
                              slot={slot}
                              placed={false}
                              chapterValue={questionChapters[slot] || ''}
                              domainValue={questionDomains[slot] || 'R/U'}
                              images={questionImages[slot]}
                              chapterOptions={renderChapterOptions()}
                              onDragStartCard={handleCardDragStart}
                              onDragEndCard={handleCardDragEnd}
                              onChapterChange={updateQuestionChapter}
                              onDomainChange={updateQuestionDomain}
                              onDropDiagram={handleDropDiagram}
                              onDragOverDiagram={handleDragOver}
                              onDragLeaveDiagram={handleDragLeave}
                              onRemoveImage={removeImageFromQuestion}
                              onRemovePlacement={removeSlot}
                            />
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Middle Panel: Canvas 1 - Question Paper (central assembly canvas) */}
            <div className="col-span-4 bg-white border-r border-gray-200 overflow-hidden flex flex-col">
              <div className="p-6 border-b border-gray-200 bg-white">
                <h2 className="text-lg font-semibold text-gray-900">
                  Question Paper
                </h2>
                <p className="text-xs text-gray-500 mt-1">
                  Periodic Test 1 | Science VII | 20 Marks | 60 Minutes
                </p>
                {/* Live placement scoring summary (placed/total per section). */}
                <div className="mt-3 flex flex-wrap gap-2">
                  {SECTION_ORDER.map((sec) => {
                    const done = placedCount(sec);
                    const total = SECTION_SLOTS[sec].length;
                    const complete = done === total;
                    return (
                      <span
                        key={sec}
                        className={`rounded px-2 py-1 text-xs font-medium transition-colors duration-300 ${
                          complete ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {sec}: {done}/{total}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Question Paper Content: five section-locked drop zones, always Aâ†’E order. */}
              <div className="flex-1 overflow-y-auto p-8 bg-white">
                <div className="max-w-2xl space-y-6">
                  {SECTION_ORDER.map((sec) => {
                    const placed = SECTION_SLOTS[sec].filter((s) => placedSlots[s]);
                    const isValidHover = dropHover === sec;
                    const isRejectHover = rejectHover === sec;
                    return (
                      <div key={sec}>
                        <div className="mb-4 mt-6 border-b-2 border-gray-800 pb-3 first:mt-0">
                          <p className="text-sm font-bold text-gray-900">
                            SECTION {sec}: {SECTION_META[sec].title}
                          </p>
                          <p className="mt-1 text-xs text-gray-600">{SECTION_META[sec].note}</p>
                        </div>
                        <div
                          onDragOver={(e) => handleSectionDragOver(e, sec)}
                          onDragLeave={(e) => handleSectionDragLeave(e, sec)}
                          onDrop={(e) => handleSectionDrop(e, sec)}
                          className={`ml-2 space-y-4 rounded-lg border-2 border-dashed p-3 transition-colors duration-200 ${
                            isValidHover
                              ? 'border-green-500 bg-green-50'
                              : isRejectHover
                              ? 'cursor-not-allowed border-red-400 bg-red-50'
                              : 'border-gray-200'
                          }`}
                        >
                          {placed.length === 0 ? (
                            <p className="py-4 text-center text-xs text-gray-400">
                              Drag Section {sec} questions here
                            </p>
                          ) : (
                            placed.map((slot) => (
                              <QuestionSlotCard
                                key={slot}
                                slot={slot}
                                placed
                                chapterValue={questionChapters[slot] || ''}
                                domainValue={questionDomains[slot] || 'R/U'}
                                images={questionImages[slot]}
                                chapterOptions={renderChapterOptions()}
                                onDragStartCard={handleCardDragStart}
                                onDragEndCard={handleCardDragEnd}
                                onChapterChange={updateQuestionChapter}
                                onDomainChange={updateQuestionDomain}
                                onDropDiagram={handleDropDiagram}
                                onDragOverDiagram={handleDragOver}
                                onDragLeaveDiagram={handleDragLeave}
                                onRemoveImage={removeImageFromQuestion}
                                onRemovePlacement={removeSlot}
                              />
                            ))
                          )}
                        </div>
                      </div>
                    );
                  })}

                  <div className="mt-8 border-t pt-6 text-center text-xs text-gray-600">
                    Total: 9 Questions | 20 Marks
                  </div>
                </div>
              </div>
            </div>

            {/* Right Panel: Canvas 2 — AI Assistance (generation progress, unchanged meaning) */}
            <div className="col-span-3 bg-white overflow-hidden flex flex-col">
              <div className="p-6 border-b border-gray-200 bg-white">
                <h2 className="text-lg font-semibold text-gray-900">
                  AI Assistance
                </h2>
                <p className="text-xs text-gray-500 mt-1">
                  AI-generated questions per section
                </p>
              </div>
              <div className="flex-1 min-h-0 bg-white overflow-y-auto p-4">
                <GenerationResults snapshot={genStatus} error={genError} />
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex gap-4 px-6 py-4 border-t border-gray-200 bg-white shadow-sm">
            <button
              onClick={() => handleStepChange(2)}
              className="flex-1 max-w-xs bg-gray-200 hover:bg-gray-300 text-gray-900 font-semibold py-3 px-6 rounded-lg transition"
            >
              Back to Edit
            </button>
            <button
              onClick={handleBackToHome}
              className="flex-1 max-w-xs bg-gray-300 hover:bg-gray-400 text-gray-900 font-semibold py-3 px-6 rounded-lg transition"
            >
              Back to Home
            </button>
            <button
              onClick={handleGeneratePaper}
              disabled={genStatus?.status === 'generating'}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-lg transition"
            >
              {genStatus?.status === 'generating' ? 'â³ Generatingâ€¦' : 'âœ¨ Generate Paper'}
            </button>
            <button className="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg transition">
              ðŸ“¥ Download Paper
            </button>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Head>
        <title>Craft a Paper</title>
      </Head>
      <div
        className="min-h-screen bg-gray-50 flex flex-col"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.75)), url("/craft-paper-icon.png")',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          backgroundAttachment: 'fixed',
        }}
      >
        <div className="mx-auto max-w-5xl px-4 py-10 w-full flex items-center justify-between">
          <Link href="/" className="text-sm text-gray-500 hover:text-gray-700">
            &larr; Back
          </Link>
          <div className="flex items-center gap-4">
            <SaveIndicator status={saveStatus} />
            <Link
              href="/my-drafts"
              className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              My Drafts
            </Link>
            <button
              onClick={handleBackToHome}
              className="text-sm text-gray-600 hover:text-gray-900 font-medium border border-gray-300 rounded-lg px-3 py-1.5"
            >
              â† Back to Home
            </button>
          </div>
        </div>

        <div className="flex-1 flex items-start justify-center px-4 pb-10">
          <div className="w-full max-w-2xl bg-white rounded-xl shadow-lg p-8">
            {/* Error Alert */}
            {error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Step 1: Basic Paper Info */}
            {step === 1 && (
              <>
                <h1 className="text-2xl font-bold text-gray-900 mb-8">
                  New Question Paper
                </h1>

                {/* Exam Type Section */}
                <div className="mb-8">
                  <h2 className="text-lg font-semibold text-gray-800 mb-4">
                    Exam Type
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {exams.map((exam) => (
                      <button
                        key={exam.code}
                        onClick={() => handleExamChange(exam.code)}
                        className={`p-4 rounded-lg border-2 transition text-left ${
                          selectedExam === exam.code
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 bg-white hover:border-gray-300'
                        }`}
                      >
                        <div className="font-semibold text-gray-900">
                          {exam.code}
                        </div>
                        <div className="text-sm text-gray-600">
                          {exam.name} â€” {exam.marks} marks
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Grade Section */}
                <div className="mb-8">
                  <label className="block text-lg font-semibold text-gray-800 mb-3">
                    Grade
                  </label>
                  {loadingGrades ? (
                    <div className="p-3 bg-gray-100 rounded-lg text-sm text-gray-600">
                      Loading grades...
                    </div>
                  ) : grades.length === 0 ? (
                    <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600 border border-gray-200">
                      No grades available yet.
                    </div>
                  ) : (
                    <select
                      value={selectedGrade}
                      onChange={(e) => handleGradeChange(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Select a Grade</option>
                      {grades.map((grade) => (
                        <option key={grade} value={grade}>
                          {grade}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Subject Section */}
                <div className="mb-8">
                  <label className="block text-lg font-semibold text-gray-800 mb-3">
                    Subject
                  </label>
                  {!selectedGrade ? (
                    <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600 border border-gray-200">
                      Select a Grade first
                    </div>
                  ) : loadingSubjects ? (
                    <div className="p-3 bg-gray-100 rounded-lg text-sm text-gray-600">
                      Loading subjects...
                    </div>
                  ) : subjects.length === 0 ? (
                    <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600 border border-gray-200">
                      No subjects available for {selectedGrade} yet.
                    </div>
                  ) : (
                    <select
                      value={selectedSubject}
                      onChange={(e) => handleSubjectChange(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Select a Subject</option>
                      {subjects.map((subject) => (
                        <option key={subject} value={subject}>
                          {subject}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Total Marks Display */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center justify-between mb-8">
                  <span className="text-lg font-semibold text-gray-900">
                    Total Marks
                  </span>
                  <span className="text-3xl font-bold text-blue-600">
                    {totalMarks}
                  </span>
                </div>

                {/* Continue Button */}
                <button
                  onClick={() => handleStepChange(2)}
                  disabled={!selectedGrade || !selectedSubject}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition"
                >
                  Continue
                </button>
              </>
            )}

            {/* Step 2: Chapter & Marks Allocation */}
            {step === 2 && (
              <>
                <div className="flex items-center justify-between mb-8">
                  <h1 className="text-2xl font-bold text-gray-900">
                    Chapter & Marks Allocation
                  </h1>
                  <button
                    onClick={() => handleStepChange(1)}
                    className="text-sm text-gray-500 hover:text-gray-700"
                  >
                    Edit
                  </button>
                </div>

                {/* Chapters Selection */}
                <div className="mb-8">
                  <h2 className="text-lg font-semibold text-gray-800 mb-4">
                    Select Chapters
                  </h2>
                  {loadingChapters ? (
                    <div className="p-3 bg-gray-100 rounded-lg text-sm text-gray-600">
                      Loading chapters...
                    </div>
                  ) : chapters.length === 0 ? (
                    <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600 border border-gray-200">
                      No chapters available yet.
                    </div>
                  ) : (
                    <div className="space-y-3 mb-6">
                      {chapters.map((chapter) => {
                        const isSelected = selectedChapters.includes(chapter.id);
                        return (
                          <div
                            key={chapter.id}
                            className={`p-3 border-2 rounded-lg cursor-pointer transition-all ${
                              isSelected
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200 bg-white hover:border-blue-300'
                            }`}
                            onClick={() => toggleChapter(chapter.id)}
                          >
                            <div className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => toggleChapter(chapter.id)}
                                className="w-4 h-4 rounded"
                                onClick={(e) => e.stopPropagation()}
                              />
                              <p className="text-sm text-gray-700 font-medium flex-1">
                                {chapter.order}. {chapter.title}
                              </p>
                              {isSelected && (
                                <span className="text-xs bg-blue-200 text-blue-800 px-2 py-1 rounded">
                                  Selected
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Marks Allocation */}
                {selectedChapters.length > 0 && (
                  <div className="mb-8">
                    <h2 className="text-lg font-semibold text-gray-800 mb-4">
                      Marks Allocation
                    </h2>
                    <p className="text-sm text-gray-600 mb-4">
                      Assign marks to each selected chapter. Total must equal {totalMarks} marks.
                    </p>
                    <div className="space-y-3 bg-gray-50 p-4 rounded-lg border border-gray-200">
                      {selectedChapters.map((chapterId) => {
                        const chapter = getChapterById(chapterId);
                        const marks = marksAllocation[chapterId] || 0;
                        return (
                          <div key={chapterId} className="flex items-center gap-4 p-2 bg-white rounded border border-gray-200">
                            <label className="flex-1 text-sm text-gray-700 font-medium">
                              {chapter?.order}. {chapter?.title}
                            </label>
                            <div className="flex items-center gap-2">
                              <input
                                type="number"
                                min="0"
                                max={totalMarks}
                                value={marks}
                                onChange={(e) =>
                                  handleMarksChange(chapterId, e.target.value)
                                }
                                className="w-16 px-3 py-2 border-2 border-gray-300 rounded text-center font-semibold focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                placeholder="0"
                              />
                              <span className="text-sm text-gray-600 font-medium w-8">marks</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    
                    {/* Total Marks Display with Status */}
                    <div className={`mt-4 p-4 rounded-lg border-2 flex items-center justify-between font-semibold ${
                      totalAllocated === totalMarks
                        ? 'bg-green-50 border-green-300'
                        : totalAllocated > totalMarks
                        ? 'bg-red-50 border-red-300'
                        : 'bg-yellow-50 border-yellow-300'
                    }`}>
                      <span className="text-gray-900">
                        Total Marks Allocated
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`text-2xl font-bold ${
                          totalAllocated === totalMarks
                            ? 'text-green-600'
                            : totalAllocated > totalMarks
                            ? 'text-red-600'
                            : 'text-yellow-600'
                        }`}>
                          {totalAllocated}
                        </span>
                        <span className="text-gray-600">/</span>
                        <span className="text-2xl font-bold text-gray-900">
                          {totalMarks}
                        </span>
                      </div>
                    </div>
                    
                    {/* Status Messages */}
                    {totalAllocated < totalMarks && (
                      <p className="mt-2 text-sm text-yellow-700 bg-yellow-50 p-2 rounded">
                        âš ï¸ {totalMarks - totalAllocated} marks remaining. Please allocate all marks.
                      </p>
                    )}
                    {totalAllocated > totalMarks && (
                      <p className="mt-2 text-sm text-red-700 bg-red-50 p-2 rounded">
                        âŒ {totalAllocated - totalMarks} marks over the limit. Please reduce.
                      </p>
                    )}
                    {totalAllocated === totalMarks && (
                      <p className="mt-2 text-sm text-green-700 bg-green-50 p-2 rounded">
                        âœ… All marks allocated correctly!
                      </p>
                    )}
                  </div>
                )}

                {/* Navigation Buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={() => handleStepChange(1)}
                    className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-900 font-semibold py-3 px-4 rounded-lg transition"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleBackToHome}
                    className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-900 font-semibold py-3 px-4 rounded-lg transition"
                  >
                    Home
                  </button>
                  <button
                    disabled={selectedChapters.length === 0 || totalAllocated !== totalMarks}
                    onClick={handleGeneratePaper}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-lg transition"
                    title={totalAllocated !== totalMarks ? `Please allocate exactly ${totalMarks} marks` : ''}
                  >
                    Generate Paper
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
