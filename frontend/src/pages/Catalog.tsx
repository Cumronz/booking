import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks";
import { Cover, Empty, ErrorBox, Loading, Pager, Stars } from "../components/ui";
import type { Book, Page } from "../types";

export default function Catalog() {
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const [genre, setGenre] = useState("");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [ordering, setOrdering] = useState("title");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => { setApplied(q); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const genres = useApi<{ genre: string; count: number }[]>("/genres");
  const books = useApi<Page<Book>>("/books", {
    search: applied, genre, available: onlyAvailable ? 1 : undefined, ordering, page,
  });

  return (
    <>
      <section className="catalog-intro">
        <div>
          <p className="eyebrow">Общая библиотека сообщества</p>
          <h1>Книжный каталог</h1>
          <p className="catalog-description">Находите книги, делитесь своими экземплярами и открывайте для себя новые истории.</p>
        </div>
        <div className="catalog-count" aria-live="polite">
          <strong>{books.data?.count ?? "—"}</strong>
          <span>книг в подборке</span>
        </div>
      </section>
      <div className="filters">
        <input type="search" placeholder="Название или автор" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Поиск" />
        <select value={genre} onChange={(e) => { setGenre(e.target.value); setPage(1); }} aria-label="Жанр">
          <option value="">Все жанры</option>
          {genres.data?.map((g) => <option key={g.genre} value={g.genre}>{g.genre} ({g.count})</option>)}
        </select>
        <select value={ordering} onChange={(e) => setOrdering(e.target.value)} aria-label="Сортировка">
          <option value="title">По названию</option>
          <option value="author">По автору</option>
          <option value="-avg_rating">По рейтингу</option>
          <option value="-created_at">Новые</option>
        </select>
        <label className="check">
          <input type="checkbox" checked={onlyAvailable} onChange={(e) => { setOnlyAvailable(e.target.checked); setPage(1); }} />
          Только доступные
        </label>
      </div>

      {books.loading && <Loading />}
      {books.error && <ErrorBox text={books.error} onRetry={books.reload} />}
      {!books.loading && !books.error && books.data?.count === 0 && (
        <Empty title="Ничего не найдено" hint="Измените запрос или сбросьте фильтры." />
      )}
      <ul className="grid">
        {books.data?.results.map((b) => (
          <li key={b.id} className="card book-card">
            <Link to={`/books/${b.id}`} aria-label={`Открыть книгу «${b.title}»`}><Cover src={b.cover} title={b.title} /></Link>
            <div className="card-body">
              <h3><Link to={`/books/${b.id}`}>{b.title}</Link></h3>
              <p className="muted">{b.author} · {b.genre}</p>
              <p><Stars value={b.avg_rating} /></p>
              <p className={b.available_copies > 0 ? "ok" : "muted"}>
                {b.available_copies > 0 ? `Доступно: ${b.available_copies} из ${b.copies_total}` : b.copies_total ? "Все экземпляры заняты" : "Экземпляров нет"}
              </p>
            </div>
          </li>
        ))}
      </ul>
      <Pager page={page} setPage={setPage} data={books.data} />
    </>
  );
}
