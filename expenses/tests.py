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

