import Link from 'next/link';

/**
 * Special card for "Craft a Paper" with a background wallpaper
 * and an image icon displayed inside.
 */
export default function CraftAPaperCard() {
  return (
    <Link
      href="/craft-a-paper"
      className="group relative rounded-xl border border-gray-200 overflow-hidden text-center shadow-sm transition hover:-translate-y-0.5 hover:border-gray-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-gray-400 min-h-[70vh] lg:min-h-[90vh] flex flex-col justify-between"
      style={{
        backgroundImage: 'url(/craft-paper-bg.png)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-black/40" />

      {/* Content container - flexbox to center and space items */}
      <div className="relative z-10 flex flex-col items-center justify-center gap-6 px-6 py-12 h-full">
        {/* Title */}
        <h2 className="text-2xl font-semibold text-white group-hover:text-gray-100 flex-shrink-0">
          Craft a Paper
        </h2>

        {/* Description */}
        <p className="text-sm text-gray-100 flex-shrink-0">
          Generate a new assessment paper from your criteria.
        </p>
      </div>
    </Link>
  );
}
