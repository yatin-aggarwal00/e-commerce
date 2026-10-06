import Link from "next/link";

export function Pagination({
  page,
  total,
  pageSize,
  makeHref,
}: {
  page: number;
  total: number;
  pageSize: number;
  makeHref: (page: number) => string;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;

  return (
    <nav className="mt-8 flex items-center justify-center gap-2" aria-label="Pagination">
      {page > 1 && (
        <Link href={makeHref(page - 1)} className="btn-secondary">
          Previous
        </Link>
      )}
      <span className="px-3 text-sm text-brand-500">
        Page {page} of {pages}
      </span>
      {page < pages && (
        <Link href={makeHref(page + 1)} className="btn-secondary">
          Next
        </Link>
      )}
    </nav>
  );
}
