import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';

import { withAuth } from '../lib/withAuth';
import WelcomeAnimation from '../components/WelcomeAnimation';
import ProfileMenu from '../components/ProfileMenu';
import CraftAPaperCard from '../components/CraftAPaperCard';

const SECTIONS = [
  {
    title: 'Craft a Paper',
    description: 'Generate a new assessment paper from your criteria.',
    href: '/craft-a-paper',
  },
  {
    title: 'Review previous Papers',
    description: 'Browse and revisit papers you created earlier.',
    href: '/review-papers',
  },
  {
    title: 'Create Question Bank',
    description: 'Build and organize a reusable bank of questions.',
    href: '/question-bank',
  },
  {
    title: 'User Management',
    description: 'Manage users, roles, and access.',
    href: '/user-management',
  },
  {
    title: 'Update the KB',
    description: 'Add or update the knowledge base content.',
    href: '/update-kb',
  },
];

export const getServerSideProps = withAuth(async (context) => {
  const isAuthenticated = context.user ? true : false;
  const user = context.user || null;

  return {
    props: {
      isAuthenticated,
      user,
    },
  };
});

export default function Home({ isAuthenticated, user }) {
  const [showWelcome, setShowWelcome] = useState(false);

  const userId = user?.sub || user?.username || 'dev-user';

  useEffect(() => {
    if (!isAuthenticated) return;
    // Play the intro only right after a fresh login. The flag is set by
    // /auth/success and consumed here so refreshes don't replay it.
    try {
      if (sessionStorage.getItem('gradeJustLoggedIn') === 'true') {
        sessionStorage.removeItem('gradeJustLoggedIn');
        setShowWelcome(true);
      }
    } catch (e) {
      // sessionStorage unavailable; skip the animation.
    }
  }, [isAuthenticated]);

  const handleWelcomeFinish = () => {
    setShowWelcome(false);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-blue-600 mb-4">
            Atharva&apos;s MVP
          </h1>
          <p className="text-gray-600 mb-8">Please log in to continue.</p>
          <a
            href={process.env.NEXT_PUBLIC_LOGIN_URL || '/api/auth/login'}
            className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium"
          >
            Login
          </a>
        </div>
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>Assessment Drafting Engine</title>
        <meta
          name="description"
          content="Generative Rubric & Assessment Drafting Engine"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      {showWelcome && <WelcomeAnimation onFinish={handleWelcomeFinish} />}

      <div className="min-h-screen bg-gray-50">
        {/* Top-right profile avatar with dropdown (email + Logout) */}
        <ProfileMenu email={user?.email} />

        <div className="mx-auto max-w-7xl px-4 py-16 sm:py-24">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 lg:gap-6">
            {/* Craft a Paper card */}
            <CraftAPaperCard />

            {/* Other 4 cards - same height as Craft a Paper */}
            {SECTIONS.slice(1).map((section) => (
              <Link
                key={section.href}
                href={section.href}
                className="group flex flex-col justify-center items-center rounded-xl border border-gray-200 bg-white p-8 min-h-[70vh] lg:min-h-[90vh] text-center shadow-sm transition hover:-translate-y-0.5 hover:border-gray-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-gray-400"
              >
                <h2 className="text-xl font-semibold text-gray-900 group-hover:text-gray-700">
                  {section.title}
                </h2>
                <p className="mt-3 text-sm text-gray-500">
                  {section.description}
                </p>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
