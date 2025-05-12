from django.urls import path
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    UserDetailView,
    GroupListCreateView,
    GroupDetailView,
    ExpenseListCreateView
)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth_register'),

    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),

    path('auth/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),

    path('auth/user/', UserDetailView.as_view(), name='auth_user_detail'),

    path('groups/', GroupListCreateView.as_view(), name='group-list-create'),

    path('groups/<int:pk>/', GroupDetailView.as_view(), name='group-detail'),

    path('groups/<int:group_pk>/expenses/', ExpenseListCreateView.as_view(), name='group-expense-list-create'),
]

