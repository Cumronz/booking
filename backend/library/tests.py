from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from library.models import Book, Copy, Loan, Review


class BaseCase(APITestCase):
    def setUp(self):
        mk = lambda name, **kw: User.objects.create_user(name, password="pass12345", **kw)  # noqa: E731
        self.anna, self.boris, self.clara = mk("anna"), mk("boris"), mk("clara")
        self.moder = mk("moder", role=User.Role.MODERATOR)
        self.admin = User.objects.create_superuser("root", "r@example.com", "pass12345")
        self.book = Book.objects.create(title="Дюна", author="Фрэнк Герберт", genre="Фантастика")

    def as_(self, user):
        self.client.force_authenticate(user)

    def copy_of(self, owner, book=None):
        return Copy.objects.create(book=book or self.book, owner=owner, pickup_place="Общежитие")

    def due(self, days=7):
        return (timezone.localdate() + timedelta(days=days)).isoformat()

    def request_loan(self, borrower, copy, days=7):
        self.as_(borrower)
        return self.client.post(f"/api/copies/{copy.id}/loans", {"requested_return_date": self.due(days)}, format="json")

    def act(self, user, loan_id, action):
        self.as_(user)
        return self.client.post(f"/api/loans/{loan_id}/{action}")


class CriteriaTests(BaseCase):
    """Критерии приёмки из задания."""

    def test_two_copies_are_booked_independently(self):
        c1, c2 = self.copy_of(self.anna), self.copy_of(self.boris)
        l1 = self.request_loan(self.clara, c1).data["id"]
        self.request_loan(self.clara, c2)
        self.assertEqual(self.act(self.anna, l1, "accept").status_code, 200)

        self.as_(self.clara)
        book = self.client.get(f"/api/books/{self.book.id}").data
        self.assertEqual(book["copies_total"], 2)
        self.assertEqual(book["available_copies"], 1)
        self.assertFalse(self.client.get(f"/api/copies/{c1.id}").data["available"])
        self.assertTrue(self.client.get(f"/api/copies/{c2.id}").data["available"])

    def test_full_cycle_restores_availability(self):
        copy = self.copy_of(self.anna)
        loan_id = self.request_loan(self.boris, copy).data["id"]
        self.assertEqual(self.act(self.anna, loan_id, "accept").data["status"], "accepted")
        r = self.act(self.anna, loan_id, "hand-over")
        self.assertEqual(r.data["status"], "handed_over")
        self.assertIsNotNone(r.data["handed_at"])
        self.assertEqual(self.act(self.anna, loan_id, "return").data["status"], "returned")

        self.as_(self.boris)
        self.assertTrue(self.client.get(f"/api/copies/{copy.id}").data["available"])
        history = self.client.get("/api/loans?role=outgoing").data["results"]
        self.assertEqual([x["status"] for x in history], ["returned"])
        self.assertEqual(self.request_loan(self.boris, copy).status_code, 201)

    def test_cannot_accept_two_borrowers_for_one_copy(self):
        copy = self.copy_of(self.anna)
        lb = self.request_loan(self.boris, copy).data["id"]
        lc = self.request_loan(self.clara, copy).data["id"]
        self.assertEqual(self.act(self.anna, lb, "accept").status_code, 200)
        self.assertEqual(Loan.objects.get(pk=lc).status, "rejected")
        r = self.act(self.anna, lc, "accept")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Loan.objects.filter(copy=copy, status__in=Loan.BUSY_STATUSES).count(), 1)

    def test_review_edit_updates_rating_without_duplicate(self):
        def put(user, score):
            self.as_(user)
            return self.client.put(f"/api/books/{self.book.id}/review", {"score": score, "text": "ок"}, format="json")

        self.assertEqual(put(self.boris, 5).status_code, 201)
        self.assertEqual(put(self.clara, 3).status_code, 201)
        self.assertEqual(self.client.get(f"/api/books/{self.book.id}").data["avg_rating"], 4.0)
        self.assertEqual(put(self.boris, 1).status_code, 200)
        self.assertEqual(Review.objects.filter(book=self.book).count(), 2)
        self.assertEqual(self.client.get(f"/api/books/{self.book.id}").data["avg_rating"], 2.0)

    def test_hidden_review_excluded_from_rating(self):
        self.as_(self.boris)
        self.client.put(f"/api/books/{self.book.id}/review", {"score": 5}, format="json")
        self.as_(self.clara)
        rid = self.client.put(f"/api/books/{self.book.id}/review", {"score": 1}, format="json").data["id"]
        self.as_(self.moder)
        self.assertEqual(self.client.post(f"/api/reviews/{rid}/hide").status_code, 200)
        data = self.client.get(f"/api/books/{self.book.id}").data
        self.assertEqual(data["avg_rating"], 5.0)
        self.assertEqual(data["reviews_count"], 1)
        self.as_(self.anna)
        self.assertEqual(len(self.client.get(f"/api/books/{self.book.id}/reviews").data["results"]), 1)
        self.as_(self.clara)
        self.assertEqual(len(self.client.get(f"/api/books/{self.book.id}/reviews").data["results"]), 2)


class PermissionTests(BaseCase):
    def test_anonymous_gets_401(self):
        self.assertEqual(self.client.get("/api/books").status_code, 401)

    def test_member_cannot_manage_catalog(self):
        self.as_(self.anna)
        r = self.client.post("/api/books", {"title": "X", "author": "Y", "genre": "Z"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_moderator_manages_catalog_and_duplicate_rejected(self):
        self.as_(self.moder)
        payload = {"title": "Хоббит", "author": "Толкин", "genre": "Фэнтези"}
        self.assertEqual(self.client.post("/api/books", payload, format="json").status_code, 201)
        dup = self.client.post("/api/books", {**payload, "title": "хоббит"}, format="json")
        self.assertEqual(dup.status_code, 400)
        self.assertIn("title", dup.data["errors"])

    def test_only_admin_assigns_roles(self):
        self.as_(self.moder)
        self.assertEqual(self.client.patch(f"/api/users/{self.anna.id}/role", {"role": "moderator"}, format="json").status_code, 403)
        self.as_(self.admin)
        r = self.client.patch(f"/api/users/{self.anna.id}/role", {"role": "moderator"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["role"], "moderator")

    def test_registration_cannot_set_role(self):
        self.client.force_authenticate(None)
        r = self.client.post(
            "/api/auth/register",
            {"username": "newbie", "password": "Str0ng-pass-77", "role": "admin"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.get(username="newbie").role, "member")

    def test_login_logout(self):
        self.client.force_authenticate(None)
        bad = self.client.post("/api/auth/login", {"username": "anna", "password": "nope"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post("/api/auth/login", {"username": "anna", "password": "pass12345"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {ok.data['token']}")
        self.assertEqual(self.client.get("/api/auth/me").data["username"], "anna")
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_loan_actions_rights(self):
        copy = self.copy_of(self.anna)
        lid = self.request_loan(self.boris, copy).data["id"]
        self.assertEqual(self.act(self.boris, lid, "accept").status_code, 403)
        self.assertEqual(self.act(self.clara, lid, "accept").status_code, 404)
        self.as_(self.clara)
        self.assertEqual(self.client.get(f"/api/loans/{lid}").status_code, 404)

    def test_only_owner_edits_copy(self):
        copy = self.copy_of(self.anna)
        self.as_(self.boris)
        self.assertEqual(self.client.patch(f"/api/copies/{copy.id}", {"pickup_place": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/copies/{copy.id}").status_code, 403)


class ValidationAndStateTests(BaseCase):
    def test_cannot_borrow_own_copy(self):
        copy = self.copy_of(self.anna)
        r = self.request_loan(self.anna, copy)
        self.assertEqual(r.status_code, 400)
        self.assertIn("copy", r.data["errors"])

    def test_return_date_must_be_future(self):
        copy = self.copy_of(self.anna)
        r = self.request_loan(self.boris, copy, days=-1)
        self.assertEqual(r.status_code, 400)
        self.assertIn("requested_return_date", r.data["errors"])

    def test_duplicate_pending_request_conflict(self):
        copy = self.copy_of(self.anna)
        self.assertEqual(self.request_loan(self.boris, copy).status_code, 201)
        self.assertEqual(self.request_loan(self.boris, copy).status_code, 409)

    def test_illegal_transitions_give_409(self):
        copy = self.copy_of(self.anna)
        lid = self.request_loan(self.boris, copy).data["id"]
        self.assertEqual(self.act(self.anna, lid, "hand-over").status_code, 409)
        self.assertEqual(self.act(self.anna, lid, "return").status_code, 409)
        self.act(self.anna, lid, "reject")
        self.assertEqual(self.act(self.anna, lid, "accept").status_code, 409)
        self.assertEqual(self.act(self.boris, lid, "cancel").status_code, 409)

    def test_cannot_request_busy_or_inactive_copy(self):
        copy = self.copy_of(self.anna)
        lid = self.request_loan(self.boris, copy).data["id"]
        self.act(self.anna, lid, "accept")
        self.assertEqual(self.request_loan(self.clara, copy).status_code, 409)
        other = self.copy_of(self.anna)
        other.is_active = False
        other.save()
        self.assertEqual(self.request_loan(self.clara, other).status_code, 409)

    def test_handed_over_copy_cannot_be_hidden_or_deleted(self):
        copy = self.copy_of(self.anna)
        lid = self.request_loan(self.boris, copy).data["id"]
        self.act(self.anna, lid, "accept")
        self.act(self.anna, lid, "hand-over")
        self.as_(self.anna)
        self.assertEqual(self.client.patch(f"/api/copies/{copy.id}", {"is_active": False}, format="json").status_code, 409)
        self.assertEqual(self.client.delete(f"/api/copies/{copy.id}").status_code, 409)
        self.act(self.anna, lid, "return")
        self.as_(self.anna)
        self.assertEqual(self.client.patch(f"/api/copies/{copy.id}", {"is_active": False}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/copies/{copy.id}").status_code, 409)

    def test_deactivation_rejects_pending(self):
        copy = self.copy_of(self.anna)
        lid = self.request_loan(self.boris, copy).data["id"]
        self.as_(self.anna)
        self.client.patch(f"/api/copies/{copy.id}", {"is_active": False}, format="json")
        self.assertEqual(Loan.objects.get(pk=lid).status, "rejected")

    def test_overdue_computed(self):
        copy = self.copy_of(self.anna)
        lid = self.request_loan(self.boris, copy).data["id"]
        self.act(self.anna, lid, "accept")
        self.act(self.anna, lid, "hand-over")
        Loan.objects.filter(pk=lid).update(requested_return_date=timezone.localdate() - timedelta(days=3))
        self.as_(self.boris)
        row = self.client.get("/api/loans?overdue=1").data["results"][0]
        self.assertTrue(row["is_overdue"])
        self.assertEqual(row["days_overdue"], 3)

    def test_review_score_validation(self):
        self.as_(self.boris)
        r = self.client.put(f"/api/books/{self.book.id}/review", {"score": 6}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("score", r.data["errors"])

    def test_missing_objects_404(self):
        self.as_(self.boris)
        self.assertEqual(self.client.get("/api/books/9999").status_code, 404)
        self.assertEqual(self.client.post("/api/copies/9999/loans", {"requested_return_date": self.due()}, format="json").status_code, 404)
        self.assertEqual(self.client.put("/api/reading/9999", {"status": "want"}, format="json").status_code, 404)


class ReadingAndSearchTests(BaseCase):
    def test_reading_flow_and_monthly_stats(self):
        self.as_(self.anna)
        r = self.client.put(f"/api/reading/{self.book.id}", {"status": "read"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["finished_at"], timezone.localdate().isoformat())
        again = self.client.put(f"/api/reading/{self.book.id}", {"status": "reading"}, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertIsNone(again.data["finished_at"])
        self.client.put(f"/api/reading/{self.book.id}", {"status": "read"}, format="json")
        stats = self.client.get("/api/reading/stats").data
        self.assertEqual(stats["read_this_month"], 1)
        self.assertEqual(stats["by_status"]["read"], 1)
        self.assertEqual(self.client.get(f"/api/books/{self.book.id}").data["read_this_month"], 1)

    def test_finished_at_validation(self):
        self.as_(self.anna)
        future = (timezone.localdate() + timedelta(days=2)).isoformat()
        r = self.client.put(f"/api/reading/{self.book.id}", {"status": "read", "finished_at": future}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.put(f"/api/reading/{self.book.id}", {"status": "want", "finished_at": timezone.localdate().isoformat()}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cyrillic_search_ignores_case(self):
        self.as_(self.anna)
        for q in ("дюна", "ДЮНА", "герберт", "ГЕРБЕРТ"):
            res = self.client.get("/api/books", {"search": q}).data
            self.assertEqual(res["count"], 1, q)
        self.assertEqual(self.client.get("/api/books", {"search": "нет такой"}).data["count"], 0)

    def test_catalog_filters_pagination_and_available(self):
        for i in range(12):
            Book.objects.create(title=f"Книга {i:02d}", author="Автор", genre="Проза")
        self.copy_of(self.boris)
        self.as_(self.anna)
        page1 = self.client.get("/api/books").data
        self.assertEqual(page1["count"], 13)
        self.assertEqual(len(page1["results"]), 10)
        self.assertEqual(self.client.get("/api/books", {"genre": "Проза"}).data["count"], 12)
        self.assertEqual(self.client.get("/api/books", {"available": "1"}).data["count"], 1)
        self.assertEqual(len(self.client.get("/api/genres").data), 2)
