from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        MEMBER = "member", "Участник"
        MODERATOR = "moderator", "Модератор"
        ADMIN = "admin", "Администратор"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER, db_index=True)
    bio = models.TextField("О себе", blank=True)

    def save(self, *args, **kwargs):
        if self.is_superuser and self.role != self.Role.ADMIN:
            self.role = self.Role.ADMIN
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"role"}
        super().save(*args, **kwargs)

    @property
    def is_moderator(self) -> bool:
        return self.role in (self.Role.MODERATOR, self.Role.ADMIN)

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    def __str__(self):
        return self.username
