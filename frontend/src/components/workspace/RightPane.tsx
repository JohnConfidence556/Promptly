import { Activity, Code, Eye, History } from "lucide-react";
import { useState } from "react";

import type { VersionSummary } from "../../lib/api";
import CodePane from "./CodePane";
import PreviewPane from "./PreviewPane";
import RunLogPane from "./RunLogPane";
import VersionsPane from "./VersionsPane";

const TABS = [
  { id: "preview", label: "Preview", icon: Eye },
  { id: "code", label: "Code", icon: Code },
  { id: "versions", label: "Versions", icon: History },
  { id: "runs", label: "Run log", icon: Activity },
] as const;

type TabId = (typeof TABS)[number]["id"];

type Props = {
  projectId: string | null;
  selected: number | null;
  title: string;
  building: boolean;
  versions: VersionSummary[];
  files: Record<string, string> | null;
  onSelect: (number: number) => void;
  onRestore: (number: number) => Promise<void>;
};

export default function RightPane({
  projectId,
  selected,
  title,
  building,
  versions,
  files,
  onSelect,
  onRestore,
}: Props) {
  const [tab, setTab] = useState<TabId>("preview");

  return (
    <div className="absolute inset-0 grid grid-rows-[auto_minmax(0,1fr)]">
      <div
        className="flex h-11 items-center gap-1 border-b border-ink-800 px-3"
        role="tablist"
        aria-label="Workspace views"
      >
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors ${
              tab === id ? "bg-ink-800 text-white" : "text-ink-400 hover:text-white"
            }`}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </div>

      <div className="relative min-h-0">
        {/* The preview stays mounted so switching tabs doesn't reload the app. */}
        <div
          role="tabpanel"
          className={tab === "preview" ? "absolute inset-0 flex flex-col" : "hidden"}
        >
          <PreviewPane projectId={projectId} version={selected} title={title} building={building} />
        </div>

        {tab === "code" && (
          <div role="tabpanel" className="absolute inset-0 flex flex-col">
            <CodePane files={files} />
          </div>
        )}

        {tab === "versions" && (
          <div role="tabpanel" className="absolute inset-0 flex flex-col">
            <VersionsPane
              versions={versions}
              selected={selected}
              disabled={building}
              onSelect={onSelect}
              onRestore={onRestore}
            />
          </div>
        )}

        {tab === "runs" && (
          <div role="tabpanel" className="absolute inset-0 flex flex-col">
            <RunLogPane projectId={projectId} refreshKey={versions.length} />
          </div>
        )}
      </div>
    </div>
  );
}