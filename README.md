# Книжная полка — общая библиотека личных книг

Django REST Framework (backend) + React/TypeScript/Vite (frontend).
Студенты ведут общий каталог, добавляют свои экземпляры, одалживают книги друг другу, ведут список чтения и пишут рецензии.

```
backend/    Django + DRF, приложения accounts (пользователи, роли) и library (книги, обмены, чтение, отзывы)
frontend/   React + TypeScript (Vite), страницы из задания
```

## Запуск backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Сервер доступен по адресу `http://127.0.0.1:8000`. Для повторного заполнения базы демо-данными используйте `seed_demo --reset`. Тесты: `.venv\Scripts\python.exe manage.py test`.

### Демо-аккаунты (пароли вымышленные)

| Логин | Пароль | Роль |
|---|---|---|
| `admin` | `admin12345` | администратор (назначает роли; также /admin/) |
| `moder` | `demo12345` | модератор (справочник книг, скрытие рецензий) |
| `anna`, `boris`, `clara` | `demo12345` | участники |

Демо-данные: 15 произведений, 20 экземпляров (у 5 книг по два экземпляра у разных владельцев), 5 пользователей, 10 передач во всех статусах (включая просроченную), 10 рецензий (одна скрыта), записи чтения. Обложки генерируются кодом (Pillow), поэтому вопросов с лицензией нет.

## Запуск frontend

Для запуска требуется Node.js версии 22.12 или новее.

```bash
cd frontend
npm install
npm run dev
npm run build
```

Frontend доступен по адресу `http://localhost:5173`; запросы `/api` и `/media` проксируются на порт 8000. Команда `npm run build` проверяет типы и собирает приложение.

## Модель данных

```mermaid
erDiagram
    User ||--o{ Copy : "владеет (PROTECT)"
    User ||--o{ Loan : "заёмщик (PROTECT)"
    User ||--o{ ReadingEntry : ""
    User ||--o{ Review : ""
    Book ||--o{ Copy : "PROTECT"
    Book ||--o{ ReadingEntry : "PROTECT"
    Book ||--o{ Review : "PROTECT"
    Copy ||--o{ Loan : "PROTECT"
    User { string role "member | moderator | admin" }
    Book { string title string author string genre text description image cover string search_key UK }
    Copy { fk book fk owner string condition string pickup_place bool is_active }
    Loan { fk copy fk borrower date requested_return_date string status datetime handed_at datetime returned_at }
    ReadingEntry { fk user fk book string status date finished_at }
    Review { fk user fk book int score text text bool is_hidden }
```

Что отличается от предложенной модели и почему:

* `Book.search_key` — нормализованный ключ «название|автор» (casefold). Даёт уникальность книги без учёта регистра и корректный поиск по кириллице (в SQLite `LIKE` не различает регистр только для ASCII).
* `Loan.message` — необязательная приписка к запросу; `User.role`, `User.bio` — роль и профиль.
* Каскадных удалений нет: все внешние ключи `PROTECT`, история обменов не теряется. Экземпляр с историей не удаляется, а снимается с полки (`is_active=false`).

Ограничения на уровне БД:

| Ограничение | Смысл |
|---|---|
| `uniq_busy_loan_per_copy` (partial unique: `copy` где статус `accepted`/`handed_over`) | один экземпляр — не более одной принятой/активной передачи, даже при гонке запросов |
| `uniq_pending_loan_per_borrower` | нельзя дважды подать ожидающий запрос на один экземпляр |
| `uniq_review_user_book`, `uniq_reading_user_book` | одна рецензия и одна запись чтения на пару пользователь/книга |
| `review_score_1_5`, `reading_finished_only_if_read` | оценка 1–5; дата завершения только у «прочитал» |

Индексы: внешние ключи, `title/author/genre`, `(book, is_active)`, `(owner, is_active)`, `(status, requested_return_date)`, `(borrower, status)`, `(copy, status)`, `(book, is_hidden)`, `(status, finished_at)`.

## Бизнес-правила (реализованы в `library/services.py`)

* Переходы: `ожидает → принята / отклонена / отменена`, `принята → передана / отменена`, `передана → возвращена`. Остальные — **409**.
* Каждый переход выполняется в транзакции с блокировкой экземпляра (`select_for_update`), плюс partial unique в БД как последний рубеж.
* При принятии запроса остальные ожидающие запросы на этот экземпляр автоматически отклоняются.
* Нельзя запросить свой экземпляр (400), прошлую дату или дату дальше года (400), снятый с полки или занятый экземпляр (409).
* Принять, отклонить, отметить передачу и возврат может только владелец (403); отменить — владелец или заёмщик. Посторонний не видит чужие запросы (404).
* Переданный экземпляр нельзя ни снять с полки, ни удалить (409); при снятии ожидающие запросы отклоняются; при наличии принятого запроса сначала нужно его отменить.
* Просрочка вычисляется: статус `handed_over` и `requested_return_date < сегодня` (`is_overdue`, `days_overdue`, фильтр `?overdue=1`).
* Рейтинг книги считается без скрытых рецензий; «прочитано за месяц» — по `finished_at`.
* Регистрация всегда создаёт участника; роли назначает только администратор (`PATCH /api/users/{id}/role`). Свою роль менять нельзя.

## API

Авторизация: заголовок `Authorization: Token <token>`. Все пути с префиксом `/api`, без завершающего `/`. Списки пагинируются: `?page=`, `?page_size=` (до 50), ответ `{count, next, previous, results}`.

| Метод и путь | Доступ | Описание |
|---|---|---|
| `POST /auth/register`, `/auth/login` | все | возвращает `{token, user}` |
| `POST /auth/logout`, `GET/PATCH /auth/me`, `POST /auth/change-password` | вошедший | выход, профиль, смена пароля |
| `GET /books` | вошедший | `?search=&genre=&available=1&ordering=title\|author\|-avg_rating\|-created_at` |
| `GET /books/{id}` | вошедший | + `my_review`, `my_reading`; в списке: `avg_rating`, `reviews_count`, `available_copies`, `read_this_month` |
| `POST/PATCH/DELETE /books[/{id}]` | модератор | справочник (multipart для обложки) |
| `GET /genres` | вошедший | жанры со счётчиками |
| `GET /books/{id}/copies`, `GET /books/{id}/reviews` | вошедший | экземпляры и рецензии книги |
| `PUT /books/{id}/review`, `DELETE …` | вошедший | создать/изменить свою рецензию (201/200) |
| `GET /copies` | вошедший | `?mine=1&book=&available=1` |
| `POST /copies`, `PATCH/DELETE /copies/{id}` | владелец | своя полка |
| `POST /copies/{id}/loans` | вошедший | `{requested_return_date, message}` — запрос на книгу |
| `GET /loans` | участники запроса | `?role=incoming\|outgoing&status=&overdue=1`; в ответе `available_actions` |
| `POST /loans/{id}/accept\|reject\|hand-over\|return` | владелец | действия владельца |
| `POST /loans/{id}/cancel` | заёмщик / владелец | отмена |
| `GET /reading`, `GET /reading/stats` | вошедший | список и статистика (по статусам, месяц, год, 6 месяцев) |
| `PUT/GET/DELETE /reading/{book_id}` | вошедший | `{status: want\|reading\|read, finished_at?}` |
| `GET /reviews`, `POST /reviews/{id}/hide\|unhide` | модератор | модерация (`?hidden=0\|1`) |
| `GET /users`, `PATCH /users/{id}/role` | администратор | роли |

Ошибки: `400` — ввод, `401` — нет/неверный токен, `403` — нет прав, `404` — нет объекта, `409` — конфликт состояния. Формат всегда один:

```json
{ "detail": "Проверьте введённые данные.", "errors": { "requested_return_date": ["Дата возврата должна быть в будущем."] } }
```

## Критерии приёмки → где проверяются

| Критерий | Тест (`library/tests.py`) |
|---|---|
| Два экземпляра одной книги бронируются независимо | `test_two_copies_are_booked_independently` |
| Принять → передать → вернуть, доступность восстанавливается | `test_full_cycle_restores_availability` |
| Нельзя принять двух заёмщиков на один экземпляр | `test_cannot_accept_two_borrowers_for_one_copy` |
| Редактирование отзыва меняет рейтинг без дубликата | `test_review_edit_updates_rating_without_duplicate` |
| Права, ошибки данных, запрещённые переходы | `PermissionTests`, `ValidationAndStateTests` |
| Запуск по README на чистой базе | шаги выше |
| Сценарий через интерфейс, сохранение после перезагрузки | вручную: войти как `anna` → «Обмены» → принять запрос → перезагрузить страницу |

Сценарий демонстрации через интерфейс: `boris` открывает книгу «Мастер и Маргарита» → два экземпляра (anna и boris) → `clara` запрашивает оба → `anna` принимает один в «Обмены», отмечает передачу и возврат → в каталоге счётчик «Доступно» меняется.
