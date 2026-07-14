import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardSkeleton() {
  return (
    <main
      aria-busy="true"
      aria-label="Caricamento dashboard"
      className="px-6 py-8 lg:px-10 lg:py-10"
    >
      <section className="rounded-[2rem] border border-white/70 bg-white/68 p-7 shadow-[0_28px_80px_rgba(15,23,42,0.08)] backdrop-blur-2xl lg:p-9">
        <div className="grid gap-8 xl:grid-cols-[1.5fr_0.9fr] xl:items-center">
          <div>
            <Skeleton className="h-7 w-52 rounded-full" />

            <Skeleton className="mt-5 h-12 w-full max-w-xl rounded-2xl" />

            <div className="mt-4 space-y-3">
              <Skeleton className="h-5 w-full max-w-2xl" />
              <Skeleton className="h-5 w-4/5 max-w-xl" />
            </div>

            <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:max-w-2xl">
              <Skeleton className="h-28 rounded-2xl" />
              <Skeleton className="h-28 rounded-2xl" />
            </div>
          </div>

          <Skeleton className="mx-auto aspect-square w-full max-w-md rounded-[2rem]" />
        </div>
      </section>

      <section className="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="rounded-3xl border border-white/70 bg-white/72 p-5 shadow-sm backdrop-blur-2xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="mt-4 h-9 w-20" />
                <Skeleton className="mt-3 h-4 w-32" />
              </div>

              <Skeleton className="h-12 w-12 rounded-2xl" />
            </div>
          </div>
        ))}
      </section>

      <section className="mt-8 grid gap-6 xl:grid-cols-2">
        {Array.from({ length: 2 }).map((_, cardIndex) => (
          <div
            key={cardIndex}
            className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-sm backdrop-blur-2xl"
          >
            <Skeleton className="h-6 w-44" />
            <Skeleton className="mt-2 h-4 w-56" />

            <div className="mt-6 space-y-3">
              {Array.from({ length: 4 }).map((_, rowIndex) => (
                <Skeleton
                  key={rowIndex}
                  className="h-16 rounded-2xl"
                />
              ))}
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}