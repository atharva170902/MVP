import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

import { withAuth } from '../lib/withAuth';
import { listDrafts, deleteDraft } from '../lib/api';
import { timeAgo } from '../lib/formatTime';

export const getServerSideProps = withAuth(async (context) => {
  return { props: { user: context.user || null } };
});

export default function MyDrafts({ user }) {
  const router = useRouter();
  const userId = user?.sub || user?.username || 'dev-user';

  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      const data = await listDrafts(userId);
      if (!cancelled) {
        setDrafts(data);
        setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const handleResume = (draftId) => {
    router.push(`/craft-a-paper?draftId=${encodeURIComponent(draftId)}`);
  };

  const handleDelete = async (draftId) => {
    setDeletingId(draftId);
    try {
      await deleteDraft(draftId, userId);
      setDrafts((prev) => prev.filter((d) => d.draftId !== draftId));
    } catch (e) {
      console.warn('Delete failed:', e);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <>
      <Head>
        <title>My Drafts</title>
      </Head>
      <div className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-4xl px-4 py-10">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <Link href="/" className="text-sm text-gray-500 hover:text-gray-700">
                &larr; Back
              </Link>
              <h1 className="text-2xl font-bold text-gray-900 mt-2">My Drafts</h1>
            </div>
            <Link
              href="/craft-a-paper"
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
            >
              + New Paper
            </Link>
          </div>

          {/* List */}
          {loading ? (
            <div className="p-6 bg-white rounded-xl text-sm text-gray-600 shadow-sm">
              Loading your drafts…
            </div>
          ) : drafts.length === 0 ? (
            <div className="p-10 bg-white rounded-xl text-center shadow-sm">
              <div className="text-4xl mb-3">📝</div>
              <p className="text-gray-700 font-medium">No drafts yet</p>
              <p className="text-sm text-gray-500 mt-1">
                Start crafting a paper and it will be saved here automatically.
              </p>
              <Link
                href="/craft-a-paper"
                className="inline-block mt-5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
              >
                Craft a Paper
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {drafts.map((draft) => (
                <div
                  key={draft.draftId}
                  className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h2 className="text-lg font-semibold text-gray-900 truncate">
                        {draft.title || 'Untitled Paper'}
                      </h2>
                      <p className="text-sm text-gray-500 mt-1">
                        Step {draft.step} of 3 · Updated {timeAgo(draft.updatedAt)}
                        {draft.totalMarks ? ` · ${draft.totalMarks} marks` : ''}
                      </p>

                      {/* Progress bar */}
                      <div className="mt-3 flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden max-w-xs">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all"
                            style={{ width: `${draft.progress || 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">
                          {draft.progress || 0}%
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 shrink-0">
                      <button
                        onClick={() => handleResume(draft.draftId)}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition"
                      >
                        Resume
                      </button>
                      <button
                        onClick={() => handleDelete(draft.draftId)}
                        disabled={deletingId === draft.draftId}
                        className="text-sm text-red-600 hover:text-red-700 font-medium px-4 py-1.5 rounded-lg border border-red-200 hover:bg-red-50 transition disabled:opacity-50"
                      >
                        {deletingId === draft.draftId ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
