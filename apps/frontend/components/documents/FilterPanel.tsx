"use client";

/**
 * Registry filters.
 *
 * Since Milestone 30.1.3 the options come from the **contract's closed
 * enums**, not from the values that happen to appear on the current page.
 * Deriving them from the page was correct only while the client held the
 * whole registry; with server-side paging it would hide every filter
 * whose matches are on another page.
 */

export interface FilterOption {
  value: string;
  label: string;
}

interface FilterPanelProps {
  categories: FilterOption[];
  formats: FilterOption[];
  scopes: FilterOption[];
  selectedCategory: string;
  selectedFormat: string;
  selectedScope: string;
  onCategoryChange: (value: string) => void;
  onFormatChange: (value: string) => void;
  onScopeChange: (value: string) => void;
  onReset: () => void;
  hasActiveFilters: boolean;
}

const selectClass =
  "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition hover:border-slate-300 focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70";

function Filter({
  id,
  label,
  emptyLabel,
  options,
  value,
  onChange,
}: {
  id: string;
  label: string;
  emptyLabel: string;
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex-1">
      <label
        htmlFor={id}
        className="mb-2 block text-sm font-medium text-slate-700"
      >
        {label}
      </label>

      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={selectClass}
      >
        <option value="">{emptyLabel}</option>

        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function FilterPanel({
  categories,
  formats,
  scopes,
  selectedCategory,
  selectedFormat,
  selectedScope,
  onCategoryChange,
  onFormatChange,
  onScopeChange,
  onReset,
  hasActiveFilters,
}: FilterPanelProps) {
  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
        <Filter
          id="category-filter"
          label="Categoria"
          emptyLabel="Tutte le categorie"
          options={categories}
          value={selectedCategory}
          onChange={onCategoryChange}
        />

        <Filter
          id="format-filter"
          label="Formato"
          emptyLabel="Tutti i formati"
          options={formats}
          value={selectedFormat}
          onChange={onFormatChange}
        />

        <Filter
          id="scope-filter"
          label="Ambito"
          emptyLabel="Tutti gli ambiti"
          options={scopes}
          value={selectedScope}
          onChange={onScopeChange}
        />

        <button
          type="button"
          onClick={onReset}
          disabled={!hasActiveFilters}
          className="rounded-xl border border-slate-200 px-5 py-3 font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Reimposta
        </button>
      </div>
    </section>
  );
}
