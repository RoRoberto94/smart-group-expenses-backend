from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from .models import Group, Expense, ExpenseSplit
from decimal import Decimal
from rest_framework.exceptions import ValidationError, PermissionDenied

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')

class GroupSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ('id', 'name', 'owner', 'members', 'created_at')

    def create(self, validated_data):
        user = self.context['request'].user
        group = Group.objects.create(owner=user, **validated_data)
        group.members.add(user)

        return group

class ExpenseSplitSerializer(serializers.ModelSerializer):
    owed_by = UserSerializer(read_only=True)

    class Meta:
        model = ExpenseSplit

        fields = ('id', 'owed_by', 'amount')

class ExpenseSerializer(serializers.ModelSerializer):
    paid_by = UserSerializer(read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)
    

    class Meta:
        model = Expense

        fields = ('id', 'group', 'description', 'amount', 'paid_by', 'splits', 'created_at')
        read_only_fields = ('id', 'paid_by', 'splits', 'created_at', 'group')
    
    def create(self, validated_data):
        current_user = self.context['request'].user

        if 'group_instance' not in self.context:
            raise ValidationError({'detail': "Group instance (context) is required for creating an expense."})
    
        group_instance = self.context['group_instance']

        if not group_instance.members.filter(id=current_user.id).exists():
            raise PermissionDenied(_("You are not a member of this group and cannot add expenses to it"))
        
        expense = Expense.objects.create(paid_by=current_user,
                                         group=group_instance,
                                         description=validated_data['description'],
                                         amount=Decimal(validated_data['amount'])
                                         )
        members = group_instance.members.all()
        number_of_members = members.count()

        if number_of_members > 0:
            split_amount_raw = expense.amount / Decimal(number_of_members)
            split_amount = split_amount_raw.quantize(Decimal('0.01'))
            splits_to_create = []
            for member in members:
                splits_to_create.append(
                    ExpenseSplit(expense=expense, owed_by=member, amount=split_amount))
                
            ExpenseSplit.objects.bulk_create(splits_to_create)

        return expense

    def update(self, instance, validated_data):
        old_amount = instance.amount
        instance.description = validated_data.get('description', instance.description)
        new_amount_str = validated_data.get('amount', str(instance.amount))
        instance.amount = Decimal(new_amount_str)
        instance.save(update_fields=['description', 'amount'])

        if old_amount != instance.amount:
            instance.splits.all().delete()
            group_of_expense = instance.group
            members = group_of_expense.members.all()
            number_of_members = members.count()

            if number_of_members > 0:
                split_amount_raw = instance.amount / Decimal(number_of_members)
                split_amount = split_amount_raw.quantize(Decimal('0.01'))

                splits_to_create = []
                for member in members:
                    splits_to_create.append(ExpenseSplit(expense=instance, owed_by=member, amount=split_amount))
                ExpenseSplit.objects.bulk_create(splits_to_create)

        return instance

class OptimizedSettlementSerializer(serializers.Serializer):
    from_user_username = serializers.CharField(source='from_user.username')
    to_user_username = serializers.CharField(source='to_user.username')
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

class SettlementTransactionSerializer(serializers.Serializer):
    from_user = UserSerializer(source='from_user_obj')
    to_user = UserSerializer(source='to_user_obj')
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )

    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model=User
        fields = ('username', 'email', 'password', 'password2', 'first_name', 'last_name')
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": _("Password fields didn't match.")})
        return attrs
    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )

        user.set_password(validated_data['password'])
        user.save()
        return user
    
class ManageGroupMemberSerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)

    def validate_username(self, value):
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User with this username does not exist."))
        return value