import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  ApiError,
  getProject,
  getVersion,
  restoreVersion,
  type ProjectDetail,
  type VersionDetail,
} from "./api";
import type { PipelineKind } from "./steps";
import { useBuildStream } from "./stream";

export type LiveTurn = { prompt: string; kind: PipelineKind };

export function useWorkspace(paramId: string, token: string, initialPrompt?: string) {
  const navigate = useNavigate();
  const { state: stream, start, reset: resetStream } = useBuildStream(token);

  const idRef = useRef<string | null>(paramId === "new" ? null : paramId);
  const loadedRef = useRef<string | null>(null);
  const startedRef = useRef(false);

  const [projectId, setProjectId] = useState<string | null>(idRef.current);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [version, setVersion] = useState<VersionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<LiveTurn | null>(null);

  const loadProject = useCallback(
    async (id: string, select?: number) => {
      const detail = await getProject(token, id);
      if (idRef.current !== id) return;

      loadedRef.current = id;
      setProject(detail);
      setSelected(
        (current) =>
          select ?? current ?? detail.versions[detail.versions.length - 1].number,
      );
    },
    [token],
  );

  // Load the project when we have an id.
  useEffect(() => {
    if (!projectId || loadedRef.current === projectId) return;

    loadProject(projectId).catch((failure) =>
      setError(failure instanceof ApiError ? failure.message : "Couldn't load this project."),
    );
  }, [projectId, loadProject]);

  // Load the files of the selected version.
  useEffect(() => {
    if (!projectId || selected === null) return;

    let cancelled = false;
    setVersion(null);

    getVersion(token, projectId, selected)
      .then((data) => {
        if (!cancelled) setVersion(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load that version.");
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, selected, token]);

  // The URL changed to a different existing project (back button, link).
  useEffect(() => {
    if (paramId === "new" || paramId === idRef.current) return;

    resetStream();
    idRef.current = paramId;
    loadedRef.current = null;
    setLive(null);
    setProject(null);
    setVersion(null);
    setSelected(null);
    setError(null);
    setProjectId(paramId);
  }, [paramId, resetStream]);

  // A brand-new build started from the Home page.
  useEffect(() => {
    if (paramId !== "new" || !initialPrompt || startedRef.current) return;

    startedRef.current = true;
    setLive({ prompt: initialPrompt, kind: "build" });
    void start("/api/builds/stream", initialPrompt);
  }, [paramId, initialPrompt, start]);

  // A build or edit finished successfully.
  useEffect(() => {
    const result = stream.result;
    if (!result || result.status !== "passed" || !result.project_id || result.version === null) {
      return;
    }

    const id = result.project_id;
    const number = result.version;
    let cancelled = false;

    (async () => {
      try {
        idRef.current = id;
        setProjectId(id);
        await loadProject(id, number);
        if (cancelled) return;

        setLive(null);
        if (paramId === "new") navigate(`/p/${id}`, { replace: true });
      } catch {
        setError("Your app was built, but loading it failed. Refresh the page.");
      }
    })();

    return () => {
      cancelled = true;
    };
    // Only react when a new result arrives.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.result]);

  const send = useCallback(
    (prompt: string) => {
      if (!idRef.current) return;
      setLive({ prompt, kind: "edit" });
      void start(`/api/projects/${idRef.current}/edits/stream`, prompt);
    },
    [start],
  );

  const retry = useCallback(() => {
    if (!live) return;

    if (live.kind === "build") {
      void start("/api/builds/stream", live.prompt);
    } else if (idRef.current) {
      void start(`/api/projects/${idRef.current}/edits/stream`, live.prompt);
    }
  }, [live, start]);

  const dismissLive = useCallback(() => {
    resetStream();
    setLive(null);
  }, [resetStream]);

  const restore = useCallback(
    async (number: number) => {
      const id = idRef.current;
      if (!id) return;

      try {
        const created = await restoreVersion(token, id, number);
        await loadProject(id, created.version);
      } catch {
        setError("Couldn't restore that version. Try again.");
      }
    },
    [token, loadProject],
  );

  return {
    projectId,
    project,
    selected,
    version,
    error,
    live,
    stream,
    select: setSelected,
    send,
    retry,
    dismissLive,
    restore,
    clearError: () => setError(null),
  };
}