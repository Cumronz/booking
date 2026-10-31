# Книжная полка

Веб-приложение для общего каталога книг: можно добавлять свои экземпляры, обмениваться книгами, вести список чтения и оставлять отзывы.

## Установка на Windows

Нужны Windows 10/11, интернет и `winget` (он входит в «Установщик приложений»). Откройте PowerShell и установите Git, Python и Node.js:

```powershell
winget install --exact --id Git.Git
winget install --exact --id Python.Python.3.12
winget install --exact --id OpenJS.NodeJS.LTS
```

После установки закройте PowerShell, откройте его снова и скачайте проект:

```powershell
git clone https://github.com/Cumronz/booking.git
cd booking
```

## Запуск backend

В первом окне PowerShell выполните команды из папки проекта:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Оставьте это окно открытым: backend работает на `http://127.0.0.1:8000`. База данных SQLite создаётся автоматически; отдельно устанавливать сервер базы данных не нужно.

## Запуск сайта

Откройте **второе** окно PowerShell. Если вы клонировали проект в домашнюю папку Windows, выполните команды ниже. Если выбрали другое место, замените `$HOME\booking` на полный путь к папке проекта:

```powershell
cd "$HOME\booking\frontend"
npm install
npm run dev
```

Откройте адрес, который покажет команда, обычно `http://localhost:5173`. Не закрывайте оба окна PowerShell, пока пользуетесь приложением. Frontend отправляет запросы backend на порт `8000`.

## Демо-аккаунты

| Логин | Пароль | Роль |
|---|---|---|
| `admin` | `admin12345` | администратор |
| `moder` | `demo12345` | модератор |
| `Eldar` | `demo12345` | участник |
| `Atabek` | `demo12345` | участник |
| `Sosat` | `demo12345` | участник |

## Проверка и остановка

Для запуска backend-тестов откройте PowerShell и перейдите в папку backend:

```powershell
cd "$HOME\booking\backend"
.\.venv\Scripts\python.exe manage.py test
```

Для проверки frontend-сборки откройте PowerShell и перейдите в папку frontend:

```powershell
cd "$HOME\booking\frontend"
npm run build
```

Если проект находится не в домашней папке, замените `$HOME\booking` на полный путь к нему.

Для остановки серверов нажмите `Ctrl+C` в каждом окне PowerShell.
