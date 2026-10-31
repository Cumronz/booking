import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api";
import { useApi } from "../hooks";
import { Empty, ErrorBox, fmtDate, fullName, Loading, Pager, useToast } from "../components/ui";
import type { Loan, LoanAction, Page } from "../types";

const LABEL: Record<LoanAction, string> = {
  accept: "Принять", reject: "Отклонить", cancel: "Отменить", "hand-over": "Отметить передачу", return: "Отметить возврат",
};

export default function Exchanges() {
  const notify = useToast();
  const [tab, setTab] = useState<"incoming" | "outgoing">("incoming");
  const [page, setPage] = useState(1);
  const loans = useApi<Page<Loan>>("/loans", { role: tab, page });

  async function run(loan: Loan, action: LoanAction) {
    try {
      await api(`/loans/${loan.id}/${action}`, { method: "POST" });
      notify("Готово."); loans.reload();
    } catch (e) { notify(errorText(e), "error"); loans.reload(); }
  }

  return (
    <>
      <h1>Обмены</h1>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "incoming"} onClick={() => { setTab("incoming"); setPage(1); }}>Входящие (мои книги)</button>
        <button role="tab" aria-selected={tab === "outgoing"} onClick={() => { setTab("outgoing"); setPage(1); }}>Исходящие (я беру)</button>
      </div>

      {loans.loading && <Loading />}
      {loans.error && <ErrorBox text={loans.error} onRetry={loans.reload} />}
      {loans.data?.count === 0 && (
        <Empty title={tab === "incoming" ? "Пока никто не просил ваши книги" : "Вы ещё ничего не запрашивали"}
          hint={tab === "outgoing" ? "Выберите книгу в каталоге и нажмите «Запросить»." : undefined} />
      )}
      <ul className="list">
        {loans.data?.results.map((l) => (
          <li key={l.id} className="card pad">
            <div className="row">
              <strong><Link to={`/books/${l.book.id}`}>{l.book.title}</Link></strong>
              <span className={"badge " + (l.is_overdue ? "danger" : l.status === "returned" ? "ok" : "")}>
                {l.is_overdue ? `просрочена на ${l.days_overdue} дн.` : l.status_display}
              </span>
            </div>
            <p className="muted">
              {tab === "incoming" ? `Просит: ${fullName(l.borrower)}` : `Владелец: ${fullName(l.owner)}`} · вернуть до {fmtDate(l.requested_return_date)} · место: {l.pickup_place}
            </p>
            {l.message && <p>«{l.message}»</p>}
            {l.returned_at && <p className="muted">Возвращена {fmtDate(l.returned_at)}</p>}
            {l.available_actions.length > 0 && (
              <div className="row wrap">
                {l.available_actions.map((a) => (
                  <button key={a} className={a === "accept" || a === "hand-over" || a === "return" ? "primary" : ""} onClick={() => run(l, a)}>{LABEL[a]}</button>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
      <Pager page={page} setPage={setPage} data={loans.data} />
    </>
  );
}
