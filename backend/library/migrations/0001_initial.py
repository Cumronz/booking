import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(db_index=True, max_length=255, verbose_name='Название')),
                ('author', models.CharField(db_index=True, max_length=255, verbose_name='Автор')),
                ('genre', models.CharField(db_index=True, max_length=100, verbose_name='Жанр')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('cover', models.ImageField(blank=True, null=True, upload_to='covers/', verbose_name='Обложка')),
                ('search_key', models.CharField(editable=False, max_length=600, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['title', 'id'],
            },
        ),
        migrations.CreateModel(
            name='Copy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('condition', models.CharField(choices=[('new', 'Новая'), ('good', 'Хорошее'), ('fair', 'Удовлетворительное'), ('worn', 'Потрёпанная')], default='good', max_length=10)),
                ('pickup_place', models.CharField(max_length=255, verbose_name='Место передачи')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='На полке')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='copies', to='library.book')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='copies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='Loan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requested_return_date', models.DateField(verbose_name='Желаемая дата возврата')),
                ('status', models.CharField(choices=[('pending', 'Ожидает'), ('accepted', 'Принята'), ('rejected', 'Отклонена'), ('cancelled', 'Отменена'), ('handed_over', 'Передана'), ('returned', 'Возвращена')], default='pending', max_length=12)),
                ('message', models.CharField(blank=True, max_length=500, verbose_name='Сообщение владельцу')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('handed_at', models.DateTimeField(blank=True, null=True)),
                ('returned_at', models.DateTimeField(blank=True, null=True)),
                ('borrower', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='borrowed_loans', to=settings.AUTH_USER_MODEL)),
                ('copy', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='loans', to='library.copy')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ReadingEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('want', 'Хочу прочитать'), ('reading', 'Читаю'), ('read', 'Прочитал')], max_length=10)),
                ('finished_at', models.DateField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reading_entries', to='library.book')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reading_entries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('text', models.TextField(blank=True)),
                ('is_hidden', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reviews', to='library.book')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='copy',
            index=models.Index(fields=['book', 'is_active'], name='copy_book_active_idx'),
        ),
        migrations.AddIndex(
            model_name='copy',
            index=models.Index(fields=['owner', 'is_active'], name='copy_owner_active_idx'),
        ),
        migrations.AddIndex(
            model_name='loan',
            index=models.Index(fields=['status', 'requested_return_date'], name='loan_status_due_idx'),
        ),
        migrations.AddIndex(
            model_name='loan',
            index=models.Index(fields=['borrower', 'status'], name='loan_borrower_status_idx'),
        ),
        migrations.AddIndex(
            model_name='loan',
            index=models.Index(fields=['copy', 'status'], name='loan_copy_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='loan',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['accepted', 'handed_over'])), fields=('copy',), name='uniq_busy_loan_per_copy'),
        ),
        migrations.AddConstraint(
            model_name='loan',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'pending')), fields=('copy', 'borrower'), name='uniq_pending_loan_per_borrower'),
        ),
        migrations.AddIndex(
            model_name='readingentry',
            index=models.Index(fields=['status', 'finished_at'], name='reading_status_fin_idx'),
        ),
        migrations.AddConstraint(
            model_name='readingentry',
            constraint=models.UniqueConstraint(fields=('user', 'book'), name='uniq_reading_user_book'),
        ),
        migrations.AddConstraint(
            model_name='readingentry',
            constraint=models.CheckConstraint(condition=models.Q(('status', 'read'), ('finished_at__isnull', True), _connector='OR'), name='reading_finished_only_if_read'),
        ),
        migrations.AddIndex(
            model_name='review',
            index=models.Index(fields=['book', 'is_hidden'], name='review_book_hidden_idx'),
        ),
        migrations.AddConstraint(
            model_name='review',
            constraint=models.UniqueConstraint(fields=('user', 'book'), name='uniq_review_user_book'),
        ),
        migrations.AddConstraint(
            model_name='review',
            constraint=models.CheckConstraint(condition=models.Q(('score__gte', 1), ('score__lte', 5)), name='review_score_1_5'),
        ),
    ]
