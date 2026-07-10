import UploadBox from "@/components/UploadBox";

export default function DocumentsPage() {
  return (
    <main className="p-8">

      <h1 className="text-3xl font-bold">
        Document Management
      </h1>

      <p className="mt-2 text-gray-600">
        Upload and manage substation engineering documents.
      </p>


      <div className="mt-8 grid grid-cols-2 gap-6">


        <div className="border rounded-xl p-6 bg-white">

          <h2 className="text-xl font-semibold">
            📄 PDF Documents
          </h2>

          <p className="mt-2 text-gray-600">
            Functional diagrams, single line diagrams,
            protection schemes and technical documents.
          </p>

        </div>


        <div className="border rounded-xl p-6 bg-white">

          <h2 className="text-xl font-semibold">
            📐 CAD Files
          </h2>

          <p className="mt-2 text-gray-600">
            DWG drawings, CAD libraries and engineering files.
          </p>

        </div>


      </div>


      <div className="mt-8">

        <UploadBox />

      </div>


    </main>
  );
}