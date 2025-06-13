from plaid import ApiException as PlaidApiException  # Corrected import
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.country_code import CountryCode as PlaidCountryCode
from plaid.model.products import Products as PlaidProducts
from django.conf import settings
from django.utils import timezone  # Added for timezone.now()
import logging
from .models import PlaidItem, StagedBankTransaction, Organization

logger = logging.getLogger(__name__)


def get_plaid_client():
    # Map PLAID_ENV to Plaid API environments
    # Make sure PLAID_ENV in settings matches one of 'sandbox', 'development', 'production'
    env_map = {
        'sandbox': plaid_api.Host.sandbox,
        'development': plaid_api.Host.development,
        # 'production': plaid_api.Host.production, # Uncomment when ready for production
    }
    # Default to sandbox if PLAID_ENV is not set or invalid for safety
    plaid_host = env_map.get(settings.PLAID_ENV, plaid_api.Host.sandbox)

    # Determine secret based on environment
    if settings.PLAID_ENV == 'development':
        plaid_secret = settings.PLAID_SECRET_DEVELOPMENT
    # elif settings.PLAID_ENV == 'production':
        # plaid_secret = settings.PLAID_SECRET_PRODUCTION # Uncomment for production
    else:  # Default to sandbox
        plaid_secret = settings.PLAID_SECRET_SANDBOX

    if not settings.PLAID_CLIENT_ID or not plaid_secret:
        logger.error("Plaid Client ID or Secret is not configured.")
        raise ValueError("Plaid Client ID or Secret is not configured.")

    configuration = plaid_api.Configuration(
        host=plaid_host,
        api_key={
            'clientId': settings.PLAID_CLIENT_ID,
            'secret': plaid_secret,
        }
    )
    api_client = plaid_api.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(user_id_str: str, organization: Organization):
    '''Generates a link_token for the Plaid Link frontend component.'''
    try:
        client = get_plaid_client()
        request_products = [PlaidProducts(p.strip()) for p in settings.PLAID_PRODUCTS if p.strip()]
        request_country_codes = [PlaidCountryCode(cc.strip()) for cc in settings.PLAID_COUNTRY_CODES if cc.strip()]

        if not request_products:
            logger.error(f"PLAID_PRODUCTS not configured for org {organization.name}")
            return None
        if not request_country_codes:
            logger.error(f"PLAID_COUNTRY_CODES not configured for org {organization.name}")
            return None

        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=user_id_str),
            client_name='LedgerPro',  # Consider making this configurable
            products=request_products,
            country_codes=request_country_codes,
            language='en',  # Consider making this configurable
            redirect_uri=settings.PLAID_REDIRECT_URI if settings.PLAID_REDIRECT_URI else None,
        )
        response = client.link_token_create(request)
        logger.info(f'Plaid link token created for user {user_id_str} in org {organization.name}')
        return response['link_token']
    except PlaidApiException as e:
        logger.error(f'Plaid API error creating link token for org {organization.name}: {e.body}')
        return None
    except ValueError as ve:  # Catch configuration errors from get_plaid_client
        logger.error(f'Configuration error for Plaid: {ve}')
        return None
    except Exception as e:
        logger.error(f'Unexpected error creating link token for org {organization.name}: {e}')
        return None


def exchange_public_token(public_token: str, user, organization: Organization, institution_id: str, institution_name: str):
    '''Exchanges a public_token for an access_token and item_id.'''
    try:
        client = get_plaid_client()
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = client.item_public_token_exchange(request)
        access_token = response['access_token']
        item_id = response['item_id']

        # Store the PlaidItem
        # Ensure access_token is encrypted before saving in a real application
        plaid_item, created = PlaidItem.objects.update_or_create(
            organization=organization,
            item_id=item_id,
            defaults={
                'user': user,
                'access_token': access_token,  # IMPORTANT: Encrypt this in a real app
                'institution_id': institution_id,
                'institution_name': institution_name,
                'last_successful_sync': None,  # Initialize sync time
                'sync_cursor': None,  # Initialize cursor
            }
        )
        logger.info(f'Plaid item {("created" if created else "updated")} for org {organization.name}, item_id: {item_id}')
        return plaid_item
    except PlaidApiException as e:
        logger.error(f'Plaid API error exchanging public token for org {organization.name}: {e.body}')
        return None
    except ValueError as ve:  # Catch configuration errors
        logger.error(f'Configuration error for Plaid: {ve}')
        return None
    except Exception as e:
        logger.error(f'Unexpected error exchanging public token for org {organization.name}: {e}')
        return None


def fetch_plaid_transactions(plaid_item: PlaidItem):
    '''Fetches transactions for a given PlaidItem.'''
    try:
        client = get_plaid_client()
        added_count = 0

        request = TransactionsSyncRequest(
            access_token=plaid_item.access_token,
            cursor=plaid_item.sync_cursor if plaid_item.sync_cursor else None  # Pass None if cursor is empty/null
        )
        response = client.transactions_sync(request)

        transactions_data = response.get('added', [])
        # TODO: Handle 'modified' and 'removed' transactions for full sync

        for tx_data in transactions_data:
            # Ensure amount is a Decimal
            amount = tx_data.get('amount')
            if amount is None:
                logger.warning(f"Skipping transaction with no amount: {tx_data.get('transaction_id')}")
                continue

            # Map Plaid pending status to our StagedBankTransaction status
            status_source = StagedBankTransaction.PENDING if tx_data.get('pending', False) else StagedBankTransaction.POSTED

            _, created = StagedBankTransaction.objects.update_or_create(
                organization=plaid_item.organization,
                transaction_id_source=tx_data['transaction_id'],  # Plaid's unique transaction ID
                defaults={
                    'plaid_item': plaid_item,
                    'account_id_source': tx_data['account_id'],
                    'date': tx_data['date'],
                    'posted_date': tx_data.get('authorized_date'),  # Or use 'datetime'
                    'name': tx_data['name'],
                    'merchant_name': tx_data.get('merchant_name'),
                    'amount': amount,
                    'currency_code': tx_data['iso_currency_code'],
                    'category_source': ', '.join(tx_data.get('category', [])) if tx_data.get('category') else None,
                    'status_source': status_source,
                    'raw_data': tx_data.to_dict(),
                    'source': 'PLAID',
                    # reconciliation_status defaults to UNMATCHED
                }
            )
            if created:
                added_count += 1

        plaid_item.sync_cursor = response.get('next_cursor')
        plaid_item.last_successful_sync = timezone.now()
        plaid_item.save(update_fields=['sync_cursor', 'last_successful_sync'])

        logger.info(f'{added_count} new transactions synced for item {plaid_item.item_id}. Next cursor: {plaid_item.sync_cursor}')
        return added_count
    except PlaidApiException as e:
        logger.error(f'Plaid API error fetching transactions for item {plaid_item.item_id}: {e.body}')
        return -1
    except ValueError as ve:  # Catch configuration errors
        logger.error(f'Configuration error for Plaid: {ve}')
        return -1
    except Exception as e:
        logger.error(f'Unexpected error fetching Plaid transactions for item {plaid_item.item_id}: {e}')
        return -1
