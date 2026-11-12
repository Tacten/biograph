import { useEffect, useId, useRef, useState } from "react";
import { searchPatients } from "../api/abha";
import { ApiError } from "../api/client";
import type { PatientRow } from "../api/types";
import { useKnown } from "../domain/StoreContext";

const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;

type Status = "idle" | "loading" | "ready" | "error";

export function PatientPicker() {
  const { known, dispatch } = useKnown();
  const [text, setText] = useState("");
  const [rows, setRows] = useState<PatientRow[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const latest = useRef(0);

  useEffect(() => {
    const q = text.trim();
    if (q.length < MIN_CHARS) {
      setStatus("idle");
      setRows([]);
      return;
    }
    const ticket = ++latest.current;
    setStatus("loading");
    const timer = setTimeout(() => {
      searchPatients(q)
        .then((found) => {
          if (ticket !== latest.current) return; // a newer search is in flight
          setRows(found);
          setActive(0);
          setStatus("ready");
        })
        .catch((e: unknown) => {
          if (ticket !== latest.current) return;
          setError(e instanceof ApiError ? e.message : "Could not search patients.");
          setStatus("error");
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);

  function choose(row: PatientRow) {
    dispatch({ type: "patient", patient: { name: row.name, patient_name: row.patient_name } });
    setText("");
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") return setOpen(false);
    if (!rows.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, rows.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && open) { e.preventDefault(); const row = rows[active]; if (row) choose(row); }
  }

  if (known.patient) {
    return (
      <div className="chip" data-testid="patient-chip">
        <span className="chip-name">{known.patient.patient_name}</span>
        <small>{known.patient.name}</small>
        <button type="button" className="chip-clear" aria-label={`Clear patient ${known.patient.patient_name}`} onClick={() => dispatch({ type: "patient", patient: undefined })}>×</button>
      </div>
    );
  }

  const showList = open && text.trim().length >= MIN_CHARS;
  return (
    <div className="picker">
      <input
        className="picker-input"
        type="search"
        role="combobox"
        aria-label="Find patient"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && rows[active] ? `${listId}-${active}` : undefined}
        placeholder="Find patient by name, ID or mobile"
        autoComplete="off"
        value={text}
        onChange={(e) => { setText(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul className="picker-list" id={listId} role="listbox" aria-label="Matching patients">
          {status === "loading" && <li className="picker-note" role="presentation">Searching…</li>}
          {status === "error" && <li className="picker-note" role="alert">{error}</li>}
          {status === "ready" && rows.length === 0 && <li className="picker-note" role="presentation">No patient found.</li>}
          {status === "ready" && rows.map((r, i) => (
            <li key={r.name} id={`${listId}-${i}`} role="option" aria-selected={i === active} className="picker-option" onMouseDown={(e) => { e.preventDefault(); choose(r); }}>
              <span>{r.patient_name}</span>
              <small>{[r.name, r.mobile ? "mobile on file" : null, r.abha_number ? "has ABHA" : null].filter(Boolean).join(" · ")}</small>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
