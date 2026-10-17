// pages/_app.js
import Head from "next/head";
import "../styles/globals.css";

export default function MyApp({ Component, pageProps }) {
  return (
    <>
      <Head>
        <title>Assessment Drafting Engine</title>
      </Head>
      <main className="p-6">
        <Component {...pageProps} />
      </main>
    </>
  );
}
