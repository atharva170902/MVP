/**
 * API helper functions for fetching grades, subjects, and chapters
 * from the backend catalog listing API.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  console.warn('NEXT_PUBLIC_API_URL is not set in environment variables');
}

/**
 * Check if backend is running by making a simple test request
 * @returns {Promise<boolean>} true if backend is reachable
 */
export async function isBackendRunning() {
  try {
    if (!API_URL) return false;
    const response = await fetch(`${API_URL}/grades`, { 
      method: 'GET',
      timeout: 3000 
    });
    return response.ok || response.status < 500;
  } catch (_err) {
    return false;
  }
}

/**
 * Fetch all available grades
 * @returns {Promise<string[]>} Array of grade names
 */
export async function getGrades() {
  try {
    if (!API_URL) {
      throw new Error('API_URL not configured');
    }
    const response = await fetch(`${API_URL}/grades`, { timeout: 5000 });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data.grades || [];
  } catch (error) {
    console.warn('Error fetching grades (backend may not be running):', error.message);
    // Return mock data for development when backend is offline
    return ['Grade 7', 'Grade 8', 'Grade 9'];
  }
}

/**
 * Fetch subjects for a specific grade
 * @param {string} grade - The grade name (e.g., "Grade 7")
 * @returns {Promise<string[]>} Array of subject names
 */
export async function getSubjects(grade) {
  try {
    if (!API_URL) {
      throw new Error('API_URL not configured');
    }
    const encodedGrade = encodeURIComponent(grade);
    const response = await fetch(`${API_URL}/grades/${encodedGrade}/subjects`, { timeout: 5000 });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data.subjects || [];
  } catch (error) {
    console.warn(`Error fetching subjects for grade ${grade} (backend may not be running):`, error.message);
    // Return mock data for development when backend is offline
    return ['Science', 'Mathematics', 'English', 'Social Studies'];
  }
}

/**
 * Fetch chapters for a specific grade and subject
 * @param {string} grade - The grade name (e.g., "Grade 7")
 * @param {string} subject - The subject name (e.g., "Science")
 * @returns {Promise<Object[]>} Array of chapter objects with id, order, title, folder
 */
export async function getChapters(grade, subject) {
  try {
    if (!API_URL) {
      throw new Error('API_URL not configured');
    }
    const encodedGrade = encodeURIComponent(grade);
    const encodedSubject = encodeURIComponent(subject);
    const response = await fetch(
      `${API_URL}/grades/${encodedGrade}/subjects/${encodedSubject}/chapters`,
      { timeout: 5000 }
    );
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    // Sort by order as a client-side safety net
    const chapters = data.chapters || [];
    return chapters.sort((a, b) => (a.order || 0) - (b.order || 0));
  } catch (error) {
    console.warn(
      `Error fetching chapters for ${grade}/${subject} (backend may not be running):`,
      error.message
    );
    // Return mock chapters for development when backend is offline
    return [
      { id: 'ch_01', order: 1, title: 'Chapter 1: Introduction', folder: 'Ch01_Introduction' },
      { id: 'ch_02', order: 2, title: 'Chapter 2: Nutrition in Plants', folder: 'Ch02_Nutrition_in_Plants' },
      { id: 'ch_03', order: 3, title: 'Chapter 3: Nutrition in Animals', folder: 'Ch03_Nutrition_in_Animals' },
      { id: 'ch_04', order: 4, title: 'Chapter 4: Heat and Transfer', folder: 'Ch04_Heat_and_Transfer' },
    ];
  }
}

/**
 * Fetch diagrams for a chapter from backend API
 * @param {string} grade - The grade name (e.g., "Grade 7")
 * @param {string} subject - The subject name (e.g., "Science")
 * @param {string} folder - The chapter folder name from API (e.g., "Ch01_Nutrition_in_Plants")
 * @returns {Promise<Object[]>} Array of diagram objects with key, name, url
 */
export async function getDiagrams(grade, subject, folder) {
  try {
    if (!API_URL) {
      console.warn('API_URL not configured');
      return [];
    }

    const encodedGrade = encodeURIComponent(grade);
    const encodedSubject = encodeURIComponent(subject);
    const encodedFolder = encodeURIComponent(folder);
    
    const url = `${API_URL}/diagrams?grade=${encodedGrade}&subject=${encodedSubject}&folder=${encodedFolder}`;
    console.log('Fetching diagrams from backend:', url);
    
    // Call backend endpoint to get diagrams with presigned URLs
    const response = await fetch(url);
    
    if (!response.ok) {
      console.warn(`Backend returned ${response.status}: ${response.statusText}`);
      return [];
    }
    
    const data = await response.json();
    const diagrams = data.diagrams || [];
    
    console.log(`Found ${diagrams.length} diagrams for ${grade}/${subject}/${folder}`);
    return diagrams;
  } catch (error) {
    console.warn(
      `Error fetching diagrams for ${grade}/${subject}/${folder}:`,
      error.message
    );
    return [];
  }
}

// ============================================================================
// DRAFTS API (question-paper auto-save / persistence)
// ============================================================================
//
// DEV-MODE AUTH: we pass the current user's id in the `X-User-Id` header. The
// backend trusts this header in development (no JWT verification). In production
// this should be replaced with an `Authorization: Bearer <id_token>` header and
// server-side Cognito verification.

/**
 * Build request headers for draft calls, including the dev-mode user id.
 * @param {string} [userId]
 */
function draftHeaders(userId) {
  const headers = { 'Content-Type': 'application/json' };
  if (userId) {
    headers['X-User-Id'] = userId;
  }
  return headers;
}

/**
 * Create a new draft.
 * @param {Object} draftData - Draft form state (step, examType, grade, subject, selectedChapters, marksAllocation, selectedDiagrams, totalMarks)
 * @param {string} userId - Current user id (Cognito sub)
 * @returns {Promise<Object>} The created draft record (includes draftId)
 */
export async function createDraft(draftData, userId) {
  const response = await fetch(`${API_URL}/api/drafts`, {
    method: 'POST',
    headers: draftHeaders(userId),
    body: JSON.stringify(draftData),
  });
  if (!response.ok) {
    throw new Error(`Failed to create draft: ${response.status}`);
  }
  return response.json();
}

/**
 * Update an existing draft (partial). Used by auto-save.
 * @param {string} draftId
 * @param {Object} updates - Only the fields that changed
 * @param {string} userId
 * @returns {Promise<Object>} The updated draft record
 */
export async function updateDraft(draftId, updates, userId) {
  const response = await fetch(`${API_URL}/api/drafts/${draftId}`, {
    method: 'PATCH',
    headers: draftHeaders(userId),
    body: JSON.stringify(updates),
  });
  if (!response.ok) {
    throw new Error(`Failed to update draft: ${response.status}`);
  }
  return response.json();
}

/**
 * List the current user's drafts (summaries).
 * @param {string} userId
 * @returns {Promise<Object[]>} Array of draft summaries
 */
export async function listDrafts(userId) {
  try {
    const response = await fetch(`${API_URL}/api/drafts`, {
      headers: draftHeaders(userId),
    });
    if (!response.ok) {
      throw new Error(`Failed to list drafts: ${response.status}`);
    }
    const data = await response.json();
    return data.drafts || [];
  } catch (error) {
    console.warn('Error listing drafts:', error.message);
    return [];
  }
}

/**
 * Fetch a single draft by id.
 * @param {string} draftId
 * @param {string} userId
 * @returns {Promise<Object|null>} The draft, or null if not found
 */
export async function getDraft(draftId, userId) {
  try {
    const response = await fetch(`${API_URL}/api/drafts/${draftId}`, {
      headers: draftHeaders(userId),
    });
    if (response.status === 404) return null;
    if (!response.ok) {
      throw new Error(`Failed to get draft: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.warn(`Error getting draft ${draftId}:`, error.message);
    return null;
  }
}

/**
 * Delete a draft by id.
 * @param {string} draftId
 * @param {string} userId
 * @returns {Promise<boolean>} true if deleted
 */
export async function deleteDraft(draftId, userId) {
  const response = await fetch(`${API_URL}/api/drafts/${draftId}`, {
    method: 'DELETE',
    headers: draftHeaders(userId),
  });
  return response.ok;
}

// ============================================================================
// AI QUESTION-PAPER GENERATION API (async job: start + poll)
// ============================================================================

/**
 * Start an AI question-paper generation job for a draft.
 * @param {string} draftId - The draft id to generate from
 * @param {string} userId - Current user id (dev-mode X-User-Id)
 * @returns {Promise<Object>} The job handle { jobId, status }
 */
export async function startGeneration(draftId, userId) {
  const response = await fetch(`${API_URL}/api/generate`, {
    method: 'POST',
    headers: draftHeaders(userId),
    body: JSON.stringify({ draftId }),
  });
  if (!response.ok) {
    throw new Error(`Failed to start generation: ${response.status}`);
  }
  return response.json(); // { jobId, status }
}

/**
 * Poll the status/snapshot of a generation job.
 * @param {string} jobId
 * @param {string} userId
 * @returns {Promise<Object|null>} The job snapshot, or null if not found (404)
 */
export async function getGenerationStatus(jobId, userId) {
  const response = await fetch(`${API_URL}/api/generate/${jobId}`, {
    headers: draftHeaders(userId),
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Failed to get generation status: ${response.status}`);
  }
  return response.json(); // snapshot
}
