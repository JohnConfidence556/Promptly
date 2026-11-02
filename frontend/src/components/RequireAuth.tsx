import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useSession } from "../lib/session";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { session, ready } = useSession();

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-300">
        <Loader2 className="size-6 animate-spin" />
      </div>
    );
  }

  if (!session) return <Navigate to="/get-started" replace />;

  return <>{children}</>;
}