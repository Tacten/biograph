import { requestDocumentOtp, verifyDocumentOtp } from "../../api/abha";
import { useKnown } from "../../domain/StoreContext";
import { OtpPanel } from "../../ui/OtpPanel";

export function DlOtpStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const { known, dispatch } = useKnown();
  const patient = known.patient?.name;

  async function send() {
    if (!patient || !known.consent) throw new Error("The agreement is missing. Go back and record it.");
    const res = await requestDocumentOtp(patient, known.consent.id, known.communicationMobile);
    dispatch({ type: "learn", patch: { txnId: res.txnId } });
  }

  async function verify(code: string) {
    if (!patient || !known.txnId) throw new Error("The OTP request has expired. Go back and send it again.");
    const res = await verifyDocumentOtp(patient, known.txnId, code);
    dispatch({ type: "learn", patch: { txnId: res.txnId ?? known.txnId } });
    dispatch({ type: "forget", keys: ["communicationMobile"] });
    onNext();
  }

  return (
    <OtpPanel
      heading="Verify mobile OTP"
      lede="Enter the 6-digit OTP sent to the mobile number. It is checked as soon as the sixth digit is in."
      label="Mobile OTP"
      verify={verify}
      resend={send}
      send={send}
      back={{ label: "Change the number", onClick: onBack }}
    />
  );
}
