import { Link } from "react-router-dom";

export function Forbidden() {
  return <div className="state"><h1>403</h1><p>У вас нет доступа к этой странице.</p><Link to="/">В каталог</Link></div>;
}
export function NotFound() {
  return <div className="state"><h1>404</h1><p>Такой страницы нет.</p><Link to="/">В каталог</Link></div>;
}
