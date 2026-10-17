/**
 * useAutoSave Hook
 * ================
 *
 * Watches a piece of form state and persists it:
 *   - Immediately to localStorage (instant, offline-safe).
 *   - Debounced (default 1.5s) to the backend in the background.
 *
 * It manages the draftId lifecycle: the first successful backend sync creates a
 * draft and captures its id, which is reused for subsequent updates.
 *
 * Returns { saveStatus, draftId } where saveStatus is one of:
 *   'idle' | 'saving' | 'saved' | 'error'
 *
 * @param {Object} options
 * @param {Object} options.formData    - The state to persist (plain object).
 * @param {string} options.userId      - Current user id (Cognito sub).
 * @param {string|null} options.initialDraftId - Existing draft id to update, if resuming.
 * @param {boolean} options.enabled     - When false, auto-save is paused (e.g. before hydration).
 * @param {number} options.debounceMs   - Debounce window for backend sync.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

import { syncDraftToBackend, writeLocalDraft } from './draftService';

export function useAutoSave({
  formData,
  userId,
  initialDraftId = null,
  enabled = true,
  debounceMs = 1500,
}) {
  const [saveStatus, setSaveStatus] = useState('idle');
  const [draftId, setDraftId] = useState(initialDraftId);

  // Keep the latest draftId in a ref so the debounced closure always sees it.
  const draftIdRef = useRef(initialDraftId);
  const timeoutRef = useRef(null);
  // Guards against overlapping/racing syncs.
  const inFlightRef = useRef(false);

  // Keep ref in sync when a caller resets the draftId (e.g. resuming a draft).
  useEffect(() => {
    draftIdRef.current = initialDraftId;
    setDraftId(initialDraftId);
  }, [initialDraftId]);

  const runSync = useCallback(
    async (data) => {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      setSaveStatus('saving');
      try {
        const result = await syncDraftToBackend({
          draftId: draftIdRef.current,
          formData: data,
          userId,
        });
        draftIdRef.current = result.draftId;
        setDraftId(result.draftId);

        // Mark the local copy as synced.
        writeLocalDraft({
          ...data,
          draftId: result.draftId,
          syncStatus: 'synced',
          updatedAt: result.updatedAt,
        });
        setSaveStatus('saved');
      } catch (e) {
        console.warn('Auto-save sync failed:', e.message);
        setSaveStatus('error');
      } finally {
        inFlightRef.current = false;
      }
    },
    [userId]
  );

  // IMMEDIATE localStorage save + debounced backend sync
  useEffect(() => {
    if (!enabled || !formData) return;

    // 1) Instant local save (NO DELAY - happens immediately)
    const draftToSave = {
      ...formData,
      draftId: draftIdRef.current,
      syncStatus: 'pending',
      updatedAt: new Date().toISOString(),
    };
    console.log('Auto-saving to localStorage immediately:', Object.keys(draftToSave));
    writeLocalDraft(draftToSave);
    setSaveStatus('saved'); // Immediately mark as saved locally

    // 2) Debounced backend sync (happens after delay).
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setSaveStatus('saving'); // Show "saving" status during backend sync
      runSync(formData);
    }, debounceMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
    // We intentionally depend on a serialized snapshot so any nested change triggers save.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(formData), enabled, debounceMs, runSync]);

  // Force-save before page unload (user navigating away, refreshing, closing tab)
  useEffect(() => {
    if (!enabled) return;

    const handleBeforeUnload = async (event) => {
      // Immediately sync current formData to backend before leaving
      if (formData && draftIdRef.current) {
        try {
          await syncDraftToBackend({
            draftId: draftIdRef.current,
            formData: formData,
            userId: userId,
          });
          console.log('Force-synced draft before unload');
        } catch (e) {
          console.warn('Could not sync before unload:', e.message);
          // Still saved to localStorage, so data is not lost
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, enabled]);

  return { saveStatus, draftId };
}
