from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth.models import User
from .serializers import UserSerializer, RegisterSerializer
from .models import Group
from .serializers import GroupSerializer
from .models import Expense, ExpenseSplit
from .serializers import ExpenseSerializer
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import OptimizedSettlementSerializer

def calculate_optimized_settlements(group_id):
    try:
        group = Group.objects.get(pk=group_id)
    except Group.DoesNotExist:
        return[]
    
    members = group.members.all()
    if not members.exists():
        return []
    
    balances = {}

    for member in members:
        balances[member.id] = Decimal('0.00')

    group_expenses = Expense.objects.filter(group=group)
    for expense in group_expenses:
        if expense.paid_by_id in balances:
            balances[expense.paid_by_id] += expense.amount
        else:
            balances[expense.paid_by_id] = expense.amount

        expense_splits = ExpenseSplit.objects.filter(expense=expense)
        for split in expense_splits:
            if split.owed_by_id in balances:
                balances[split.owed_by_id] -= split.amount
            else:
                balances[split.owed_by_id] = -split.amount

    creditors = {}
    debtors = {}

    for user_id, balance in balances.items():
        if balance > Decimal('0.00'):
            creditors[user_id]=balance
        elif balance < Decimal('0.00'):
            debtors[user_id] = -balance

    settlements = []

    sorted_debtors = sorted(debtors.items(), key=lambda item: item[1], reverse=True)
    sorted_creditors = sorted(creditors.items(), key=lambda item: item[1], reverse=True)

    debtor_idx = 0
    creditor_idx = 0

    while debtor_idx < len(sorted_debtors) and creditor_idx < len(sorted_creditors):
        debtor_id, debtor_amount = sorted_debtors[debtor_idx]
        creditor_id, creditor_amount = sorted_creditors[creditor_idx]

        amount_to_transfer = min(debtors[debtor_id], creditors[creditor_id])

        if amount_to_transfer > Decimal('0.001'):
            settlements.append({
                'from_user_id': debtor_id,
                'to_user_id': creditor_id,
                'amount': amount_to_transfer.quantize(Decimal('0.01'))
            })

            debtors[debtor_id] -= amount_to_transfer
            creditors[creditor_id] -= amount_to_transfer

        if debtors[debtor_id] < Decimal('0.001'):
            debtor_idx += 1 
        
        if creditors[creditor_id] < Decimal('0.001'):
            creditor_idx += 1

    return settlements

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    pass

class CustomTokenRefreshView(TokenRefreshView):
    pass

class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

class GroupListCreateView(generics.ListCreateAPIView):
    serializer_class = GroupSerializer

    def get_queryset(self):
        user = self.request.user
        
        return user.group_memberships.all().order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save()

class GroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = GroupSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        return user.group_memberships.all()
    
    def perform_update(self, serializer):
        group=self.get_object()
        if group.owner != self.request.user:
            raise PermissionDenied("You do not have permission to edit this group as you are not the owner.")
        serializer.save()
    
    def perform_destroy(self, instance):
        if instance.owner != self.request.user:
            raise PermissionDenied("You do not have permission to delete this group as you are not the owner.")
        instance.delete()

class ExpenseListCreateView(generics.ListCreateAPIView):
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        group_pk = self.kwargs.get('group_pk')
        group = get_object_or_404(Group, pk=group_pk)
        user = self.request.user
        if not group.members.filter(id=user.id).exists():
            raise PermissionDenied(_("You are not a member of this group and cannot view its expenses."))
        return Expense.objects.filter(group=group).order_by('-created_at')
    
    def get_serializer_context(self):
        context=super().get_serializer_context()
        group_pk = self.kwargs.get('group_pk')
        group = get_object_or_404(Group, pk=group_pk)
        context['group_instance'] = group
        return context

    def perform_create(self, serializer):
        group_pk = self.kwargs.get('group_pk')
        group = get_object_or_404(Group, pk=group_pk)
        user = self.request.user

        if not group.members.filter(id=user.id).exists():
            raise PermissionDenied(_("You are not a member of this group and cannot add expenses to it."))
        serializer.save()

class SettleUpView(APIView):
    """
    View for calculating and returning the optimized plan for payments for a specific group!
    It only accepts GET requests!
    """
    def get(self, request, group_pk=None):
        group = get_object_or_404(Group, pk=group_pk)
        user = request.user

        if not group.members.filter(id=user.id).exists():
            raise PermissionDenied(_("You are not a member of this group and cannot view its settlement plan."))
        
        raw_settlements = calculate_optimized_settlements(group_pk)
        enriched_settlements = []
        user_ids_involved = set()
        for settlement in raw_settlements:
            user_ids_involved.add(settlement['from_user_id'])
            user_ids_involved.add(settlement['to_user_id'])
        
        users_map = {user_obj.id: user_obj for user_obj in User.objects.filter(id__in=list(user_ids_involved))}

        for rs in raw_settlements:
            from_user_obj = users_map.get(rs['from_user_id'])
            to_user_obj = users_map.get(rs['to_user_id'])
            if from_user_obj and to_user_obj:
                enriched_settlements.append({
                    'from_user': from_user_obj,
                    'to_user': to_user_obj,
                    'amount': rs['amount']
                })

        serializer = OptimizedSettlementSerializer(enriched_settlements, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    