import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)

def send_email(to_email, subject, html_content, from_email=None):
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL

    if not settings.SENDGRID_API_KEY or settings.SENDGRID_API_KEY == 'YOUR_SENDGRID_API_KEY_PLACEHOLDER':
        logger.error('SendGrid API Key not configured. Email not sent.')
        # In a real app, you might raise an error or handle this differently.
        # For dev, we might just log and return True to not block flow.
        print(f'SIMULATED EMAIL: To: {to_email}, Subject: {subject}, Body:\n{html_content}')
        return True # Simulate success if no key

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f'Email sent to {to_email}, status code: {response.status_code}')
        return response.status_code in [200, 202] # 202 Accepted
    except Exception as e:
        logger.error(f'Error sending email to {to_email}: {e}')
        return False

def send_invoice_email(invoice):
    # Prepare context for the email template
    # This should match ST-103: Email includes a link to view and pay the invoice online.
    # Payment link is future, for now, just a view link placeholder.
    context = {
        'invoice': invoice,
        'customer_name': invoice.customer.name,
        'invoice_number': invoice.invoice_number,
        'issue_date': invoice.issue_date.strftime('%Y-%m-%d'),
        'due_date': invoice.due_date.strftime('%Y-%m-%d'),
        'total_amount': invoice.total_amount,
        'items': invoice.items.all(),
        'organization_name': invoice.organization.name,
        'view_invoice_url': f'https://app.ledgerpro.example.com/invoices/{invoice.id}' # Placeholder URL
    }

    # Render HTML content from a template
    # For MVP, template is basic and included here.
    # In a real app, this would be a separate .html file.
    # Basic HTML template (very rudimentary)
    html_template_string = """
    <html>
        <body>
            <p>Dear {{ customer_name }},</p>
            <p>Please find attached your invoice {{ invoice_number }} from {{ organization_name }}.</p>
            <p><strong>Invoice Summary:</strong></p>
            <ul>
                <li>Invoice Number: {{ invoice_number }}</li>
                <li>Issue Date: {{ issue_date }}</li>
                <li>Due Date: {{ due_date }}</li>
                <li>Total Amount: {{ total_amount }}</li>
            </ul>
            <p><strong>Items:</strong></p>
            <table border='1' cellpadding='5' cellspacing='0'>
                <thead>
                    <tr><th>Description</th><th>Quantity</th><th>Unit Price</th><th>Amount</th></tr>
                </thead>
                <tbody>
                {% for item in items %}
                    <tr>
                        <td>{{ item.description }}</td>
                        <td>{{ item.quantity }}</td>
                        <td>{{ item.unit_price }}</td>
                        <td>{{ item.amount }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            <p>You can view the invoice online here: <a href='{{ view_invoice_url }}'>View Invoice</a></p>
            <p>Thank you for your business!</p>
            <p>Sincerely,<br/>The {{ organization_name }} Team</p>
        </body>
    </html>
    """
    # Using Django's template rendering for the string
    from django.template import Context, Template
    template = Template(html_template_string)
    html_content = template.render(Context(context))

    subject = f'Invoice {invoice.invoice_number} from {invoice.organization.name}'

    if not invoice.customer.email:
        logger.warning(f'Customer {invoice.customer.name} has no email address. Invoice {invoice.invoice_number} not sent.')
        return False

    return send_email(
        to_email=invoice.customer.email,
        subject=subject,
        html_content=html_content
    )
