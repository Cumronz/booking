import { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { fieldError } from "../api";
import type { Page } from "../types";

export function Loading() { return <p className="state" role="status">Загрузка…</p>; }
export function ErrorBox({ text, onRetry }: { text: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      {text} {onRetry && <button className="link" onClick={onRetry}>Повторить</button>}
    </div>
  );
}
export function Empty({ title, hint }: { title: string; hint?: string }) {
  return <div className="state"><strong>{title}</strong>{hint && <div>{hint}</div>}</div>;
}

export function Pager<T>({ page, setPage, data }: { page: number; setPage: (n: number) => void; data: Page<T> | null }) {
  if (!data || (!data.next && !data.previous)) return null;
  return (
    <nav className="pager" aria-label="Страницы">
      <button disabled={!data.previous} onClick={() => setPage(page - 1)}>Назад</button>
      <span>Страница {page} · всего {data.count}</span>
      <button disabled={!data.next} onClick={() => setPage(page + 1)}>Вперёд</button>
    </nav>
  );
}

export function Field({ label, error, children }: { label: string; error?: unknown; field?: string; children: ReactNode }) {
  const text = typeof error === "string" ? error : undefined;
  return (
    <label className={"field" + (text ? " has-error" : "")}>
      <span>{label}</span>
      {children}
      {text && <small className="err">{text}</small>}
    </label>
  );
}
export const errOf = fieldError;

export function FormError({ text }: { text?: string }) {
  return text ? <div className="state state-error" role="alert">{text}</div> : null;
}

interface Toast { id: number; text: string; kind: "ok" | "error" }
const ToastCtx = createContext<(text: string, kind?: "ok" | "error") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const notify = useCallback((text: string, kind: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { id, text, kind }]);
    setTimeout(() => setItems((xs) => xs.filter((t) => t.id !== id)), 4500);
  }, []);
  return (
    <ToastCtx.Provider value={notify}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => <div key={t.id} className={"toast " + t.kind}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

export function fullName(u: { username: string; first_name: string; last_name: string }) {
  const n = `${u.first_name} ${u.last_name}`.trim();
  return n || u.username;
}
export function fmtDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString("ru-RU") : "—";
}
export function Cover({ src, title }: { src: string | null; title: string }) {
  return src
    ? <img className="cover" src={src} alt={`Обложка: ${title}`} loading="lazy" />
    : <div className="cover cover-empty" aria-hidden="true">{title.slice(0, 1)}</div>;
}
export function Stars({ value }: { value: number | null }) {
  return <span className="stars" title="Средний рейтинг">{value === null ? "нет оценок" : `★ ${value.toFixed(1)}`}</span>;
}
