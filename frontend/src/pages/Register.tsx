import { ChangeEvent, FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { fieldError } from "../api";
import { useAuth } from "../auth";
import { Field, FormError } from "../components/ui";

export default function Register() {
  const { user, register } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ username: "", password: "", email: "", first_name: "", last_name: "" });
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  const set = (k: keyof typeof f) => (e: ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await register(f); nav("/", { replace: true }); }
    catch (e2) { setErr(e2); }
    finally { setBusy(false); }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <p className="eyebrow">Книжная полка · общая библиотека</p>
        <h1>Своя полка. Общие истории.</h1>
        <p>Создайте аккаунт, чтобы делиться книгами, следить за обменами и отмечать прочитанное.</p>
      </section>
      <section className="auth-panel">
        <p className="eyebrow">Присоединиться</p>
        <h2>Регистрация</h2>
        <form onSubmit={submit} className="form">
          <FormError text={fieldError(err, "non_field_errors")} />
          <Field label="Логин" error={fieldError(err, "username")}><input value={f.username} onChange={set("username")} autoComplete="username" required /></Field>
          <Field label="Пароль (минимум 8 символов)" error={fieldError(err, "password")}>
            <input type="password" value={f.password} onChange={set("password")} autoComplete="new-password" required />
          </Field>
          <Field label="Имя" error={fieldError(err, "first_name")}><input value={f.first_name} onChange={set("first_name")} autoComplete="given-name" /></Field>
          <Field label="Фамилия" error={fieldError(err, "last_name")}><input value={f.last_name} onChange={set("last_name")} autoComplete="family-name" /></Field>
          <Field label="Email" error={fieldError(err, "email")}><input type="email" value={f.email} onChange={set("email")} autoComplete="email" /></Field>
          <button className="primary" disabled={busy}>Создать аккаунт</button>
        </form>
        <p>Уже есть аккаунт? <Link to="/login">Войти</Link></p>
      </section>
    </main>
  );
}
