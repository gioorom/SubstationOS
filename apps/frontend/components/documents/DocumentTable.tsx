import { Document } from "@/types/document";

interface DocumentTableProps {
  documents: Document[];
}

export default function DocumentTable({
  documents,
}: DocumentTableProps) {
  return (
    <div className="mt-8 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full border-collapse">
        <thead className="bg-gray-50 text-gray-700">
          <tr>
            <th className="p-4 text-left font-semibold">
              Filename
            </th>

            <th className="p-4 text-left font-semibold">
              Categoria
            </th>

            <th className="p-4 text-left font-semibold">
              Progetto
            </th>

            <th className="p-4 text-left font-semibold">
              Revisione
            </th>

            <th className="p-4 text-left font-semibold">
              Caricato il
            </th>
          </tr>
        </thead>

        <tbody>
          {documents.map((document) => (
            <tr
              key={document.id}
              className="border-t border-gray-100 transition hover:bg-gray-50"
            >
              <td className="p-4 font-medium text-gray-900">
                {document.filename}
              </td>

              <td className="p-4 text-gray-600">
                {document.category}
              </td>

              <td className="p-4 text-gray-600">
                {document.project}
              </td>

              <td className="p-4 text-gray-600">
                {document.revision}
              </td>

              <td className="p-4 text-gray-500">
                {new Date(
                  document.uploaded_at
                ).toLocaleString("it-IT")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}