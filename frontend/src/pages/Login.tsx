import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorText, fieldError } from "../api";
import { useAuth } from "../auth";
import { Field, FormError } from "../components/ui";

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  if (user) return <Navigate to={from} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await login(username, password); nav(from, { replace: true }); }
    catch (e2) { setErr(e2); }
    finally { setBusy(false); }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <p className="eyebrow">Книжная полка · общая библиотека</p>
        <h1>Истории становятся ближе, когда ими делятся.</h1>
        <p>Находите книги у соседей, ведите список чтения и собирайте библиотеку вместе.</p>
      </section>
      <section className="auth-panel">
        <p className="eyebrow">Ваша библиотека</p>
        <h2>Вход</h2>
        <form onSubmit={submit} className="form">
          <FormError text={err ? errorText(err) : undefined} />
          <Field label="Логин" error={fieldError(err, "username")}>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
          </Field>
          <Field label="Пароль" error={fieldError(err, "password")}>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </Field>
          <button className="primary" disabled={busy}>Войти</button>
        </form>
        <p>Нет аккаунта? <Link to="/register">Зарегистрироваться</Link></p>
      </section>
    </main>
  );
}
