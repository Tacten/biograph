import { createContext, useContext } from "react";
import { defaultRd, type RdClient } from "./rdService";

export const RdContext = createContext<RdClient>(defaultRd);
export const useRd = (): RdClient => useContext(RdContext);
