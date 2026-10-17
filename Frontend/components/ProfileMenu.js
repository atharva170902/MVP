import { useEffect, useRef, useState } from 'react';

/**
 * Clickable profile avatar in the top-right corner.
 * Clicking the avatar toggles a dropdown showing the user's email
 * and a Logout link. Closes when clicking outside or pressing Escape.
 */
export default function ProfileMenu({ email }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const handleEsc = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEsc);
    };
  }, [open]);

  // First letter of the email as the avatar label.
  const initial = email ? email.charAt(0).toUpperCase() : '?';

  return (
    <div className="fixed top-4 right-4 z-20" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-800 text-white font-semibold hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-400 shadow"
      >
        {initial}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-56 rounded-lg border border-gray-200 bg-white shadow-lg overflow-hidden">
          {email && (
            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-xs text-gray-500">Signed in as</p>
              <p className="text-sm font-medium text-gray-800 truncate">
                {email}
              </p>
            </div>
          )}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a
            href="/api/auth/logout"
            className="block px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
          >
            Logout
          </a>
        </div>
      )}
    </div>
  );
}
