import { FormEvent, useState } from "react";
import { api, errorText, fieldError } from "../api";
import { useApi } from "../hooks";
import { Empty, ErrorBox, Field, FormError, Loading, Pager, useToast } from "../components/ui";
import type { Book, Condition, Copy, Page } from "../types";

const CONDITIONS: [Condition, string][] = [["new", "Новая"], ["good", "Хорошее"], ["fair", "Удовлетворительное"], ["worn", "Потрёпанная"]];

export default function Shelf() {
  const notify = useToast();
  const [page, setPage] = useState(1);
  const copies = useApi<Page<Copy>>("/copies", { mine: 1, page });

  const [bookQ, setBookQ] = useState("");
  const found = useApi<Page<Book>>("/books", { search: bookQ, page_size: 30 });
  const [bookId, setBookId] = useState("");
  const [condition, setCondition] = useState<Condition>("good");
  const [place, setPlace] = useState("");
  const [err, setErr] = useState<unknown>(null);

  async function add(e: FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/copies", { method: "POST", body: { book: bookId ? Number(bookId) : null, condition, pickup_place: place } });
      notify("Экземпляр добавлен на полку."); setPlace(""); copies.reload();
    } catch (e2) { setErr(e2); }
  }
  async function toggle(c: Copy) {
    try { await api(`/copies/${c.id}`, { method: "PATCH", body: { is_active: !c.is_active } }); copies.reload(); }
    catch (e) { notify(errorText(e), "error"); }
  }
  async function remove(c: Copy) {
    if (!confirm(`Удалить экземпляр «${c.book_title}»?`)) return;
    try { await api(`/copies/${c.id}`, { method: "DELETE" }); notify("Экземпляр удалён."); copies.reload(); }
    catch (e) { notify(errorText(e), "error"); }
  }
  async function edit(c: Copy, patch: Partial<Pick<Copy, "pickup_place" | "condition">>) {
    try { await api(`/copies/${c.id}`, { method: "PATCH", body: patch }); copies.reload(); }
    catch (e) { notify(errorText(e), "error"); }
  }

  return (
    <>
      <h1>Моя полка</h1>
      <form onSubmit={add} className="form card pad">
        <h3>Добавить экземпляр</h3>
        <FormError text={err && !fieldError(err, "book") && !fieldError(err, "pickup_place") ? errorText(err) : undefined} />
        <Field label="Найти книгу в каталоге">
          <input type="search" value={bookQ} onChange={(e) => setBookQ(e.target.value)} placeholder="Название или автор" />
        </Field>
        <Field label="Книга" error={fieldError(err, "book")}>
          <select value={bookId} onChange={(e) => setBookId(e.target.value)} required>
            <option value="">— выберите —</option>
            {found.data?.results.map((b) => <option key={b.id} value={b.id}>{b.title} — {b.author}</option>)}
          </select>
        </Field>
        <Field label="Состояние" error={fieldError(err, "condition")}>
          <select value={condition} onChange={(e) => setCondition(e.target.value as Condition)}>
            {CONDITIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <Field label="Место передачи" error={fieldError(err, "pickup_place")}>
          <input value={place} onChange={(e) => setPlace(e.target.value)} placeholder="Например, вахта общежития" required />
        </Field>
        <button className="primary">Добавить</button>
      </form>

      {copies.loading && <Loading />}
      {copies.error && <ErrorBox text={copies.error} onRetry={copies.reload} />}
      {copies.data?.count === 0 && <Empty title="Полка пуста" hint="Добавьте первую книгу — её смогут запросить другие студенты." />}
      <ul className="list">
        {copies.data?.results.map((c) => (
          <li key={c.id} className="card pad">
            <div className="row">
              <strong>{c.book_title}</strong>
              <span className={"badge " + (c.is_active ? (c.available ? "ok" : "warn") : "")}>
                {!c.is_active ? "снята с полки" : c.available ? "доступна" : "занята"}
              </span>
            </div>
            <p className="muted">{c.book_author}</p>
            <div className="row wrap">
              <select value={c.condition} onChange={(e) => edit(c, { condition: e.target.value as Condition })} aria-label="Состояние">
                {CONDITIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <input defaultValue={c.pickup_place} aria-label="Место передачи"
                onBlur={(e) => { const v = e.target.value.trim(); if (v && v !== c.pickup_place) edit(c, { pickup_place: v }); }} />
              <button onClick={() => toggle(c)}>{c.is_active ? "Снять с полки" : "Вернуть на полку"}</button>
              <button className="link danger" onClick={() => remove(c)}>Удалить</button>
            </div>
          </li>
        ))}
      </ul>
      <Pager page={page} setPage={setPage} data={copies.data} />
    </>
  );
}
