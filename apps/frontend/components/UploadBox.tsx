"use client";

import { useState } from "react";


export default function UploadBox() {

  const [file, setFile] = useState<File | null>(null);


  return (
    <div className="border rounded-xl p-6">

      <h2 className="text-xl font-semibold">
        Upload Engineering Documents
      </h2>


      <input
        type="file"
        className="mt-4"
        onChange={(e) =>
          setFile(e.target.files?.[0] || null)
        }
      />


      {file && (
        <p className="mt-4 text-gray-600">
          Selected: {file.name}
        </p>
      )}


      <button
        className="mt-4 px-4 py-2 rounded bg-black text-white"
      >
        Upload
      </button>


    </div>
  );
}