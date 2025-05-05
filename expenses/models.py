from django.db import models

# Create your models here.
from django.contrib.auth.models import User

from decimal import Decimal



class Group(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_groups")
    members = models.ManyToManyField(User, related_name="group_memberships", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Expense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="expenses")
    description = models.CharField(max_length=255, null=False, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    paid_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="paid_expenses")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"'{self.description}' in group '{self.group.name}' - {self.amount} RON paid by {self.paid_by.username}"
    
class ExpenseSplit(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="splits")
    owed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owed_splits")
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    # settled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.owed_by.username} owes {self.amount} RON for '{self.expense.description}'"
