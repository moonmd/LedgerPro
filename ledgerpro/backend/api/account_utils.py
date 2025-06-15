from .models import Account, Organization  # Assuming models are in the same app level
import logging
# Not strictly used in this snippet but good for financial utilities

logger = logging.getLogger(__name__)


def get_or_create_default_account(
    organization: Organization,
    account_type: str,
    account_name_substring: str,
    default_name: str,
    default_description_suffix: str = 'account'
):
    '''
    Helper function to find an account by a name substring or create a default one.
    If multiple accounts match the substring, logs a warning and returns the first one found by exact default_name, then by substring.
    '''
    try:
        # First, try to find by an exact match of the default_name, as it's more specific
        account = Account.objects.get(organization=organization, type=account_type, name=default_name, is_active=True)
    except Account.DoesNotExist:
        try:
            # If exact default_name not found, try by substring
            account = Account.objects.get(organization=organization, type=account_type, name__icontains=account_name_substring, is_active=True)
            logger.info(f'Found account "{account.name}" for {account_type} using substring "{account_name_substring}" for default "{default_name}" in org {organization.name}.')
        except Account.DoesNotExist:
            logger.info(f'Default account with name "{default_name}" or substring "{account_name_substring}" not found for {account_type} in org {organization.name}. Creating "{default_name}".')
            account = Account.objects.create(
                organization=organization,
                name=default_name,
                type=account_type,
                description=f'Default {default_description_suffix} for {organization.name}. Auto-created.'
            )
        except Account.MultipleObjectsReturned:
            logger.warning(
                f'Multiple accounts found for org {organization.name} with type {account_type} and substring "{account_name_substring}" '
                f'when searching for default "{default_name}". Using the first one found by substring.'
            )
            account = Account.objects.filter(organization=organization, type=account_type, name__icontains=account_name_substring, is_active=True).first()
    except Account.MultipleObjectsReturned:
        logger.warning(
            f'Multiple accounts found for org {organization.name} with exact name "{default_name}" for type {account_type}. '
            f'Using the first one found. Please ensure unique default account names.'
        )
        account = Account.objects.filter(organization=organization, type=account_type, name=default_name, is_active=True).first()
    return account
