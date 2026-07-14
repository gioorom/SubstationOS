interface RecentDocument {
  id: number;
  filename: string;
  project: string;
  revision: string;
}

interface RecentDocumentsCardProps {
  documents: RecentDocument[];
}

export default function RecentDocumentsCard({
  documents,
}: RecentDocumentsCardProps) {
  return (
    <section className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            Recent Documents
          </h2>

          <p className="mt-1 text-sm text-muted-foreground">
            Ultimi documenti caricati
          </p>
        </div>

        <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
          {documents.length}
        </span>
      </div>

      {documents.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Nessun documento disponibile.
        </p>
      ) : (
        <div className="space-y-3">
          {documents.map((document) => (
            <div
              key={document.id}
              className="flex items-center justify-between rounded-2xl border border-border bg-white/60 px-4 py-3 transition hover:bg-white"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-foreground">
                  {document.filename}
                </p>

                <p className="text-sm text-muted-foreground">
                  {document.project}
                </p>
              </div>

              <span className="rounded-full bg-secondary px-3 py-1 text-xs font-semibold">
                Rev. {document.revision}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}