"use client";

import { useEffect, useState } from "react";

interface Document {
  id: number;
  filename: string;
  category: string | null;
  project: string | null;
  revision: string | null;
  uploaded_at: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/documents/")
      .then((response) => response.json())
      .then((data) => setDocuments(data))
      .catch((error) => console.error(error));
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold mb-6">Document Registry</h1>

      <table className="w-full border-collapse border border-gray-300">
        <thead>
          <tr className="bg-gray-100 text-black">
            <th className="border p-3 text-left">Filename</th>
            <th className="border p-3 text-left">Category</th>
            <th className="border p-3 text-left">Project</th>
            <th className="border p-3 text-left">Revision</th>
          </tr>
        </thead>

        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td className="border p-3">{doc.filename}</td>
              <td className="border p-3">{doc.category ?? "-"}</td>
              <td className="border p-3">{doc.project ?? "-"}</td>
              <td className="border p-3">{doc.revision ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}