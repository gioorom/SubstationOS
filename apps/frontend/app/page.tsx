import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import DashboardCard from "@/components/DashboardCard";


export default function Home() {

  return (
    <main className="flex min-h-screen">

      <Sidebar />

      <section className="flex-1">

        <Header />

        <div className="p-8">

          <h1 className="text-3xl font-bold">
            SubstationOS Dashboard
          </h1>

          <p className="mt-2 text-gray-600">
            Electrical engineering AI workspace
          </p>


          <div className="grid grid-cols-3 gap-6 mt-8">

            <DashboardCard
              title="Projects"
              value="0"
              icon="📁"
            />

            <DashboardCard
              title="Documents"
              value="0"
              icon="📄"
            />

            <DashboardCard
              title="AI Agents"
              value="2"
              icon="🤖"
            />

          </div>


        </div>

      </section>

    </main>
  );
}