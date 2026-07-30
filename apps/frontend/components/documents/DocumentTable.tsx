import Link from "next/link";

import {
  DOCUMENT_CATEGORY_LABELS,
  DOCUMENT_FORMAT_LABELS,
  type DocumentSummary,
} from "@/lib/contracts";

interface DocumentTableProps {
  documents: DocumentSummary[];
}

/**
 * `file_path` is deliberately not rendered. It is a server-side storage
 * location, and the frontend must not know where the backend keeps its
 * files - nor could a user do anything with it, since the API exposes no
 * download endpoint.
 */
export default function DocumentTable({
  documents,
}: DocumentTableProps) {
  return (
    <div className="mt-8 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-slate-50 text-slate-700">
          <tr>
            <th className="p-4 text-left font-semibold">Documento</th>
            <th className="p-4 text-left font-semibold">Formato</th>
            <th className="p-4 text-left font-semibold">Categoria</th>
            <th className="p-4 text-left font-semibold">Progetto</th>
            <th className="p-4 text-left font-semibold">Revisione</th>
            <th className="p-4 text-left font-semibold">Caricato il</th>
            <th className="p-4 text-left font-semibold">Pipeline</th>
          </tr>
        </thead>

        <tbody>
          {documents.map((document) => (
            <tr
              key={document.id}
              className="border-t border-slate-100 transition hover:bg-slate-50"
            >
              <td className="p-4 font-medium text-slate-900">
                {document.filename}
              </td>

              <td className="p-4 text-slate-600">
                {DOCUMENT_FORMAT_LABELS[document.file_format] ??
                  document.file_format}
              </td>

              <td className="p-4 text-slate-600">
                {DOCUMENT_CATEGORY_LABELS[document.category] ??
                  document.category}
              </td>

              <td className="p-4 text-slate-600">
                {document.project_name}
              </td>

              <td className="p-4 text-slate-600">
                {document.revision}
              </td>

              <td className="p-4 text-slate-500">
                {new Date(document.uploaded_at).toLocaleString("it-IT")}
              </td>

              <td className="p-4">
                <div className="flex flex-wrap gap-3">
                  {/*
                    Two destinations for two questions: the Workspace
                    answers what was extracted and why, the pipeline
                    answers whether the stages ran.
                  */}
                  <Link
                    href={`/documents/${document.id}/workspace`}
                    className="font-medium text-primary hover:underline"
                  >
                    Apri workspace
                  </Link>

                  <Link
                    href={`/documents/${document.id}/pipeline`}
                    className="font-medium text-muted-foreground hover:underline"
                  >
                    Pipeline
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
