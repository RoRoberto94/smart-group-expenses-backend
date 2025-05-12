from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth.models import User
from .serializers import UserSerializer, RegisterSerializer
from .models import Group
from .serializers import GroupSerializer
from .models import Expense
from .serializers import ExpenseSerializer
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

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
