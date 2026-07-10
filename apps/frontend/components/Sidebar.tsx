export default function Sidebar() {
  return (
    <aside className="w-64 min-h-screen border-r bg-white p-6">

      <h1 className="text-2xl font-bold mb-8">
        SubstationOS
      </h1>

      <nav className="space-y-4">

        <a href="/">
          📁 Projects
        </a>

        <a href="/documents">
          📄 Documents
        </a>

        <a href="/agents/drawing">
          🤖 AI Drawing Agent
        </a>

        <a href="/agents/checker">
          🔍 Checker Agent
        </a>

        <a href="/settings">
          ⚙ Settings
        </a>

      </nav>

    </aside>
  );
}