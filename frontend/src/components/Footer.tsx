export function Footer() {
  return (
    <footer className="mt-16 border-t border-brand-100 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-brand-500">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p>© {new Date().getFullYear()} Haus&amp;Home Furniture. Demo store.</p>
          <p>Free standard shipping on orders over $500.</p>
        </div>
      </div>
    </footer>
  );
}
