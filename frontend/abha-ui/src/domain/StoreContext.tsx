import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import { knownReducer, type Action, type Known } from "./known";

interface Store {
  known: Known;
  dispatch: Dispatch<Action>;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children, initial = {} }: { children: ReactNode; initial?: Known }) {
  const [known, dispatch] = useReducer(knownReducer, initial);
  const value = useMemo(() => ({ known, dispatch }), [known]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useKnown(): Store {
  const store = useContext(Ctx);
  if (!store) throw new Error("useKnown must be used inside <StoreProvider>");
  return store;
}
