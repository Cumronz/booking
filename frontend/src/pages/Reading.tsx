import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api";
import { useApi } from "../hooks";
import { Empty, ErrorBox, fmtDate, Loading, Pager, useToast } from "../components/ui";
import type { Page, ReadingEntry, ReadingStats, ReadingStatus } from "../types";

const TABS: { value: ReadingStatus | ""; label: string }[] = [
  { value: "", label: "Все" }, { value: "want", label: "Хочу прочитать" },
  { value: "reading", label: "Читаю" }, { value: "read", label: "Прочитал" },
];

export default function Reading() {
  const notify = useToast();
  const [status, setStatus] = useState<ReadingStatus | "">("");
  const [page, setPage] = useState(1);
  const list = useApi<Page<ReadingEntry>>("/reading", { status, page });
  const stats = useApi<ReadingStats>("/reading/stats");

  async function update(e: ReadingEntry, next: ReadingStatus, date?: string) {
    try {
      await api(`/reading/${e.book.id}`, { method: "PUT", body: { status: next, finished_at: next === "read" ? date || null : null } });
      list.reload(); stats.reload();
    } catch (err) { notify(errorText(err), "error"); }
  }
  async function remove(e: ReadingEntry) {
    try { await api(`/reading/${e.book.id}`, { method: "DELETE" }); list.reload(); stats.reload(); }
    catch (err) { notify(errorText(err), "error"); }
  }

  const max = Math.max(1, ...(stats.data?.months.map((m) => m.count) ?? [1]));

  return (
    <>
      <h1>Моё чтение</h1>
      {stats.error && <ErrorBox text={stats.error} onRetry={stats.reload} />}
      {stats.data && (
        <section className="stats">
          <div><b>{stats.data.read_this_month}</b><span>прочитано в этом месяце</span></div>
          <div><b>{stats.data.read_this_year}</b><span>за год</span></div>
          <div><b>{stats.data.by_status.reading}</b><span>читаю сейчас</span></div>
          <div><b>{stats.data.by_status.want}</b><span>в планах</span></div>
          <div className="bars" aria-label="Прочитано по месяцам">
            {stats.data.months.map((m) => (
              <div key={m.month} className="bar" title={`${m.month}: ${m.count}`}>
                <i style={{ height: `${(m.count / max) * 100}%` }} /><span>{m.month.slice(5)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.value} role="tab" aria-selected={status === t.value} onClick={() => { setStatus(t.value); setPage(1); }}>{t.label}</button>
        ))}
      </div>

      {list.loading && <Loading />}
      {list.error && <ErrorBox text={list.error} onRetry={list.reload} />}
      {list.data?.count === 0 && <Empty title="Здесь пусто" hint="Откройте книгу в каталоге и отметьте её статус." />}
      <ul className="list">
        {list.data?.results.map((e) => (
          <li key={e.id} className="card pad">
            <div className="row">
              <strong><Link to={`/books/${e.book.id}`}>{e.book.title}</Link></strong>
              <span className="muted">{e.book.author}</span>
            </div>
            <div className="row wrap">
              <select value={e.status} aria-label="Статус" onChange={(ev) => update(e, ev.target.value as ReadingStatus, e.finished_at ?? undefined)}>
                <option value="want">Хочу прочитать</option>
                <option value="reading">Читаю</option>
                <option value="read">Прочитал</option>
              </select>
              {e.status === "read" && (
                <label className="check">Завершено:
                  <input type="date" defaultValue={e.finished_at ?? ""} max={new Date().toISOString().slice(0, 10)}
                    onChange={(ev) => ev.target.value && update(e, "read", ev.target.value)} />
                </label>
              )}
              {e.finished_at && <span className="muted">{fmtDate(e.finished_at)}</span>}
              <button className="link danger" onClick={() => remove(e)}>Убрать</button>
            </div>
          </li>
        ))}
      </ul>
      <Pager page={page} setPage={setPage} data={list.data} />
    </>
  );
}
