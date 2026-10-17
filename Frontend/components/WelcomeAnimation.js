import { useEffect, useState } from 'react';

const LOGO_TEXT = 'G.R.A.D.E';

/**
 * Netflix-style intro shown right after login.
 * The logo starts small and dim, zooms up toward the viewer while a
 * bright shine sweeps across it, then the whole overlay fades out and
 * calls onFinish to reveal the app.
 */
export default function WelcomeAnimation({ onFinish }) {
  const [dismiss, setDismiss] = useState(false);

  useEffect(() => {
    // Begin the overlay fade-out once the zoom has finished.
    const dismissTimer = setTimeout(() => setDismiss(true), 3000);
    // Remove the overlay after the fade-out completes.
    const finishTimer = setTimeout(() => onFinish?.(), 3700);

    return () => {
      clearTimeout(dismissTimer);
      clearTimeout(finishTimer);
    };
  }, [onFinish]);

  return (
    <div
      className={`grade-overlay${dismiss ? ' grade-overlay--dismiss' : ''}`}
      role="status"
      aria-label="Welcome to G.R.A.D.E, Generative Rubric and Assessment Drafting Engine"
    >
      <div className="grade-logo-wrap">
        <span className="grade-logo" data-text={LOGO_TEXT} aria-hidden="true">
          {LOGO_TEXT}
        </span>

        <p className="grade-fullname">
          Generative Rubric &amp; Assessment Drafting Engine
        </p>
      </div>
    </div>
  );
}
