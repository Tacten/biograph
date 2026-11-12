import { getBoot } from "../api/client";
import { StoreProvider } from "../domain/StoreContext";
import { useKnown } from "../domain/StoreContext";
import { CreateFlow } from "../flows/create/CreateFlow";
import { ApprovalsFlow } from "../flows/approvals/ApprovalsFlow";
import { VerifyFlow } from "../flows/verify/VerifyFlow";
import { ProfileFlow } from "../flows/profile/ProfileFlow";
import { RdContext } from "../rd/RdContext";
import type { RdClient } from "../rd/rdService";
import { RoutesProvider } from "./RoutesContext";
import { Shell } from "./Shell";
import { useRoute } from "./router";

function Workspace() {
  const route = useRoute();
  const { known } = useKnown();

  // Approvals are about documents waiting in the system, not about the patient picked in the header.
  if (route.id === "approvals") return <ApprovalsFlow />;

  if (!known.patient) {
    return (
      <div className="card empty">
        <strong>Select a patient to begin</strong>
        Use “Find patient” above. Every ABHA task starts from a registered patient.
      </div>
    );
  }

  if (route.id === "create") return <CreateFlow key={known.patient.name} />;
  if (route.id === "verify") return <VerifyFlow key={known.patient.name} />;
  return <ProfileFlow key={known.patient.name} />;
}

export function App({ rd }: { rd?: RdClient } = {}) {
  const boot = getBoot();
  const tree = (
    <RoutesProvider>
      <StoreProvider initial={boot.patient ? { patient: boot.patient } : {}}>
        <Shell>
          <Workspace />
        </Shell>
      </StoreProvider>
    </RoutesProvider>
  );
  return rd ? <RdContext.Provider value={rd}>{tree}</RdContext.Provider> : tree;
}
