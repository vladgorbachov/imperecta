import { Link } from "react-router-dom";

export function Sidebar() {
  return (
    <aside className="w-64 border-r bg-muted/40">
      <nav className="flex flex-col gap-1 p-4">
        <Link to="/dashboard" className="rounded-md px-3 py-2 hover:bg-muted">
          Дашборд
        </Link>
        <Link to="/products" className="rounded-md px-3 py-2 hover:bg-muted">
          Товары
        </Link>
        <Link to="/competitors" className="rounded-md px-3 py-2 hover:bg-muted">
          Конкуренты
        </Link>
        <Link to="/alerts" className="rounded-md px-3 py-2 hover:bg-muted">
          Уведомления
        </Link>
        <Link to="/digests" className="rounded-md px-3 py-2 hover:bg-muted">
          Дайджесты
        </Link>
        <Link to="/import" className="rounded-md px-3 py-2 hover:bg-muted">
          Импорт
        </Link>
        <Link to="/settings" className="rounded-md px-3 py-2 hover:bg-muted">
          Настройки
        </Link>
      </nav>
    </aside>
  );
}
