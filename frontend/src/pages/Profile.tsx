import { FormEvent, useState } from "react";
import { api, errorText, fieldError, setToken } from "../api";
import { useAuth } from "../auth";
import { Field, FormError, useToast } from "../components/ui";
import type { User } from "../types";

const ROLE: Record<string, string> = { member: "Участник", moderator: "Модератор", admin: "Администратор" };

export default function Profile() {
  const { user, setUser } = useAuth();
  const notify = useToast();
  const [f, setF] = useState({
    first_name: user?.first_name ?? "", last_name: user?.last_name ?? "", email: user?.email ?? "", bio: user?.bio ?? "",
  });
  const [err, setErr] = useState<unknown>(null);
  const [pw, setPw] = useState({ old_password: "", new_password: "" });
  const [pwErr, setPwErr] = useState<unknown>(null);

  async function save(e: FormEvent) {
    e.preventDefault(); setErr(null);
    try { setUser(await api<User>("/auth/me", { method: "PATCH", body: f })); notify("Профиль сохранён."); }
    catch (e2) { setErr(e2); }
  }
  async function changePassword(e: FormEvent) {
    e.preventDefault(); setPwErr(null);
    try {
      const res = await api<{ token: string }>("/auth/change-password", { method: "POST", body: pw });
      setToken(res.token); setPw({ old_password: "", new_password: "" }); notify("Пароль изменён.");
    } catch (e2) { setPwErr(e2); }
  }

  return (
    <>
      <h1>Профиль</h1>
      <p className="muted">{user?.username} · {user ? ROLE[user.role] : ""}</p>
      <form onSubmit={save} className="form card pad">
        <FormError text={err && !Object.keys((err as { errors?: object }).errors ?? {}).length ? errorText(err) : undefined} />
        <Field label="Имя" error={fieldError(err, "first_name")}><input value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></Field>
        <Field label="Фамилия" error={fieldError(err, "last_name")}><input value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} /></Field>
        <Field label="Email" error={fieldError(err, "email")}><input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="О себе" error={fieldError(err, "bio")}><textarea rows={3} value={f.bio} onChange={(e) => setF({ ...f, bio: e.target.value })} /></Field>
        <button className="primary">Сохранить</button>
      </form>

      <form onSubmit={changePassword} className="form card pad">
        <h3>Смена пароля</h3>
        <Field label="Текущий пароль" error={fieldError(pwErr, "old_password")}>
          <input type="password" autoComplete="current-password" value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} required />
        </Field>
        <Field label="Новый пароль" error={fieldError(pwErr, "new_password")}>
          <input type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required />
        </Field>
        <button>Изменить пароль</button>
      </form>
    </>
  );
}
