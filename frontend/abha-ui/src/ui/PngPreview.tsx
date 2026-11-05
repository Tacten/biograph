import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import type { Png } from "../api/types";
import { ErrorNote } from "./ErrorNote";

function toBlobUrl(png: Png): string {
  const bytes = Uint8Array.from(atob(png.content), (c) => c.charCodeAt(0));
  return URL.createObjectURL(new Blob([bytes], { type: png.content_type }));
}

/** Loads an image on demand (card or QR), shows it, and offers the download. The bytes live in memory only. */
export function PngPreview({ title, load }: { title: string; load: () => Promise<Png> }) {
  const [state, setState] = useState<{ status: "idle" | "loading" | "ready" | "error"; url?: string; name?: string; error?: string }>({ status: "idle" });

  useEffect(() => () => { if (state.url) URL.revokeObjectURL(state.url); }, [state.url]);

  async function open() {
    setState({ status: "loading" });
    try {
      const png = await load();
      setState({ status: "ready", url: toBlobUrl(png), name: png.file_name });
    } catch (e) {
      setState({ status: "error", error: e instanceof ApiError ? e.message : "Could not load this image." });
    }
  }

  return (
    <div className="png">
      {state.status !== "ready" && (
        <button type="button" className="btn" onClick={open} disabled={state.status === "loading"}>
          {state.status === "loading" ? "Loading…" : state.status === "error" ? `Try ${title} again` : `Show ${title}`}
        </button>
      )}
      {state.status === "error" && <ErrorNote>{state.error}</ErrorNote>}
      {state.status === "ready" && state.url && (
        <figure className="png-figure">
          <img src={state.url} alt={title} />
          <figcaption>
            <a className="btn" href={state.url} download={state.name}>
              Download {title}
            </a>
          </figcaption>
        </figure>
      )}
    </div>
  );
}
