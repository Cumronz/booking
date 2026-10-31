from django.contrib import admin

from .models import Book, Copy, Loan, ReadingEntry, Review

admin.site.register(Book)
admin.site.register(Copy)
admin.site.register(Loan)
admin.site.register(ReadingEntry)
admin.site.register(Review)
