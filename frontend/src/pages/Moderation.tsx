import { FormEvent, useState } from "react";
import { api, errorText, fieldError } from "../api";
import { useAuth } from "../auth";
import { useApi } from "../hooks";
import { Cover, Empty, ErrorBox, Field, FormError, fmtDate, fullName, Loading, Pager, useToast } from "../components/ui";
import type { Book, Page, Review, Role, User } from "../types";

type Tab = "books" | "reviews" | "users";

export default function Moderation() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("books");
  return (
    <>
      <h1>Модерация</h1>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "books"} onClick={() => setTab("books")}>Справочник книг</button>
        <button role="tab" aria-selected={tab === "reviews"} onClick={() => setTab("reviews")}>Рецензии</button>
        {user?.role === "admin" && <button role="tab" aria-selected={tab === "users"} onClick={() => setTab("users")}>Пользователи</button>}
      </div>
      {tab === "books" && <BooksAdmin />}
      {tab === "reviews" && <ReviewsAdmin />}
      {tab === "users" && user?.role === "admin" && <UsersAdmin />}
    </>
  );
}

function BooksAdmin() {
  const notify = useToast();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const books = useApi<Page<Book>>("/books", { search: q, page });
  const [editing, setEditing] = useState<Book | null>(null);
  const [form, setForm] = useState({ title: "", author: "", genre: "", description: "" });
  const [cover, setCover] = useState<File | null>(null);
  const [err, setErr] = useState<unknown>(null);

  function startEdit(b: Book | null) {
    setEditing(b); setErr(null); setCover(null);
    setForm(b ? { title: b.title, author: b.author, genre: b.genre, description: b.description } : { title: "", author: "", genre: "", description: "" });
  }

  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    if (cover) fd.append("cover", cover);
    try {
      await api(editing ? `/books/${editing.id}` : "/books", { method: editing ? "PATCH" : "POST", form: fd });
      notify(editing ? "Книга обновлена." : "Книга добавлена в справочник.");
      startEdit(null); books.reload();
    } catch (e2) { setErr(e2); }
  }
  async function remove(b: Book) {
    if (!confirm(`Удалить «${b.title}» из справочника?`)) return;
    try { await api(`/books/${b.id}`, { method: "DELETE" }); notify("Книга удалена."); books.reload(); }
    catch (e) { notify(errorText(e), "error"); }
  }

  return (
    <>
      <form onSubmit={submit} className="form card pad">
        <h3>{editing ? `Редактирование: ${editing.title}` : "Новая книга"}</h3>
        <FormError text={err && !Object.keys((err as { errors?: object }).errors ?? {}).length ? errorText(err) : undefined} />
        <Field label="Название" error={fieldError(err, "title")}><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required /></Field>
        <Field label="Автор" error={fieldError(err, "author")}><input value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} required /></Field>
        <Field label="Жанр" error={fieldError(err, "genre")}><input value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} required /></Field>
        <Field label="Описание" error={fieldError(err, "description")}><textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <Field label="Обложка (изображение)" error={fieldError(err, "cover")}>
          <input type="file" accept="image/*" onChange={(e) => setCover(e.target.files?.[0] ?? null)} />
        </Field>
        <div className="row wrap">
          <button className="primary">{editing ? "Сохранить" : "Добавить"}</button>
          {editing && <button type="button" onClick={() => startEdit(null)}>Отмена</button>}
        </div>
      </form>

      <input type="search" placeholder="Поиск по справочнику" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Поиск" />
      {books.loading && <Loading />}
      {books.error && <ErrorBox text={books.error} onRetry={books.reload} />}
      {books.data?.count === 0 && <Empty title="Ничего не найдено" />}
      <ul className="list">
        {books.data?.results.map((b) => (
          <li key={b.id} className="card pad row">
            <div className="row"><Cover src={b.cover} title={b.title} /><div><strong>{b.title}</strong><div className="muted">{b.author} · {b.genre} · экземпляров: {b.copies_total}</div></div></div>
            <div className="row wrap">
              <button onClick={() => { startEdit(b); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Изменить</button>
              <button className="link danger" onClick={() => remove(b)}>Удалить</button>
            </div>
          </li>
        ))}
      </ul>
      <Pager page={page} setPage={setPage} data={books.data} />
    </>
  );
}

function ReviewsAdmin() {
  const notify = useToast();
  const [page, setPage] = useState(1);
  const [hidden, setHidden] = useState("");
  const reviews = useApi<Page<Review>>("/reviews", { hidden, page });

  async function toggle(r: Review) {
    try { await api(`/reviews/${r.id}/${r.is_hidden ? "unhide" : "hide"}`, { method: "POST" }); reviews.reload(); }
    catch (e) { notify(errorText(e), "error"); }
  }

  return (
    <>
      <select value={hidden} onChange={(e) => { setHidden(e.target.value); setPage(1); }} aria-label="Фильтр">
        <option value="">Все рецензии</option>
        <option value="0">Только видимые</option>
        <option value="1">Только скрытые</option>
      </select>
      {reviews.loading && <Loading />}
      {reviews.error && <ErrorBox text={reviews.error} onRetry={reviews.reload} />}
      {reviews.data?.count === 0 && <Empty title="Рецензий нет" />}
      <ul className="list">
        {reviews.data?.results.map((r) => (
          <li key={r.id} className="card pad">
            <div className="row">
              <div><strong>{r.book_title}</strong> · {fullName(r.user)} · ★ {r.score} · <span className="muted">{fmtDate(r.updated_at)}</span></div>
              <button onClick={() => toggle(r)}>{r.is_hidden ? "Показать" : "Скрыть"}</button>
            </div>
            {r.is_hidden && <span className="badge warn">скрыта</span>}
            <p>{r.text || <span className="muted">Без текста</span>}</p>
          </li>
        ))}
      </ul>
      <Pager page={page} setPage={setPage} data={reviews.data} />
    </>
  );
}

function UsersAdmin() {
  const notify = useToast();
  const { user: me } = useAuth();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const users = useApi<Page<User>>("/users", { search: q, page });

  async function setRole(u: User, role: Role) {
    try { await api(`/users/${u.id}/role`, { method: "PATCH", body: { role } }); notify("Роль изменена."); users.reload(); }
    catch (e) { notify(errorText(e), "error"); users.reload(); }
  }

  return (
    <>
      <input type="search" placeholder="Поиск пользователя" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Поиск" />
      {users.loading && <Loading />}
      {users.error && <ErrorBox text={users.error} onRetry={users.reload} />}
      <ul className="list">
        {users.data?.results.map((u) => (
          <li key={u.id} className="card pad row">
            <div><strong>{u.username}</strong> <span className="muted">{fullName(u)}</span></div>
            <select value={u.role} disabled={u.id === me?.id} onChange={(e) => setRole(u, e.target.value as Role)} aria-label={`Роль ${u.username}`}>
              <option value="member">Участник</option>
              <option value="moderator">Модератор</option>
              <option value="admin">Администратор</option>
            </select>
          </li>
        ))}
      </ul>
      <Pager page={page} setPage={setPage} data={users.data} />
    </>
  );
}
