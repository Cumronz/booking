import io
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from library.models import Book, Copy, Loan, ReadingEntry, Review

BOOKS = [
    ("Мастер и Маргарита", "Михаил Булгаков", "Роман", "Дьявол приезжает в Москву 1930-х, а параллельно разворачивается история Пилата."),
    ("Преступление и наказание", "Фёдор Достоевский", "Роман", "Бедный студент решает, что имеет право на преступление, и расплачивается за это."),
    ("Война и мир", "Лев Толстой", "Роман", "Судьбы нескольких семей на фоне наполеоновских войн."),
    ("1984", "Джордж Оруэлл", "Антиутопия", "Общество тотального контроля и человек, который пытается думать сам."),
    ("Дюна", "Фрэнк Герберт", "Фантастика", "Борьба домов за пустынную планету, единственный источник пряности."),
    ("Три товарища", "Эрих Мария Ремарк", "Роман", "Дружба и любовь в Германии между двумя войнами."),
    ("Маленький принц", "Антуан де Сент-Экзюпери", "Сказка", "Лётчик в пустыне встречает мальчика с далёкой планеты."),
    ("Сто лет одиночества", "Габриэль Гарсиа Маркес", "Магический реализм", "История рода Буэндиа в вымышленном городке Макондо."),
    ("Понедельник начинается в субботу", "Аркадий и Борис Стругацкие", "Фантастика", "Программист попадает в институт, где работают настоящие волшебники."),
    ("Этюд в багровых тонах", "Артур Конан Дойл", "Детектив", "Первое дело Шерлока Холмса и доктора Ватсона."),
    ("Убийство в «Восточном экспрессе»", "Агата Кристи", "Детектив", "Пуаро расследует убийство в поезде, застрявшем в снегах."),
    ("Хоббит", "Дж. Р. Р. Толкин", "Фэнтези", "Бильбо Бэггинс отправляется с гномами за сокровищами дракона."),
    ("451 градус по Фаренгейту", "Рэй Брэдбери", "Антиутопия", "Пожарный, который сжигает книги, начинает задавать вопросы."),
    ("Краткая история времени", "Стивен Хокинг", "Научпоп", "От Большого взрыва до чёрных дыр простым языком."),
    ("Чистый код", "Роберт Мартин", "Программирование", "Как писать код, который удобно читать и поддерживать."),
]

PLACES = ["Общежитие №3, вахта", "Библиотека, 2 этаж", "Корпус А, кафетерий", "Парк у главного входа"]
CONDITIONS = ["new", "good", "good", "fair", "worn"]


def make_cover(index: int):
    from PIL import Image, ImageDraw

    palettes = [
        ((25, 47, 73), (245, 241, 232)),
        ((242, 238, 228), (34, 52, 73)),
        ((54, 65, 78), (239, 235, 226)),
        ((225, 222, 214), (42, 57, 75)),
        ((38, 55, 75), (223, 220, 212)),
    ]
    background, ink = palettes[index % len(palettes)]
    img = Image.new("RGB", (300, 450), background)
    d = ImageDraw.Draw(img)
    d.rectangle([19, 19, 281, 431], outline=ink, width=2)
    d.rectangle([38, 64, 45, 271], fill=ink)
    d.rectangle([62, 92, 238, 97], fill=ink)
    d.rectangle([62, 108, 204, 112], fill=ink)
    d.rectangle([62, 124, 224, 128], fill=ink)
    d.line([38, 306, 262, 306], fill=ink, width=2)
    d.rectangle([38, 331, 154 + (index % 4) * 22, 337], fill=ink)
    d.rectangle([38, 350, 112 + (index % 3) * 24, 354], fill=ink)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "Создаёт демонстрационные данные (на чистой базе)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="сначала удалить демо-данные")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            for model in (Loan, Review, ReadingEntry, Copy, Book):
                model.objects.all().delete()
            User.objects.filter(
                username__in=["admin", "moder", "Eldar", "Atabek", "Sosat", "anna", "boris", "clara"]
            ).delete()
        elif Book.objects.exists() or User.objects.filter(username="admin").exists():
            raise CommandError("База уже содержит данные. Запустите с --reset или используйте чистую базу.")

        today = timezone.localdate()
        now = timezone.now()

        admin = User.objects.create_superuser("admin", "admin@example.com", "admin12345")
        moder = User.objects.create_user("moder", "moder@example.com", "demo12345", role=User.Role.MODERATOR)
        eldar = User.objects.create_user("Eldar", "eldar@example.com", "demo12345", first_name="Eldar")
        atabek = User.objects.create_user("Atabek", "atabek@example.com", "demo12345", first_name="Atabek")
        sosat = User.objects.create_user("Sosat", "sosat@example.com", "demo12345", first_name="Sosat")
        members = [eldar, atabek, sosat]

        books = []
        for i, (title, author, genre, desc) in enumerate(BOOKS):
            b = Book.objects.create(title=title, author=author, genre=genre, description=desc)
            try:
                b.cover.save(f"cover_{i}.png", make_cover(i), save=True)
            except Exception as exc:
                self.stderr.write(f"Обложка {i} пропущена: {exc}")
            books.append(b)

        copies = []
        for i, b in enumerate(books):
            copies.append(Copy.objects.create(book=b, owner=members[i % 3], condition=CONDITIONS[i % 5], pickup_place=PLACES[i % 4]))
        for j in range(5):
            copies.append(
                Copy.objects.create(book=books[j], owner=members[(j + 1) % 3], condition="good", pickup_place=PLACES[(j + 2) % 4])
            )

        S = Loan.Status
        plan = [
            (0, atabek, S.RETURNED, -20, -6),
            (1, eldar, S.RETURNED, -15, -3),
            (2, eldar, S.HANDED_OVER, 7, None),
            (3, sosat, S.HANDED_OVER, -5, None),
            (4, sosat, S.ACCEPTED, 10, None),
            (5, atabek, S.PENDING, 12, None),
            (5, eldar, S.PENDING, 14, None),
            (6, atabek, S.REJECTED, 9, None),
            (7, sosat, S.CANCELLED, 9, None),
            (15, sosat, S.PENDING, 8, None),
        ]
        for copy_idx, borrower, st, due_offset, returned_offset in plan:
            loan = Loan.objects.create(
                copy=copies[copy_idx],
                borrower=borrower,
                requested_return_date=today + timedelta(days=due_offset),
                status=st,
                message="Привет! Можно взять почитать?",
            )
            if st in (S.HANDED_OVER, S.RETURNED):
                loan.handed_at = now + timedelta(days=min(due_offset, 0) - 7)
            if st == S.RETURNED:
                loan.returned_at = now + timedelta(days=returned_offset)
            loan.save()

        reviews = [
            (eldar, 0, 5, "Перечитываю каждый год."),
            (atabek, 0, 4, "Сильно, хотя вторая половина слабее."),
            (sosat, 0, 5, "Лучшее, что я читала."),
            (eldar, 3, 5, "Страшно актуально."),
            (atabek, 4, 4, "Мир проработан отлично."),
            (sosat, 4, 3, "Тяжело читать начало."),
            (eldar, 6, 5, "Короткая и очень тёплая."),
            (atabek, 9, 4, "Классический детектив."),
            (sosat, 11, 5, "Уютное приключение."),
            (atabek, 14, 2, "Реклама! Купите курс дёшево!!!"),
        ]
        for user, bi, score, text in reviews:
            Review.objects.create(user=user, book=books[bi], score=score, text=text, is_hidden=(text.startswith("Реклама")))

        first_of_month = today.replace(day=1)
        entries = [
            (eldar, 0, "read", today), (eldar, 3, "read", first_of_month), (eldar, 4, "reading", None),
            (atabek, 0, "read", first_of_month), (atabek, 9, "read", today - timedelta(days=45)), (atabek, 12, "want", None),
            (sosat, 0, "read", today), (sosat, 11, "reading", None), (sosat, 7, "want", None),
        ]
        for user, bi, st, fin in entries:
            ReadingEntry.objects.create(user=user, book=books[bi], status=st, finished_at=fin)

        self.stdout.write(self.style.SUCCESS(
            f"Готово: пользователей 5, книг {Book.objects.count()}, экземпляров {Copy.objects.count()}, "
            f"передач {Loan.objects.count()}, отзывов {Review.objects.count()}."
        ))
        self.stdout.write("Аккаунты: admin/admin12345 (администратор), moder/demo12345 (модератор), "
                          "Eldar|Atabek|Sosat/demo12345 (участники).")
