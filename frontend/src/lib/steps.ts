import type { FileProgress, StepEvent, Waiting } from "./stream";

export type PipelineKind = "build" | "edit";

export type StepView = {
  key: string;
  label: string;
  status: "done" | "running" | "failed";
  tone?: "warn";
  details?: string[];
  files?: FileProgress[];
  waiting?: Waiting;
};

const RUNNING_LABELS: Record<string, string> = {
  planner: "Planning the app",
  architect: "Designing the shared contract",
  coder: "Writing HTML, CSS and JavaScript",
  validator: "Checking the result",
  repairer: "Fixing the issues it found",
  writer: "Saving the version",
  edit_planner: "Planning the change",
  editor: "Updating the files",
};

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export function describeStep(event: StepEvent, index: number): StepView {
  const key = `${event.step}-${index}`;
  const error = text(event.error);

  if (error) {
    return {
      key,
      label: `${RUNNING_LABELS[event.step] ?? event.step} failed`,
      status: "failed",
      details: [error],
    };
  }

  switch (event.step) {
    case "planner": {
      const name = text(event.app_name);
      const note = event.scope_status === "redirected" ? text(event.scope_note) : null;
      return {
        key,
        label: name ? `Planned "${name}"` : "Planned the app",
        status: "done",
        details: note ? [note] : undefined,
      };
    }

    case "architect":
      return {
        key,
        label: "Designed the shared contract",
        status: "done",
        details: [
          `${Number(event.element_ids) || 0} elements · ${Number(event.css_classes) || 0} classes · ${Number(event.js_functions) || 0} functions`,
        ],
      };

    case "coder":
      return {
        key,
        label: `Wrote ${plural(strings(event.files).length, "file")}`,
        status: "done",
      };

    case "validator": {
      if (event.passed) return { key, label: "All checks passed", status: "done" };

      const found = Array.isArray(event.issues) ? event.issues : [];
      const details = found.slice(0, 3).map((item) => {
        const record = (item ?? {}) as Record<string, unknown>;
        return `${String(record.file ?? "")}: ${String(record.message ?? "")}`;
      });

      return {
        key,
        label: `Found ${plural(found.length, "issue")} to fix`,
        status: "done",
        tone: "warn",
        details,
      };
    }

    case "repairer":
      return {
        key,
        label: `Fixed the issues (round ${Number(event.fix_rounds) || 1})`,
        status: "done",
      };

    case "writer":
      return { key, label: "Saved the new version", status: "done" };

    case "edit_planner": {
      const files = strings(event.files);
      return {
        key,
        label: text(event.summary) ?? "Planned the change",
        status: "done",
        details: files.length ? [`Touches ${files.join(", ")}`] : undefined,
      };
    }

    case "editor":
      return {
        key,
        label: `Updated ${strings(event.files).join(", ") || "the files"}`,
        status: "done",
      };

    default:
      return { key, label: event.step, status: "done" };
  }
}

export function nextStep(kind: PipelineKind, events: StepEvent[]): string | null {
  const last = events[events.length - 1];
  if (!last) return kind === "build" ? "planner" : "edit_planner";
  if (text(last.error)) return null;

  switch (last.step) {
    case "planner":
      return "architect";
    case "architect":
      return "coder";
    case "edit_planner":
      return "editor";
    case "coder":
    case "editor":
    case "repairer":
      return "validator";
    case "validator":
      return last.passed ? "writer" : "repairer";
    default:
      return null;
  }
}

export type LiveProgress = { files: FileProgress[]; waiting: Waiting | null };

const FILE_STEPS = new Set(["coder", "editor", "repairer"]);

export function liveSteps(
  kind: PipelineKind,
  events: StepEvent[],
  running: boolean,
  progress: LiveProgress,
): StepView[] {
  const views = events.map(describeStep);
  if (!running) return views;

  const next = nextStep(kind, events);
  if (next) {
    views.push({
      key: `running-${next}-${events.length}`,
      label: RUNNING_LABELS[next] ?? next,
      status: "running",
      files: FILE_STEPS.has(next) && progress.files.length > 0 ? progress.files : undefined,
      waiting: progress.waiting ?? undefined,
    });
  }

  return views;
}

export function storedSteps(version: { number: number; fix_rounds: number }): StepView[] {
  const labels =
    version.number === 1
      ? ["Planned the app", "Designed the shared contract", "Wrote the HTML, CSS and JavaScript"]
      : ["Planned the change", "Updated the files"];

  if (version.fix_rounds > 0) {
    labels.push(`Fixed the issues it found (${plural(version.fix_rounds, "round")})`);
  }
  labels.push("All checks passed");

  return labels.map((label) => ({ key: label, label, status: "done" as const }));
}