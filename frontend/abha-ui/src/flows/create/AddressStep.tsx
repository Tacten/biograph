import { useEffect, useState } from "react";
import { getAddressSuggestions, setAddress } from "../../api/abha";
import { ApiError } from "../../api/client";
import { useKnown } from "../../domain/StoreContext";
import { ErrorNote } from "../../ui/ErrorNote";
import { ADDRESS_RULES, addressError, domainOf, stripDomain } from "../../ui/validate";

const SHOWN = 5;
const FALLBACK_DOMAIN = "@sbx";
const CUSTOM = "__custom__";

export function AddressStep({ onNext }: { onNext: () => void }) {
  const { known, dispatch } = useKnown();
  const [suggestions, setSuggestions] = useState<string[] | null>(null);
  const [picked, setPicked] = useState("");
  const [custom, setCustom] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!known.patient) return;
    let live = true;
    getAddressSuggestions(known.patient.name)
      .then((all) => {
        if (!live) return;
        const list = all.slice(0, SHOWN);
        setSuggestions(list);
        setPicked(list[0] ?? CUSTOM);
      })
      .catch((e: unknown) => {
        if (!live) return;
        setSuggestions([]);
        setPicked(CUSTOM);
        setError(e instanceof ApiError ? e.message : "Could not get address suggestions. You can type your own.");
      });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const domain = (suggestions ?? []).map(domainOf).find(Boolean) ?? FALLBACK_DOMAIN;
  const isCustom = picked === CUSTOM;
  const customProblem = isCustom ? addressError(custom) : null;

  async function submit() {
    setTouched(true);
    if (!known.patient || !picked || customProblem) return;
    const address = isCustom ? custom.trim().toLowerCase() + domain : picked.includes("@") ? picked : picked + domain;
    setBusy(true);
    setError("");
    try {
      const res = await setAddress(known.patient.name, address);
      dispatch({ type: "learn", patch: { abhaAddress: res.abha_address ?? address } });
      onNext();
    } catch (e) {
      // A taken or refused address keeps the alternatives on screen rather than leaving only an error.
      setError(e instanceof ApiError ? e.message : "Could not create the address.");
    } finally {
      setBusy(false);
    }
  }

  if (suggestions === null) return <p className="muted" role="status">Getting address suggestions…</p>;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      noValidate
    >
      <h2 id="step-title">Choose ABHA address</h2>
      <p className="lede">The ABHA address is how the patient signs in and shares records. Pick a suggestion or write your own.</p>
      <fieldset className="choices">
        <legend className="sr-only">ABHA address</legend>
        {suggestions.map((s) => (
          <label key={s} className="choice">
            <input type="radio" name="abha-address" checked={picked === s} onChange={() => setPicked(s)} />
            <span>{s.includes("@") ? s : s + domain}</span>
          </label>
        ))}
        <label className="choice">
          <input type="radio" name="abha-address" checked={isCustom} onChange={() => setPicked(CUSTOM)} />
          <span>Write my own</span>
        </label>
      </fieldset>
      {isCustom && (
        <div className="field">
          <label htmlFor="custom-address">Your address</label>
          <div className="suffixed">
            <input
              id="custom-address"
              autoFocus
              autoComplete="off"
              autoCapitalize="none"
              value={custom}
              onChange={(e) => setCustom(stripDomain(e.target.value))}
              onBlur={() => setTouched(true)}
              aria-invalid={touched && customProblem ? true : undefined}
              aria-describedby="address-rules"
            />
            <span aria-hidden="true">{domain}</span>
          </div>
          {touched && customProblem && <div className="field-error">{customProblem}</div>}
          <ul id="address-rules" className="rules">
            {ADDRESS_RULES.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}
      <ErrorNote>{error}</ErrorNote>
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={busy || !picked}>
          {busy ? "Creating…" : "Create this address"}
        </button>
      </div>
    </form>
  );
}
