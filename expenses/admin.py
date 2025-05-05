from django.contrib import admin

# Register your models here.
from .models import Group, Expense, ExpenseSplit

admin.site.register(Group)
admin.site.register(Expense)
admin.site.register(ExpenseSplit)

