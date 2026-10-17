import { useEffect, useState } from "react";
import { Button, Spinner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate } from "../lib/format";
import { useStore } from "../store";
import type { InvestigationSummary } from "../types";

export function Investigations() {
  const { inv, offline, openInvestigation, openSample, closeInvestigation, toast } = useStore();
  const [list, setList] = useState<InvestigationSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = () =>
    api
      .list()
      .then((l) => {
        setList(l);
        setErr(null);
      })
      .catch((e) => setErr((e as Error).message));
  useEffect(() => {
    if (!offline) load();
  }, [offline]);

  const remove = async (id: string) => {
    try {
      await api.remove(id);
      toast("Investigation deleted.");
      if (inv?.id === id) closeInvestigation();
      load();
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  return (
    <div className="mx-auto max-w-[980px] px-5 pb-24 pt-8 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-3">
        <div>
          <div className="eyebrow mb-1">Case files</div>
          <h2 className="display text-[28px] leading-tight text-fg">Investigations</h2>
        </div>
        <div className="flex gap-2">
          <Button tone="line" size="sm" onClick={() => openSample(true)}>
            Reset sample
          </Button>
          <Button tone="primary" size="sm" onClick={closeInvestigation}>
            + New investigation
          </Button>
        </div>
      </div>
      {offline ? (
        <p className="mt-6 text-[13.5px] text-muted">The analysis server is offline, so stored investigations can't be listed. The bundled sample remains available.</p>
      ) : err ? (
        <p className="mt-6 text-[13.5px] text-alert">{err}</p>
      ) : !list ? (
        <p className="mt-6 flex items-center gap-2 text-[13px] text-muted">
          <Spinner /> Loading…
        </p>
      ) : list.length === 0 ? (
        <p className="mt-6 text-[13.5px] text-muted">No investigations yet. Start one from the intake form or open the sample.</p>
      ) : (
        <table className="mt-2 w-full border-collapse text-[13.5px]">
          <thead>
            <tr className="mono text-left text-[9.5px] uppercase tracking-widest text-faint">
              <th className="py-2 pr-3 font-normal">Name</th>
              <th className="py-2 pr-3 font-normal">Mode</th>
              <th className="py-2 pr-3 font-normal">Sources</th>
              <th className="py-2 pr-3 font-normal">Open / findings</th>
              <th className="py-2 pr-3 font-normal">Updated</th>
              <th className="py-2 font-normal" />
            </tr>
          </thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id} className="border-t border-line">
                <td className="py-2.5 pr-3">
                  <button className="display cursor-pointer text-left text-[16px] text-fg hover:text-amber" onClick={() => openInvestigation(r.id)}>
                    {r.name}
                  </button>
                  {inv?.id === r.id && <span className="mono ml-2 text-[10px] text-amber">current</span>}
                </td>
                <td className="py-2.5 pr-3">
                  <Tag tone={r.mode === "ai" ? "cool" : r.mode === "sample" ? "amber" : "default"}>{r.mode}</Tag>
                </td>
                <td className="mono py-2.5 pr-3 text-[12px] text-muted">{r.source_count}</td>
                <td className="mono py-2.5 pr-3 text-[12px] text-muted">{r.status === "ready" ? `${r.open_count} / ${r.finding_count}` : r.status}</td>
                <td className="mono py-2.5 pr-3 text-[11.5px] text-faint">{fmtDate(r.updated_at)}</td>
                <td className="py-2.5 text-right">
                  {r.mode !== "sample" && (
                    <Button size="sm" tone="ghost" onClick={() => remove(r.id)} aria-label={`Delete ${r.name}`}>
                      Delete
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {inv && (
        <section className="mt-12">
          <div className="eyebrow mb-2">Current investigation · pipeline record</div>
          <ol className="border-t border-line">
            {inv.pipeline.map((s, i) => (
              <li key={s.step} className="grid grid-cols-[2rem_1fr_auto] gap-3 border-b border-line py-2 text-[13px]">
                <span className="mono text-[11px] text-faint">{String(i + 1).padStart(2, "0")}</span>
                <span>
                  <span className="text-fg">{s.step}</span> <span className="text-muted">— {s.detail}</span>
                </span>
                <span className="mono text-[11px] text-muted">
                  {s.status !== "done" ? s.status : ""} {s.ms != null ? `${s.ms} ms` : ""}
                </span>
              </li>
            ))}
          </ol>
          <div className="eyebrow mb-2 mt-8">Limitations of this analysis</div>
          <ul className="list-inside list-[square] space-y-1 text-[13px] text-fg-dim marker:text-faint">
            {inv.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
