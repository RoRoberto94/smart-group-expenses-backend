from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Group, Expense, ExpenseSplit
from .views import calculate_optimized_settlements
from rest_framework.test import APIClient
from rest_framework import status

class SettlementCalculationTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='usera', password='password123')
        self.user_b = User.objects.create_user(username='userb', password='password123')
        self.user_c = User.objects.create_user(username='userc', password='password123')

        self.test_group = Group.objects.create(name='Test Settle Group', owner=self.user_a)

        self.test_group.members.add(self.user_a, self.user_b, self.user_c)

    def test_no_expenses_no_settlements(self):
        settlements = calculate_optimized_settlements(self.test_group.id)
        self.assertEqual(settlements, [])

    def test_simple_settlement_one_payer(self):
        expense1 = Expense.objects.create(
            group=self.test_group,
            description="Cheltuiala 1",
            amount=Decimal('30.00'),
            paid_by=self.user_a
        )

        ExpenseSplit.objects.create(expense=expense1, owed_by=self.user_a, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=expense1, owed_by=self.user_b, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=expense1, owed_by=self.user_c, amount=Decimal('10.00'))

        settlements = calculate_optimized_settlements(self.test_group.id)

        self.assertEqual(len(settlements), 2)

        expected_transactions_set = {
            (self.user_b.id, self.user_a.id, "10.00"),
            (self.user_c.id, self.user_a.id, "10.00"),
        }

        actual_transactions_set = set()
        for s in settlements:
            actual_transactions_set.add(
                (s['from_user_id'], s['to_user_id'], str(s['amount']))
            )
        
        self.assertEqual(actual_transactions_set, expected_transactions_set)

    def test_complex_settlement_multiple_payers(self):
        exp1 = Expense.objects.create(group=self.test_group, description='Exp1', amount=Decimal('30.00'), paid_by=self.user_a)
        ExpenseSplit.objects.create(expense=exp1, owed_by=self.user_a, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=exp1, owed_by=self.user_b, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=exp1, owed_by=self.user_c, amount=Decimal('10.00'))

        exp2 = Expense.objects.create(group=self.test_group, description='Exp2', amount=Decimal('60.00'), paid_by=self.user_b)
        ExpenseSplit.objects.create(expense=exp2, owed_by=self.user_a, amount=Decimal('20.00'))
        ExpenseSplit.objects.create(expense=exp2, owed_by=self.user_b, amount=Decimal('20.00'))
        ExpenseSplit.objects.create(expense=exp2, owed_by=self.user_c, amount=Decimal('20.00'))

        settlements = calculate_optimized_settlements(self.test_group.id)

        print(f"Settlements in complex test: {settlements}")

        self.assertEqual(len(settlements), 1)

        if settlements:
            first_settlement = settlements[0]
            self.assertEqual(first_settlement['from_user_id'], self.user_c.id)
            self.assertEqual(first_settlement['to_user_id'], self.user_b.id)
            self.assertEqual(first_settlement['amount'], Decimal('30.00'))
        else:
            self.fail("No settlements generated when one was expected.")


class ExpenseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.user1 = User.objects.create_user(username='apiuser1', password='password123', email='api1@test.com')
        self.user2 = User.objects.create_user(username='apiuser2', password='password123', email='api2@test.com')

        response_login = self.client.post('/api/auth/login/', {'username': 'apiuser1', 'password': 'password123'}, format='json')
        self.assertEqual(response_login.status_code, status.HTTP_200_OK)
        self.token_user1 = response_login.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_user1}')

        self.group_user1 = Group.objects.create(name="User1's Group", owner=self.user1)
        self.group_user1.members.add(self.user1)

    def test_create_group_authenticated(self):
        payload = {'name': 'New Test Group via API'}
        response = self.client.post('/api/groups/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Group.objects.count(), 2)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertEqual(response.data['owner']['username'], self.user1.username)
        created_group_id = response.data['id']
        created_group = Group.objects.get(pk=created_group_id)

        self.assertTrue(created_group.members.filter(id=self.user1.id).exists())

    def test_list_user_groups(self):
        Group.objects.create(name="User1's Second Group", owner=self.user1).members.add(self.user1)

        response = self.client.get('/api/groups/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        self.assertEqual(response.data[0]['name'], "User1's Second Group")
        self.assertEqual(response.data[1]['name'], "User1's Group")

    def test_create_expense_in_group(self):
        group_id = self.group_user1.id
        payload = {'description': 'API Expense', 'amount': '50.00'}

        url = f'/api/groups/{group_id}/expenses/'
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(response.data['description'], payload['description'])
        self.assertEqual(Decimal(response.data['amount']), Decimal(payload['amount']))
        self.assertEqual(response.data['paid_by']['username'], self.user1.username)

        self.assertEqual(len(response.data['splits']), 1)
        self.assertEqual(response.data['splits'][0]['owed_by']['username'], self.user1.username)
        self.assertEqual(Decimal(response.data['splits'][0]['amount']), Decimal(payload['amount']))

    def test_get_settle_up_for_group(self):
        self.group_user1.members.add(self.user2)
        expense_payload = {'description': 'Settle Expense', 'amount': '100.00'}
        expense_url = f'/api/groups/{self.group_user1.id}/expenses/'
        response_expense = self.client.post(expense_url, expense_payload, format='json')
        self.assertEqual(response_expense.status_code, status.HTTP_201_CREATED)

        settle_url = f'/api/groups/{self.group_user1.id}/settle/'
        response_settle = self.client.get(settle_url, format='json')

        self.assertEqual(response_settle.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_settle.data), 1)

        settlement_data = response_settle.data[0]

        self.assertEqual(settlement_data['from_user_username'], self.user2.username)
        self.assertEqual(settlement_data['to_user_username'], self.user1.username)
        self.assertEqual(Decimal(settlement_data['amount']), Decimal('50.00'))
    
    def test_update_expense_as_payer(self):
        expense = Expense.objects.create(
        group=self.group_user1,
        description='Initial Dinner',
        amount=Decimal('100.00'),
        paid_by=self.user1
        )

        ExpenseSplit.objects.create(expense=expense, owed_by=self.user1, amount=Decimal('100.00'))

        self.group_user1.members.add(self.user2)

        url = f'/api/groups/{self.group_user1.pk}/expenses/{expense.pk}/'
        payload = {'description': 'Updated Dinner', 'amount': '120.00'}
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], payload['description'])
        self.assertEqual(Decimal(response.data['amount']), Decimal(payload['amount']))

        expense.refresh_from_db()
    
        self.assertEqual(expense.splits.count(), 2)
        for split in expense.splits.all():
            self.assertEqual(split.amount, Decimal('60.00'))

    def test_update_expense_as_non_payer_fails(self):
        expense = Expense.objects.create(group=self.group_user1, description='Test Expense', amount=Decimal('50.00'), paid_by=self.user1)
        self.group_user1.members.add(self.user2)

        response_login = self.client.post('/api/auth/login/', {'username': 'apiuser2', 'password': 'password123'}, format='json')
        token_user2 = response_login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_user2}')

        url = f'/api/groups/{self.group_user1.pk}/expenses/{expense.pk}/'
        payload = {'description': 'Hacked!'}
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_expense_as_payer(self):
        expense = Expense.objects.create(group=self.group_user1, description='To be deleted', amount=Decimal('20.00'), paid_by=self.user1)
        expense_id_to_delete = expense.pk

        url = f'/api/groups/{self.group_user1.pk}/expenses/{expense_id_to_delete}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Expense.objects.filter(pk=expense_id_to_delete).exists())

    def test_delete_expense_as_non_payer_fails(self):
        expense = Expense.objects.create(group=self.group_user1, description='Protected Expense', amount=Decimal('30.00'), paid_by=self.user1)
        self.group_user1.members.add(self.user2)

        response_login = self.client.post('/api/auth/login/', {'username': 'apiuser2', 'password': 'password123'}, format='json')
        token_user2 = response_login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_user2}')

        url = f'/api/groups/{self.group_user1.pk}/expenses/{expense.pk}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_group_name_as_owner(self):
        url = f'/api/groups/{self.group_user1.pk}/'
        payload = {'name': 'Updated Group Name'}
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], payload['name'])
        self.group_user1.refresh_from_db()
        self.assertEqual(self.group_user1.name, payload['name'])

    def test_update_group_name_as_non_owner_fails(self):
        self.group_user1.members.add(self.user2)

        response_login = self.client.post('/api/auth/login/', {'username': 'apiuser2', 'password': 'password123'}, format='json')
        token_user2 = response_login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_user2}')

        url = f'/api/groups/{self.group_user1.pk}/'
        payload = {'name': 'Attempted Update'}
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_group_as_owner(self):
        Expense.objects.create(group=self.group_user1, description='Test', amount=Decimal('10.00'), paid_by=self.user1)
        self.assertEqual(Expense.objects.count(), 1)

        group_id_to_delete = self.group_user1.pk
        url = f'/api/groups/{group_id_to_delete}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Group.objects.filter(pk=group_id_to_delete).exists())
        self.assertEqual(Expense.objects.count(), 0)

    def test_add_member_as_owner(self):
        url = f'/api/groups/{self.group_user1.pk}/members/'
        payload = {'username': self.user2.username}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'User added successfully.')

        self.assertTrue(self.group_user1.members.filter(pk=self.user2.pk).exists())

    def test_remove_member_as_owner(self):
        self.group_user1.members.add(self.user2)

        self.assertTrue(self.group_user1.members.filter(pk=self.user2.pk).exists())

        url = f'/api/groups/{self.group_user1.pk}/members/'
        payload = {'username': self.user2.username}
        response = self.client.delete(url, data=payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'User removed successfully.')

        self.assertFalse(self.group_user1.members.filter(pk=self.user2.pk).exists())

    def test_remove_owner_from_group_fails(self):
        url = f'/api/groups/{self.group_user1.pk}/members/'
        payload = {'username': self.user1.username}
        response = self.client.delete(url, data=payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'The group owner cannot be removed.')

    def test_update_user_profile(self):
        url = '/api/auth/user/'
        payload = {'first_name': 'ApiUser', 'last_name': 'One'}
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], payload['first_name'])
        self.assertEqual(response.data['last_name'], payload['last_name'])

        self.user1.refresh_from_db()
        self.assertEqual(self.user1.first_name, payload['first_name'])
        self.assertEqual(self.user1.last_name, payload['last_name'])