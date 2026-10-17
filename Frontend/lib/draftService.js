/**
 * Draft Service (client-side)
 * ===========================
 *
 * A thin layer over localStorage + the drafts API that implements the
 * "hybrid" persistence strategy:
 *
 *   1. Writes go to localStorage IMMEDIATELY (instant, survives refresh, works offline).
 *   2. The same data is synced to the backend in the background (multi-device, durable).
 *
 * On load we prefer localStorage for instant restore, then reconcile with the
 * backend. Conflicts use last-write-wins based on `updatedAt`.
 */

import { createDraft, updateDraft, getDraft } from './api';

const LOCAL_KEY = 'craftPaper:currentDraft';
const SESSION_KEY_PREFIX = 'craftPaper:session:';

/**
 * Read the locally cached draft (or null).
 */
export function readLocalDraft() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(LOCAL_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * Read a specific session from localStorage
 */
export function readLocalSession(draftId) {
  if (typeof window === 'undefined') return null;
  try {
    const key = `${SESSION_KEY_PREFIX}${draftId}`;
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (err) {
    console.warn(`Error reading session ${draftId}:`, err);
    return null;
  }
}

/**
 * Write the draft to localStorage. `syncStatus` tracks backend sync state.
 * @param {Object} draft - form state + metadata (draftId, syncStatus, updatedAt)
 */
export function writeLocalDraft(draft) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(draft));
  } catch (e) {
    console.warn('Failed to write local draft:', e);
  }
}

/**
 * Write a session to localStorage
 */
export function writeLocalSession(session) {
  if (typeof window === 'undefined') return;
  try {
    if (!session || !session.draftId) return;
    const key = `${SESSION_KEY_PREFIX}${session.draftId}`;
    localStorage.setItem(key, JSON.stringify(session));
  } catch (e) {
    console.warn('Failed to write local session:', e);
  }
}

/**
 * Clear the locally cached draft (e.g. after starting a brand new paper or deleting).
 */
export function clearLocalDraft() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(LOCAL_KEY);
}

/**
 * Clear a specific session from localStorage
 */
export function clearLocalSession(draftId) {
  if (typeof window === 'undefined') return;
  const key = `${SESSION_KEY_PREFIX}${draftId}`;
  localStorage.removeItem(key);
}

/**
 * Sync form state to the backend.
 *
 * If we already have a draftId, PATCH it. Otherwise POST to create and return
 * the new draftId. Returns { draftId, updatedAt } on success.
 *
 * @param {Object} params
 * @param {string|null} params.draftId
 * @param {Object} params.formData - the fields to persist
 * @param {string} params.userId
 */
export async function syncDraftToBackend({ draftId, formData, userId }) {
  if (draftId) {
    const updated = await updateDraft(draftId, formData, userId);
    return { draftId: updated.draftId, updatedAt: updated.updatedAt };
  }
  const created = await createDraft(formData, userId);
  return { draftId: created.draftId, updatedAt: created.updatedAt };
}

/**
 * Load a draft for resuming.
 *
 * Strategy:
 *   - If an explicit draftId is given (e.g. from ?draftId= or a "Resume" click),
 *     fetch it from the backend (source of truth for a specific draft).
 *   - Otherwise fall back to the locally cached draft.
 *
 * @param {Object} params
 * @param {string|null} params.draftId - explicit draft to load, or null
 * @param {string} params.userId
 * @returns {Promise<Object|null>} draft data or null
 */
export async function loadDraftForResume({ draftId, userId }) {
  if (draftId) {
    const remote = await getDraft(draftId, userId);
    if (remote) return remote;
  }
  return readLocalDraft();
}
