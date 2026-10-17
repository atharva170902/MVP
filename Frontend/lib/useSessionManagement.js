/**
 * useSessionManagement Hook
 * 
 * Manages draft sessions - each draft is a complete, persistent session
 * with all data isolated and preserved independently.
 */

import { useEffect, useRef, useState } from 'react';
import { syncDraftToBackend, readLocalDraft as readLocalSession, writeLocalDraft as writeLocalSession } from './draftService';
import { getDraft, updateDraft, createDraft } from './api';

// Fixed per-question marks mapping (by section).
// q1-q4 = 1 mark MCQ, q5-q6 = 2, q7 = 3, q8 = 5, q9 = 4.
const QUESTION_MARKS = {
  q1: 1, q2: 1, q3: 1, q4: 1,
  q5: 2, q6: 2,
  q7: 3,
  q8: 5,
  q9: 4,
};

/**
 * Enrich each question entry with explicit `marks` and a `generation_model`
 * routing field so the stored object is self-describing. Keeps the existing
 * { chapter, domain, images } keys intact (the resume selectors depend on
 * them) and only ADDS marks + generation_model.
 *
 * Routing: a question WITH a selected diagram (non-empty images) -> "qwen-vl";
 * WITHOUT -> "sonnet-4.5".
 */
function enrichQuestionPaper(questionPaper) {
  if (!questionPaper || typeof questionPaper !== 'object') return questionPaper;

  const enriched = {};
  for (const [key, entry] of Object.entries(questionPaper)) {
    if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
      const images = Array.isArray(entry.images) ? entry.images : [];
      enriched[key] = {
        ...entry,
        marks: QUESTION_MARKS[key] ?? entry.marks ?? 0,
        generation_model: images.length > 0 ? 'qwen-vl' : 'sonnet-4.5',
      };
    } else {
      enriched[key] = entry;
    }
  }
  return enriched;
}

export function useSessionManagement({ userId }) {
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [sessionCache, setSessionCache] = useState({});
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  
  const autoSaveIntervalRef = useRef(null);
  
  /**
   * Get the current active session
   */
  const getCurrentSession = () => {
    if (!currentSessionId) return null;
    return sessionCache[currentSessionId] || null;
  };
  
  /**
   * Load a session by ID from backend/localStorage
   */
  const loadSession = async (draftId) => {
    setSessionLoading(true);
    try {
      // Check cache first
      if (sessionCache[draftId]) {
        console.log('Session loaded from cache:', draftId);
        setCurrentSessionId(draftId);
        setSessionLoading(false);
        return sessionCache[draftId];
      }
      
      // Try backend
      let session = await getDraft(draftId, userId);
      
      // Try localStorage fallback
      if (!session) {
        const localSession = readLocalSession();
        if (localSession && localSession.draftId === draftId) {
          session = localSession;
          console.log('Session loaded from localStorage:', draftId);
        }
      } else {
        console.log('Session loaded from backend:', draftId);
      }
      
      if (session) {
        // Add to cache
        setSessionCache(prev => ({
          ...prev,
          [draftId]: session
        }));
        setCurrentSessionId(draftId);
        setUnsavedChanges(false);
        setSessionLoading(false);
        return session;
      }
      
      setSessionLoading(false);
      return null;
    } catch (err) {
      console.error('Error loading session:', err);
      setSessionLoading(false);
      return null;
    }
  };
  
  /**
   * Create a new session
   */
  const createSession = async (initialData) => {
    try {
      setSessionLoading(true);
      
      // Create new session object
      const newSession = {
        ...initialData,
        userId,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        syncStatus: 'pending',
        
        // Initialize all fields (step by step)
        step: initialData.step || 1,
        examType: initialData.examType || 'PT',
        grade: initialData.grade || '',
        subject: initialData.subject || '',
        selectedChapters: initialData.selectedChapters || [],
        marksAllocation: initialData.marksAllocation || {},
        selectedDiagrams: initialData.selectedDiagrams || [],
        
        // Question paper (most important for Step 3)
        questionPaper: {
          q1: { chapter: '', domain: 'R/U', images: [] },
          q2: { chapter: '', domain: 'R/U', images: [] },
          q3: { chapter: '', domain: 'R/U', images: [] },
          q4: { chapter: '', domain: 'R/U', images: [] },
          q5: { chapter: '', domain: 'R/U', images: [] },
          q6: { chapter: '', domain: 'R/U', images: [] },
          q7: { chapter: '', domain: 'R/U', images: [] },
          q8: { chapter: '', domain: 'R/U', images: [] },
          q9: { chapter: '', domain: 'R/U', images: [] },
        }
      };
      
      // Create on backend
      const created = await createDraft(newSession, userId);
      const sessionWithId = { ...newSession, draftId: created.draftId };
      
      // Add to cache
      setSessionCache(prev => ({
        ...prev,
        [created.draftId]: sessionWithId
      }));
      
      setCurrentSessionId(created.draftId);
      setUnsavedChanges(false);
      setSessionLoading(false);
      
      console.log('Session created:', created.draftId);
      return sessionWithId;
    } catch (err) {
      console.error('Error creating session:', err);
      setSessionLoading(false);
      throw err;
    }
  };
  
  /**
   * Switch to a different session
   */
  const switchSession = async (newDraftId) => {
    try {
      // Save current session if unsaved
      if (currentSessionId && unsavedChanges) {
        await saveSession(currentSessionId);
      }
      
      // Load new session
      await loadSession(newDraftId);
      setUnsavedChanges(false);
      console.log('Switched to session:', newDraftId);
    } catch (err) {
      console.error('Error switching session:', err);
      throw err;
    }
  };
  
  /**
   * Update session field (triggers unsaved changes)
   */
  const updateSessionData = (fieldPath, value) => {
    if (!currentSessionId) return;
    
    setSessionCache(prev => {
      const session = { ...prev[currentSessionId] };
      
      // Handle nested paths like "questionPaper.q1.chapter"
      const keys = fieldPath.split('.');
      let current = session;
      
      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) {
          current[keys[i]] = {};
        }
        current = current[keys[i]];
      }
      
      current[keys[keys.length - 1]] = value;
      session.updatedAt = new Date().toISOString();
      
      return {
        ...prev,
        [currentSessionId]: session
      };
    });
    
    setUnsavedChanges(true);
  };
  
  /**
   * Save current session to backend + localStorage
   */
  const saveSession = async (sessionId = currentSessionId) => {
    if (!sessionId) return;
    
    const session = sessionCache[sessionId];
    if (!session) return;
    
    try {
      // Enrich each question with explicit marks + generation_model so the
      // stored object is self-describing (keeps chapter/domain/images intact).
      const enrichedSession = {
        ...session,
        questionPaper: enrichQuestionPaper(session.questionPaper),
      };
      
      // Save to localStorage immediately
      writeLocalSession({
        ...enrichedSession,
        syncStatus: 'pending',
        updatedAt: new Date().toISOString()
      });
      
      // Sync to backend
      await syncDraftToBackend({
        draftId: enrichedSession.draftId,
        formData: enrichedSession,
        userId
      });
      
      // Update cache with synced status
      setSessionCache(prev => ({
        ...prev,
        [sessionId]: {
          ...prev[sessionId],
          syncStatus: 'synced',
          updatedAt: new Date().toISOString()
        }
      }));
      
      console.log('Session saved:', sessionId);
    } catch (err) {
      console.error('Error saving session:', err);
      
      // Even if backend fails, data is in localStorage
      setSessionCache(prev => ({
        ...prev,
        [sessionId]: {
          ...prev[sessionId],
          syncStatus: 'error',
          updatedAt: new Date().toISOString()
        }
      }));
    }
  };
  
  /**
   * Force save all sessions in cache
   */
  const saveAllSessions = async () => {
    const promises = Object.keys(sessionCache).map(sessionId => 
      saveSession(sessionId)
    );
    await Promise.all(promises);
  };
  
  /**
   * Auto-save every 30 seconds if changes
   */
  useEffect(() => {
    autoSaveIntervalRef.current = setInterval(() => {
      if (unsavedChanges && currentSessionId) {
        saveSession(currentSessionId);
        setUnsavedChanges(false);
      }
    }, 30000);
    
    return () => {
      if (autoSaveIntervalRef.current) {
        clearInterval(autoSaveIntervalRef.current);
      }
    };
  }, [unsavedChanges, currentSessionId, sessionCache]);
  
  /**
   * Save before unload
   */
  useEffect(() => {
    const handleBeforeUnload = async () => {
      if (unsavedChanges && currentSessionId) {
        // Save synchronously if possible, or queue for sync
        const session = sessionCache[currentSessionId];
        if (session) {
          writeLocalSession({
            ...session,
            syncStatus: 'pending',
            updatedAt: new Date().toISOString()
          });
        }
      }
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [unsavedChanges, currentSessionId, sessionCache]);
  
  return {
    // State
    currentSessionId,
    currentSession: getCurrentSession(),
    sessionCache,
    unsavedChanges,
    sessionLoading,
    
    // Methods
    loadSession,
    createSession,
    switchSession,
    updateSessionData,
    saveSession,
    saveAllSessions,
    getCurrentSession
  };
}
