import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText, fieldError } from "../api";
import { useAuth } from "../auth";
import { useApi } from "../hooks";
import { Cover, Empty, ErrorBox, Field, FormError, fmtDate, fullName, Loading, Pager, Stars, useToast } from "../components/ui";
import type { BookDetail, Copy, Page, ReadingEntry, ReadingStatus, Review } from "../types";
import { NotFound } from "./Errors";

const tomorrow = (days = 14) => new Date(Date.now() + days * 864e5).toISOString().slice(0, 10);

export default function BookPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const notify = useToast();
  const [reviewsPage, setReviewsPage] = useState(1);
  const book = useApi<BookDetail>(`/books/${id}`);
  const copies = useApi<Page<Copy>>(`/books/${id}/copies`, { page_size: 50 });
  const reviews = useApi<Page<Review>>(`/books/${id}/reviews`, { page: reviewsPage });

  const reloadAll = () => { book.reload(); copies.reload(); reviews.reload(); };

  if (book.loading && !book.data) return <Loading />;
  if (book.error && !book.data) return book.error.includes("Не найдено") ? <NotFound /> : <ErrorBox text={book.error} onRetry={book.reload} />;
  const b = book.data!;

  return (
    <>
      <p><Link to="/">← Каталог</Link></p>
      <section className="book-head">
        <Cover src={b.cover} title={b.title} />
        <div>
          <h1>{b.title}</h1>
          <p className="muted">{b.author} · {b.genre}</p>
          <p><Stars value={b.avg_rating} /> · отзывов: {b.reviews_count} · прочитали в этом месяце: {b.read_this_month}</p>
          <p>{b.description || "Описания пока нет."}</p>
          <ReadingControl book={b} onChange={() => book.reload()} />
        </div>
      </section>

      <section>
        <h2>Экземпляры</h2>
        {copies.loading && <Loading />}
        {copies.error && <ErrorBox text={copies.error} onRetry={copies.reload} />}
        {copies.data?.count === 0 && <Empty title="Экземпляров пока нет" hint="Добавьте свой на странице «Моя полка» — если книги нет в каталоге, попросите модератора." />}
        <ul className="list">
          {copies.data?.results.map((c) => (
            <CopyRow key={c.id} copy={c} mine={c.owner.id === user?.id} onDone={() => { notify("Запрос отправлен владельцу."); reloadAll(); }} />
          ))}
        </ul>
      </section>

      <section>
        <h2>Рецензии</h2>
        <ReviewForm book={b} onSaved={reloadAll} />
        {reviews.loading && <Loading />}
        {reviews.error && <ErrorBox text={reviews.error} onRetry={reviews.reload} />}
        {reviews.data?.count === 0 && <Empty title="Рецензий пока нет" hint="Станьте первым." />}
        <ul className="list">
          {reviews.data?.results.map((r) => (
            <li key={r.id} className="card pad">
              <strong>{fullName(r.user)}</strong> · ★ {r.score} · <span className="muted">{fmtDate(r.updated_at)}</span>
              {r.is_hidden && <span className="badge warn">скрыта модератором — видна только вам</span>}
              <p>{r.text || <span className="muted">Без текста</span>}</p>
            </li>
          ))}
        </ul>
        <Pager page={reviewsPage} setPage={setReviewsPage} data={reviews.data} />
      </section>
    </>
  );
}

function CopyRow({ copy, mine, onDone }: { copy: Copy; mine: boolean; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState(tomorrow());
  const [message, setMessage] = useState("");
  const [err, setErr] = useState<unknown>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api(`/copies/${copy.id}/loans`, { method: "POST", body: { requested_return_date: date, message } });
      setOpen(false); onDone();
    } catch (e2) { setErr(e2); }
  }

  return (
    <li className="card pad">
      <div className="row">
        <div>
          <strong>{copy.owner.username}</strong> · {copy.condition_display} · {copy.pickup_place}
        </div>
        {mine ? <span className="badge">ваш экземпляр</span>
          : copy.available ? <button className="primary" onClick={() => setOpen(!open)}>Запросить</button>
          : <span className="badge warn">занят</span>}
      </div>
      {open && (
        <form onSubmit={submit} className="form inline-form">
          <FormError text={err ? errorText(err) : undefined} />
          <Field label="Верну до" error={fieldError(err, "requested_return_date") ?? fieldError(err, "copy")}>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </Field>
          <Field label="Сообщение владельцу" error={fieldError(err, "message")}>
            <input value={message} maxLength={500} onChange={(e) => setMessage(e.target.value)} />
          </Field>
          <button className="primary">Отправить запрос</button>
        </form>
      )}
    </li>
  );
}

function ReadingControl({ book, onChange }: { book: BookDetail; onChange: () => void }) {
  const notify = useToast();
  const current = book.my_reading;
  const [date, setDate] = useState(current?.finished_at ?? "");
  const [err, setErr] = useState<unknown>(null);

  async function save(status: ReadingStatus) {
    setErr(null);
    try {
      await api<ReadingEntry>(`/reading/${book.id}`, {
        method: "PUT",
        body: { status, finished_at: status === "read" && date ? date : null },
      });
      notify("Список чтения обновлён."); onChange();
    } catch (e) { setErr(e); notify(errorText(e), "error"); }
  }
  async function remove() {
    try { await api(`/reading/${book.id}`, { method: "DELETE" }); onChange(); }
    catch (e) { notify(errorText(e), "error"); }
  }

  return (
    <div className="reading-control">
      <span>Мой статус: <strong>{current?.status_display ?? "не в списке"}</strong></span>
      <div className="row wrap">
        <button onClick={() => save("want")}>Хочу прочитать</button>
        <button onClick={() => save("reading")}>Читаю</button>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Дата завершения" />
        <button onClick={() => save("read")}>Прочитал</button>
        {current && <button className="link" onClick={remove}>Убрать</button>}
      </div>
      {fieldError(err, "finished_at") && <small className="err">{fieldError(err, "finished_at")}</small>}
    </div>
  );
}

function ReviewForm({ book, onSaved }: { book: BookDetail; onSaved: () => void }) {
  const notify = useToast();
  const mine = book.my_review;
  const [score, setScore] = useState(mine?.score ?? 5);
  const [text, setText] = useState(mine?.text ?? "");
  const [err, setErr] = useState<unknown>(null);

  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api(`/books/${book.id}/review`, { method: "PUT", body: { score, text } });
      notify(mine ? "Рецензия обновлена." : "Рецензия опубликована."); onSaved();
    } catch (e2) { setErr(e2); }
  }
  async function remove() {
    try { await api(`/books/${book.id}/review`, { method: "DELETE" }); setText(""); notify("Рецензия удалена."); onSaved(); }
    catch (e) { notify(errorText(e), "error"); }
  }

  return (
    <form onSubmit={submit} className="form card pad">
      <h3>{mine ? "Ваша рецензия" : "Написать рецензию"}</h3>
      <FormError text={err && !Object.keys((err as { errors?: object }).errors ?? {}).length ? errorText(err) : undefined} />
      <Field label="Оценка" error={fieldError(err, "score")}>
        <select value={score} onChange={(e) => setScore(Number(e.target.value))}>
          {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </Field>
      <Field label="Текст" error={fieldError(err, "text")}>
        <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      <div className="row wrap">
        <button className="primary">{mine ? "Сохранить изменения" : "Опубликовать"}</button>
        {mine && <button type="button" className="link" onClick={remove}>Удалить рецензию</button>}
      </div>
    </form>
  );
}
