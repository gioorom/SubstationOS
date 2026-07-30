interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
}

export default function SearchBar({
  value,
  onChange,
}: SearchBarProps) {
  return (
    <div className="mt-8">
      <label
        htmlFor="document-search"
        className="mb-2 block text-sm font-medium text-gray-700"
      >
        Cerca documento
      </label>

      <div className="relative">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-gray-400"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
        </div>

        <input
          id="document-search"
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Cerca per nome file o progetto..."
          autoComplete="off"
          className="w-full rounded-2xl border border-gray-200 bg-white py-3.5 pr-12 pl-12 text-gray-900 shadow-sm outline-none transition duration-200 placeholder:text-gray-400 hover:border-gray-300 focus:border-gray-400 focus:ring-4 focus:ring-gray-200/70"
        />

        {value && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Cancella ricerca"
            className="absolute inset-y-0 right-0 flex items-center pr-4 text-gray-400 transition hover:text-gray-700"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}