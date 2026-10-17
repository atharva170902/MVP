import Head from 'next/head';
import Link from 'next/link';

import { withAuth } from '../lib/withAuth';

export const getServerSideProps = withAuth(async () => {
  return { props: {} };
});

export default function ReviewPapers() {
  return (
    <>
      <Head>
        <title>Review previous Papers</title>
      </Head>
      <div className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-5xl px-4 py-10">
          <Link href="/" className="text-sm text-gray-500 hover:text-gray-700">
            &larr; Back
          </Link>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">
            Review previous Papers
          </h1>
        </div>
      </div>
    </>
  );
}
