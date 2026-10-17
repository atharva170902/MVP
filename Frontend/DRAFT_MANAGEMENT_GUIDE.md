# Draft Management Guide - Delete Duplicates Safely

## Why Are There 8 Drafts?

The duplicates likely happened due to:

1. **Backend Test Data** - Previous API testing created multiple draft records
2. **Multiple Auto-saves** - If drafts were saved multiple times without unique IDs
3. **Development/Testing** - Multiple iterations during development created redundant drafts
4. **Session Persistence Issues** - Before session architecture, data might have been saved multiple times

## Deleting Duplicate Drafts - Safely

A new **Delete** button has been added to the drafts list. Here's how to use it:

### Step-by-Step

1. **Go Home** - Click "Home" or "Back to Home" from any step
2. **View Previously Drafted Papers** - See all your drafts (right column)
3. **Hover Over Draft** - Move your mouse over a draft you want to delete
4. **Click Delete Button** - A red "✕ Delete" button appears on hover
5. **Confirm Deletion** - Browser will ask: "Are you sure? This action cannot be undone."
6. **Draft Removed** - The draft is deleted from the backend and list

### What Gets Deleted

```
Deleting a draft removes:
✓ Draft metadata (examType, grade, subject, step)
✓ All questions (Q1-Q9) with chapters, domains, images
✓ Chapter selections and marks allocation
✓ Auto-save history
✗ Cannot be recovered (permanent delete)
```

### Safe Deletion Tips

1. **Don't delete active draft** - Always save/exit before deleting
2. **One at a time** - Delete duplicates individually
3. **Verify metadata** - Check exam type, grade, subject before deleting
4. **Keep current work** - Don't delete the draft you're working on

## How to Identify Duplicates

Look for drafts with:
- Same exam type, grade, subject, step
- Same or similar "Last saved" times
- Incomplete data (0 chapters, no questions)
- From development/testing sessions

Example duplicate pattern:
```
PT • Grade 7 • Science
Step 3
2 chapters selected
Last saved 3 min ago

PT • Grade 7 • Science    ← DUPLICATE
Step 3                     (Same metadata)
2 chapters selected
Last saved 2 min ago
```

## Delete Feature Implementation

### Frontend Changes

**File:** `pages/craft-a-paper.js`

```javascript
// New state
const [deletingDraftId, setDeletingDraftId] = useState(null);

// New handler
const handleDeleteDraft = async (draftId, e) => {
  e.stopPropagation();
  
  // Show confirmation dialog
  if (!window.confirm('Are you sure you want to delete this draft?')) {
    return;
  }
  
  // Call API
  const deleted = await deleteDraft(draftId, userId);
  
  // Update UI
  if (deleted) {
    setDrafts(drafts.filter(d => d.draftId !== draftId));
  }
};

// UI: Delete button appears on hover
<button
  onClick={(e) => handleDeleteDraft(draft.draftId, e)}
  disabled={deletingDraftId === draft.draftId}
  className="... opacity-0 group-hover:opacity-100"
>
  {deletingDraftId === draft.draftId ? 'Deleting...' : '✕ Delete'}
</button>
```

### API Endpoint Used

```
DELETE /api/drafts/{draftId}
Header: X-User-Id: {userId}

Returns: 200 OK if deleted, 404 if not found
```

## Bulk Delete (If Needed)

For removing many duplicates at once:

1. **Contact Backend Team** - Request data cleanup
2. **Use SQL Query** - Backend can run cleanup query:
   ```sql
   -- Example: Delete drafts created during testing
   DELETE FROM drafts 
   WHERE created_at < '2024-01-01' 
   AND user_id = '{userId}'
   AND step < 3;
   ```
3. **Refresh List** - Go home and reload to see updated list

## Future Improvements

- [ ] **Bulk Select** - Checkbox to select multiple drafts for batch delete
- [ ] **Duplicate Detection** - Automatic detection and flagging of identical drafts
- [ ] **Trash/Archive** - Soft delete (recoverable) instead of permanent
- [ ] **Deduplication Tool** - One-click cleanup for duplicates
- [ ] **Edit Draft Name** - Rename drafts for better organization

## Questions?

- **Issue**: Button doesn't appear
  **Solution**: Hover over draft item to reveal delete button
  
- **Issue**: Delete says "Deleting..." forever
  **Solution**: Backend may be offline. Try again or check connection
  
- **Issue**: Deleted draft still appears
  **Solution**: Refresh page or go back to home to reload list

---

**Summary**: You now have safe, manual control to delete duplicate drafts one by one. Each deletion requires confirmation to prevent accidents. ✅
