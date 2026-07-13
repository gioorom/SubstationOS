interface FilterPanelProps {
  categories: string[];
  projects: string[];
  revisions: string[];

  selectedCategory: string;
  selectedProject: string;
  selectedRevision: string;

  onCategoryChange: (value: string) => void;
  onProjectChange: (value: string) => void;
  onRevisionChange: (value: string) => void;
  onReset: () => void;
}

export default function FilterPanel({
  categories,
  projects,
  revisions,
  selectedCategory,
  selectedProject,
  selectedRevision,
  onCategoryChange,
  onProjectChange,
  onRevisionChange,
  onReset,
}: FilterPanelProps) {
  const hasActiveFilters =
    selectedCategory !== "" ||
    selectedProject !== "" ||
    selectedRevision !== "";

  return (
    <section className="mt-6 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
        <div className="flex-1">
          <label
            htmlFor="category-filter"
            className="mb-2 block text-sm font-medium text-gray-700"
          >
            Categoria
          </label>

          <select
            id="category-filter"
            value={selectedCategory}
            onChange={(event) =>
              onCategoryChange(event.target.value)
            }
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-gray-900 outline-none transition hover:border-gray-300 focus:border-gray-400 focus:ring-4 focus:ring-gray-200/70"
          >
            <option value="">Tutte le categorie</option>

            {categories.map((category) => (
              <option
                key={category}
                value={category}
              >
                {category}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1">
          <label
            htmlFor="project-filter"
            className="mb-2 block text-sm font-medium text-gray-700"
          >
            Progetto
          </label>

          <select
            id="project-filter"
            value={selectedProject}
            onChange={(event) =>
              onProjectChange(event.target.value)
            }
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-gray-900 outline-none transition hover:border-gray-300 focus:border-gray-400 focus:ring-4 focus:ring-gray-200/70"
          >
            <option value="">Tutti i progetti</option>

            {projects.map((project) => (
              <option
                key={project}
                value={project}
              >
                {project}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1">
          <label
            htmlFor="revision-filter"
            className="mb-2 block text-sm font-medium text-gray-700"
          >
            Revisione
          </label>

          <select
            id="revision-filter"
            value={selectedRevision}
            onChange={(event) =>
              onRevisionChange(event.target.value)
            }
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-gray-900 outline-none transition hover:border-gray-300 focus:border-gray-400 focus:ring-4 focus:ring-gray-200/70"
          >
            <option value="">Tutte le revisioni</option>

            {revisions.map((revision) => (
              <option
                key={revision}
                value={revision}
              >
                {revision}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={onReset}
          disabled={!hasActiveFilters}
          className="rounded-xl border border-gray-200 px-5 py-3 font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Reimposta
        </button>
      </div>
    </section>
  );
}