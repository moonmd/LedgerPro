from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from ledgerpro.backend.api.models import User, Organization, Role, Membership


class UserOrgRoleAPITests(APITestCase):
    def setUp(self):
        # User for registration/login tests
        self.register_url = reverse('user-register')
        self.login_url = reverse('user-login')
        self.me_url = reverse('user-detail')

        # Data for creating users
        self.user_data1 = {'email': 'testuser1@example.com', 'password': 'password123', 'first_name': 'Test1', 'last_name': 'User1'}
        self.user_data2 = {'email': 'testuser2@example.com', 'password': 'password123', 'first_name': 'Test2', 'last_name': 'User2'}

        # Admin user for role/permission tests
        self.admin_user = User.objects.create_superuser(email='admin@example.com', password='adminpassword')
        self.organization = Organization.objects.create(name='Main Org')
        # Note: create_superuser does not automatically create a Role or Membership.
        # For some tests requiring an admin role to be associated with an org, this might need adjustment
        # or ensure that the RoleListView/DetailView permissions are based on is_staff/is_superuser rather than specific roles.
        # The current RoleListView uses IsAdminUser, which typically checks is_staff.

    def test_user_registration(self):
        response = self.client.post(self.register_url, self.user_data1, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue('access' in response.data)
        self.assertTrue('refresh' in response.data)
        # Count will be 2: admin_user + new user
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(User.objects.get(email=self.user_data1['email']).first_name, 'Test1')

    def test_user_registration_with_organization(self):
        user_data_with_org = {**self.user_data2, 'organization_name': 'NewCo'}
        response = self.client.post(self.register_url, user_data_with_org, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = User.objects.get(email=self.user_data2['email'])
        self.assertTrue(Organization.objects.filter(name='NewCo').exists())
        organization = Organization.objects.get(name='NewCo')
        # The UserRegistrationSerializer creates a default 'Admin' role.
        admin_role = Role.objects.get(name='Admin')
        self.assertTrue(Membership.objects.filter(user=user, organization=organization, role=admin_role).exists())

    def test_user_login_and_me_endpoint(self):
        # Register user first
        self.client.post(self.register_url, self.user_data1, format='json')

        # Login
        login_data = {'email': self.user_data1['email'], 'password': self.user_data1['password']}
        response_login = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response_login.status_code, status.HTTP_200_OK, response_login.data)
        access_token = response_login.data['access']

        # Access /me endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response_me = self.client.get(self.me_url)
        self.assertEqual(response_me.status_code, status.HTTP_200_OK, response_me.data)
        self.assertEqual(response_me.data['email'], self.user_data1['email'])

    def test_duplicate_email_registration(self):
        self.client.post(self.register_url, self.user_data1, format='json')  # First registration
        response_duplicate = self.client.post(self.register_url, self.user_data1, format='json')  # Try again
        self.assertEqual(response_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response_duplicate.data.get('errors', response_duplicate.data))  # Check for email error field; structure may vary

    def test_role_management_as_admin(self):
        self.client.login(email='admin@example.com', password='adminpassword')
        roles_url = reverse('role-list')

        # Create a role
        role_data = {'name': 'Accountant', 'description': 'Manages financial records'}
        response_create_role = self.client.post(roles_url, role_data, format='json')
        self.assertEqual(response_create_role.status_code, status.HTTP_201_CREATED, response_create_role.data)
        self.assertTrue(Role.objects.filter(name='Accountant').exists())

        # List roles
        response_list_roles = self.client.get(roles_url)
        self.assertEqual(response_list_roles.status_code, status.HTTP_200_OK)
        role_names_in_response = [r['name'] for r in response_list_roles.data]
        self.assertIn('Accountant', role_names_in_response)
        # Default "Admin" role is created by UserRegistrationSerializer if an org is made.
        # "GlobalAdmin" was not created in setUp for all tests, only for this admin user.
        # It's better to check for roles known to be there or created in this test.
        # self.assertIn('GlobalAdmin', role_names_in_response)  # This might not exist depending on other tests or setup

    def test_role_management_as_non_admin(self):
        # Register and login as a normal user
        self.client.post(self.register_url, self.user_data1, format='json')
        login_resp = self.client.post(self.login_url, {'email': self.user_data1['email'], 'password': self.user_data1['password']})
        access_token = login_resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        roles_url = reverse('role-list')
        role_data = {'name': 'UnauthorizedRole', 'description': 'Should not be created'}
        response_create_role = self.client.post(roles_url, role_data, format='json')
        self.assertEqual(response_create_role.status_code, status.HTTP_403_FORBIDDEN)
