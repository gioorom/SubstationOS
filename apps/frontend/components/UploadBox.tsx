"use client";

import { useState } from "react";


export default function UploadBox() {

  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");


  async function uploadFile() {

    if (!file) {
      setMessage("Select a file first");
      return;
    }


    const formData = new FormData();

    formData.append(
      "file",
      file
    );


    try {

      const response = await fetch(
        "http://127.0.0.1:8000/documents/upload",
        {
          method: "POST",
          body: formData,
        }
      );


      const data = await response.json();


      setMessage(
        `Uploaded: ${data.filename}`
      );


    } catch (error) {

      setMessage(
        "Upload failed"
      );

    }

  }



  return (

    <div className="border rounded-xl p-6">


      <h2 className="text-xl font-semibold">
        Upload Engineering Documents
      </h2>


      <input
        type="file"
        className="mt-4"
        onChange={(e) =>
          setFile(
            e.target.files?.[0] || null
          )
        }
      />


      {file && (

        <p className="mt-3 text-gray-600">
          Selected: {file.name}
        </p>

      )}


      <button
        onClick={uploadFile}
        className="mt-4 px-4 py-2 rounded bg-black text-white"
      >
        Upload
      </button>


      {message && (

        <p className="mt-4">
          {message}
        </p>

      )}


    </div>

  );
}