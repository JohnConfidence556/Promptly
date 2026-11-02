import { ArrowUp, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import AppHeader from "../components/AppHeader";
import Button from "../components/ui/Button";
import {
  ApiError,
  deleteProject,
  listProjects,
  type ProjectSummary,
} from "../lib/api";
import { timeAgo } from "../lib/format";
import { useSession } from "../lib/session";

const EXAMPLES = [
  "A tip calculator that splits the bill between friends",
  "A pomodoro timer with start, pause, and reset",
  "A to-do list where I can add, complete, and delete tasks",
  "A unit converter for length, weight, and temperature",
];

export default function Home() {
  const { session } = useSession();
  const navigate = useNavigate();
  const token = session?.token ?? "";
  const firstName = session?.user.name.split(" ")[0] ?? "";

  const [prompt, setPrompt] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoadError(null);
    listProjects(token)
      .then(setProjects)
      .catch((error) =>
        setLoadError(
          error instanceof ApiError ? error.message : "Couldn't load your projects.",
        ),
      );
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function submit() {
    const text = prompt.trim();
    if (text.length < 3) return;
    navigate("/p/new", { state: { prompt: text } });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  async function remove(project: ProjectSummary) {
    const confirmed = window.confirm(
      `Delete "${project.title}"? This removes all of its versions.`,
    );
    if (!confirmed) return;

    try {
      await deleteProject(token, project.id);
      setProjects((current) => current?.filter((item) => item.id !== project.id) ?? null);
    } catch {
      setLoadError("Couldn't delete that project. Try again.");
    }
  }

  return (
    <div className="relative min-h-screen">
      <div
        className="hero-glow pointer-events-none absolute inset-x-0 top-0 h-[420px]"
        aria-hidden
      />
      <AppHeader />

      <main className="relative mx-auto max-w-6xl px-6 pb-24 pt-16">
        <section className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            What do you want to build{firstName ? `, ${firstName}` : ""}?
          </h1>
          <p className="mt-3 text-ink-300">
            Describe a small web app and Promptly will plan it, write it, and check it.
          </p>

          <div className="mt-8 rounded-2xl border border-ink-600 bg-ink-900 p-3 text-left focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/30">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              maxLength={2000}
              aria-label="Describe the app you want to build"
              placeholder="A pomodoro timer with start, pause, and reset"
              className="w-full resize-none bg-transparent px-2 py-1 text-base text-white placeholder:text-ink-400 focus:outline-none"
            />
            <div className="flex items-center justify-between px-2 pt-2">
              <span className="text-xs text-ink-400">
                Enter to build · Shift + Enter for a new line
              </span>
              <Button size="sm" onClick={submit} disabled={prompt.trim().length < 3}>
                <ArrowUp className="size-4" />
                Build
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setPrompt(example)}
                className="rounded-full border border-ink-700 px-3.5 py-1.5 text-sm text-ink-300 transition-colors hover:border-ink-500 hover:bg-ink-800 hover:text-white"
              >
                {example}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-20">
          <h2 className="text-lg font-medium text-white">Your projects</h2>

          {loadError && (
            <div
              role="alert"
              className="mt-4 flex items-center justify-between rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
            >
              {loadError}
              <Button variant="secondary" size="sm" onClick={load}>
                Try again
              </Button>
            </div>
          )}

          {projects === null && !loadError && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((item) => (
                <div key={item} className="h-48 animate-pulse rounded-2xl bg-ink-900" />
              ))}
            </div>
          )}

          {projects !== null && projects.length === 0 && (
            <div className="mt-4 rounded-2xl border border-dashed border-ink-700 px-6 py-14 text-center">
              <Sparkles className="mx-auto size-6 text-brand-400" />
              <p className="mt-3 font-medium text-white">Nothing here yet</p>
              <p className="mt-1 text-sm text-ink-300">
                Describe your first app above and it will show up here.
              </p>
            </div>
          )}

          {projects !== null && projects.length > 0 && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className="group relative rounded-2xl border border-ink-700 bg-ink-900/60 p-3 transition-colors hover:border-ink-500"
                >
                  <Link to={`/p/${project.id}`} className="block">
                    <div className="flex h-28 items-center justify-center rounded-xl border border-ink-700 bg-linear-to-br from-brand-500/20 to-sky-400/10">
                      <Sparkles className="size-6 text-brand-300" />
                    </div>
                    <h3 className="mt-3 truncate px-1 font-medium text-white">
                      {project.title}
                    </h3>
                    <p className="mt-0.5 px-1 text-sm text-ink-400">
                      v{project.latest_version} · Updated {timeAgo(project.updated_at)}
                    </p>
                  </Link>
                  <button
                    type="button"
                    onClick={() => remove(project)}
                    aria-label={`Delete ${project.title}`}
                    className="absolute right-5 top-5 rounded-lg bg-ink-950/80 p-1.5 text-ink-300 opacity-0 transition-opacity hover:text-red-400 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}