import { NavLink, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { ReactNode } from "react";
import { useAuth } from "./auth";
import { Loading } from "./components/ui";
import type { Role } from "./types";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Catalog from "./pages/Catalog";
import BookPage from "./pages/BookPage";
import Shelf from "./pages/Shelf";
import Exchanges from "./pages/Exchanges";
import Reading from "./pages/Reading";
import Moderation from "./pages/Moderation";
import Profile from "./pages/Profile";
import { Forbidden, NotFound } from "./pages/Errors";

function Layout() {
  const { user, logout } = useAuth();
  const isModerator = user?.role === "moderator" || user?.role === "admin";
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand">Книжная полка</NavLink>
        <nav className="nav" aria-label="Основная навигация">
          <NavLink to="/" end>Каталог</NavLink>
          <NavLink to="/shelf">Моя полка</NavLink>
          <NavLink to="/exchanges">Обмены</NavLink>
          <NavLink to="/reading">Моё чтение</NavLink>
          {isModerator && <NavLink to="/moderation">Модерация</NavLink>}
        </nav>
        <div className="who">
          <NavLink to="/profile">{user?.username}</NavLink>
          <button onClick={logout}>Выйти</button>
        </div>
      </header>
      <main className="page"><Outlet /></main>
    </div>
  );
}

function Protected() {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <Layout />;
}

function RequireRole({ min, children }: { min: Role; children: ReactNode }) {
  const { user } = useAuth();
  const rank: Record<Role, number> = { member: 0, moderator: 1, admin: 2 };
  if (!user || rank[user.role] < rank[min]) return <Forbidden />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Protected />}>
        <Route path="/" element={<Catalog />} />
        <Route path="/books/:id" element={<BookPage />} />
        <Route path="/shelf" element={<Shelf />} />
        <Route path="/exchanges" element={<Exchanges />} />
        <Route path="/reading" element={<Reading />} />
        <Route path="/moderation" element={<RequireRole min="moderator"><Moderation /></RequireRole>} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/403" element={<Forbidden />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
