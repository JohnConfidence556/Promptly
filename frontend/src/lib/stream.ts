import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useCallback, useEffect, useRef, useState } from "react";

import { API_URL } from "./api";

export type StepEvent = { step: string } & Record<string, unknown>;

export type ResultEvent = {
  status: "passed" | "failed";
  project_id: string | null;
  version: number | null;
  fix_rounds: number;
  files: string[];
  error: string | null;
};

export type FileProgress = {
  file: string;
  state: "started" | "done";
  action: "write" | "fix" | "edit";
};

export type Waiting = {
  seconds: number;
  since: number;
  reason: "rate_limit" | "retry";
};

type ProgressEvent =
  | { kind: "file"; file: string; state: "started" | "done"; action: "write" | "fix" | "edit" }
  | { kind: "waiting"; seconds: number; reason: "rate_limit" | "retry" };

export type StreamStatus = "idle" | "running" | "passed" | "failed";

export type StreamState = {
  status: StreamStatus;
  steps: StepEvent[];
  files: FileProgress[];
  waiting: Waiting | null;
  result: ResultEvent | null;
  error: string | null;
  busy: boolean;
};

const INITIAL: StreamState = {
  status: "idle",
  steps: [],
  files: [],
  waiting: null,
  result: null,
  error: null,
  busy: false,
};

// Thrown on purpose to stop the library from reconnecting automatically.
class StopStream extends Error {}

function applyProgress(previous: StreamState, event: ProgressEvent): StreamState {
  if (event.kind === "waiting") {
    return {
      ...previous,
      waiting: { seconds: event.seconds, since: Date.now(), reason: event.reason },
    };
  }

  const entry: FileProgress = { file: event.file, state: event.state, action: event.action };
  const exists = previous.files.some((item) => item.file === event.file);
  const files = exists
    ? previous.files.map((item) => (item.file === event.file ? entry : item))
    : [...previous.files, entry];

  return { ...previous, files, waiting: null };
}

export function useBuildStream(token: string) {
  const [state, setState] = useState<StreamState>(INITIAL);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const reset = useCallback(() => {
    controllerRef.current?.abort();
    setState(INITIAL);
  }, []);

  const start = useCallback(
    async (path: string, prompt: string) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      let finished = false;

      setState({ ...INITIAL, status: "running" });

      try {
        await fetchEventSource(`${API_URL}${path}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ prompt }),
          signal: controller.signal,
          openWhenHidden: true,

          async onopen(response) {
            const isStream = response.headers.get("content-type")?.includes("text/event-stream");
            if (response.ok && isStream) return;

            const busy = response.status === 429;
            let message = "Couldn't start the build. Try again.";

            if (response.status === 401) {
              message = "Your session expired. Get started again.";
            } else {
              try {
                const data = await response.json();
                if (typeof data.detail === "string") message = data.detail;
              } catch {
                if (busy) message = "Promptly is busy right now. Try again in a moment.";
              }
            }

            finished = true;
            setState({ ...INITIAL, status: "failed", error: message, busy });
            throw new StopStream();
          },

          onmessage(message) {
            if (message.event === "step") {
              const step = JSON.parse(message.data) as StepEvent;
              setState((previous) => ({
                ...previous,
                steps: [...previous.steps, step],
                files: [],
                waiting: null,
              }));
            } else if (message.event === "progress") {
              const event = JSON.parse(message.data) as ProgressEvent;
              setState((previous) => applyProgress(previous, event));
            } else if (message.event === "result") {
              const result = JSON.parse(message.data) as ResultEvent;
              finished = true;
              setState((previous) => ({
                ...previous,
                status: result.status,
                result,
                error: result.error,
                files: [],
                waiting: null,
              }));
            }
          },

          // Throwing here (even after a normal finish) stops automatic reconnects.
          onclose() {
            throw new StopStream();
          },

          onerror(error) {
            throw error;
          },
        });
      } catch {
        if (controller.signal.aborted || finished) return;

        setState((previous) => ({
          ...previous,
          status: "failed",
          error: "Lost the connection to Promptly. Try again.",
        }));
      }
    },
    [token],
  );

  return { state, start, reset };
}