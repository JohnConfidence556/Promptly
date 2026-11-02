import { useState } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";

import ChatPanel from "../components/workspace/ChatPanel";
import RightPane from "../components/workspace/RightPane";
import WorkspaceHeader from "../components/workspace/WorkspaceHeader";
import Button from "../components/ui/Button";
import { useSession } from "../lib/session";
import { useWorkspace } from "../lib/workspace";
import { downloadZip } from "../lib/zip";

export default function Workspace() {
  const { projectId: paramId = "new" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { session } = useSession();
  const prompt = (location.state as { prompt?: string } | null)?.prompt;

  const workspace = useWorkspace(paramId, session?.token ?? "", prompt);
  const [panel, setPanel] = useState<"chat" | "preview">("chat");
  const [downloading, setDownloading] = useState(false);

  if (paramId === "new" && !prompt) return <Navigate to="/home" replace />;

  const { project, selected, version, error, live, stream } = workspace;
  const versions = project?.versions ?? [];
  const title = project?.title ?? "New project";
  const building = stream.status === "running";

  if (error && !project && !live) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
        <p role="alert" className="text-ink-200">
          {error}
        </p>
        <Button variant="secondary" onClick={() => navigate("/home")}>
          Back to your projects
        </Button>
      </div>
    );
  }

  async function handleDownload() {
    if (!version) return;

    setDownloading(true);
    try {
      await downloadZip(title, version.number, version.files);
    } finally {
      setDownloading(false);
    }
  }

  function handleDismiss() {
    workspace.dismissLive();
    if (!workspace.projectId) navigate("/home");
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <WorkspaceHeader
        title={title}
        versions={versions}
        selected={selected}
        canDownload={Boolean(version)}
        downloading={downloading}
        onSelect={workspace.select}
        onDownload={handleDownload}
      />

      {error && (
        <div
          role="alert"
          className="flex shrink-0 items-center justify-between border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-200"
        >
          {error}
          <button type="button" onClick={workspace.clearError} className="text-red-300 underline">
            Dismiss
          </button>
        </div>
      )}

      <div className="flex shrink-0 gap-1 border-b border-ink-800 p-2 lg:hidden">
        {(["chat", "preview"] as const).map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setPanel(name)}
            aria-pressed={panel === name}
            className={`flex-1 rounded-lg py-1.5 text-sm capitalize transition-colors ${
              panel === name ? "bg-ink-800 text-white" : "text-ink-400"
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside
          className={`${
            panel === "chat" ? "block" : "hidden"
          } relative min-h-0 w-full overflow-hidden lg:block lg:w-[400px] lg:shrink-0 lg:border-r lg:border-ink-800`}
        >
          <ChatPanel
            versions={versions}
            selected={selected}
            loading={!project && !live && !error}
            live={live}
            stream={stream}
            canSend={Boolean(project) && !building}
            onSelect={(number) => {
              workspace.select(number);
              setPanel("preview");
            }}
            onSend={workspace.send}
            onRetry={workspace.retry}
            onDismiss={handleDismiss}
          />
        </aside>

        <section
          className={`${
            panel === "preview" ? "block" : "hidden"
          } relative min-h-0 min-w-0 flex-1 overflow-hidden lg:block`}
        >
          <RightPane
            projectId={workspace.projectId}
            selected={selected}
            title={title}
            building={building}
            versions={versions}
            files={version?.files ?? null}
            onSelect={workspace.select}
            onRestore={workspace.restore}
          />
        </section>
      </div>
    </div>
  );
}