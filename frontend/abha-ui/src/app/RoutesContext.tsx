import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getRoutes } from "../api/abha";
import type { Routes } from "../api/types";

/** Until the site answers, the always-available routes are offered and nothing that needs configuration or a role. */
const FALLBACK: Routes = { aadhaar_otp: true, driving_licence: true, biometric: false, can_approve: false };

const Ctx = createContext<Routes>(FALLBACK);

export function RoutesProvider({ children }: { children: ReactNode }) {
  const [routes, setRoutes] = useState<Routes>(FALLBACK);
  useEffect(() => {
    let live = true;
    getRoutes()
      .then((r) => live && setRoutes(r))
      .catch(() => undefined); // keep the fallback: a failed lookup must not stop the desk
    return () => {
      live = false;
    };
  }, []);
  return <Ctx.Provider value={routes}>{children}</Ctx.Provider>;
}

export const useRoutes = (): Routes => useContext(Ctx);
