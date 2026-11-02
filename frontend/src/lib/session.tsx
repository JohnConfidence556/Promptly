import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, getMe, type User } from "./api";

const STORAGE_KEY = "promptly.session";

export type Session = { token: string; user: User };

type SessionContextValue = {
  session: Session | null;
  ready: boolean;
  signIn: (session: Session) => void;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(loadSession);
  const [ready, setReady] = useState(() => loadSession() === null);

  // Check the stored token once, when the app loads.
  useEffect(() => {
    if (!session) return;

    getMe(session.token)
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) {
          localStorage.removeItem(STORAGE_KEY);
          setSession(null);
        }
      })
      .finally(() => setReady(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signIn = useCallback((next: Session) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setSession(next);
    setReady(true);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({ session, ready, signIn, signOut }),
    [session, ready, signIn, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}