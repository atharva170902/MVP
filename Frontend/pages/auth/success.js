// pages/auth/success.js
import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function Success() {
  const router = useRouter();

  useEffect(() => {
    // Mark that a fresh login just happened so the landing page
    // plays the intro animation once. Cleared after it plays.
    try {
      sessionStorage.setItem('gradeJustLoggedIn', 'true');
    } catch (e) {
      // sessionStorage may be unavailable; animation just won't trigger.
    }
    router.replace('/');
  }, [router]);

  return <p>Signing in...</p>;
}
