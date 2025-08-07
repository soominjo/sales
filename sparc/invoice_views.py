from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.db.models import Sum
from decimal import Decimal
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from django.conf import settings
import tempfile
import os
from io import BytesIO
import subprocess
import base64
from pathlib import Path


def _compute(invoice):
    """Calculate amounts based on net commission (unit_price) and withholding tax rate."""
    qty = invoice.qty
    net_comm = invoice.unit_price  # Net Commission per unit
    tax_rate = invoice.vat_rate / Decimal("100")  # withholding tax rate (e.g. 0.10)

    tax_amount = (net_comm * tax_rate).quantize(Decimal("0.01"))
    expected_comm = (net_comm - tax_amount).quantize(Decimal("0.01"))

    return {
        "qty": qty,
        "net_price": net_comm,
        "vat_amount": tax_amount,
        "subtotal": expected_comm,
    }
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now

from .models import BillingInvoice, TranchePayment

__all__ = [
    "generate_invoice_number",
    "invoice_view",
    "create_invoice",
    "invoice_pdf",
    "invoice_csv",
    "email_invoice",
    "sign_invoice",
    "upload_signature",
]


def _generate_invoice_image(html_content, invoice_no):
    """Generate a high-quality PNG image from HTML invoice content.
    
    Args:
        html_content (str): The complete HTML content of the invoice
        invoice_no (str): Invoice number for filename
        
    Returns:
        bytes: PNG image data, or None if generation fails
    """
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
            # Prepare HTML with print-optimized CSS
            optimized_html = _prepare_html_for_image(html_content)
            html_file.write(optimized_html)
            html_file.flush()
            
            # Generate PNG using wkhtmltoimage
            output_path = html_file.name.replace('.html', '.png')
            
            # Get the executable path from settings
            executable = getattr(settings, 'WKHTMLTOIMAGE_PATH', 'wkhtmltoimage')

            # Explicitly check if the executable file exists before trying to run it
            if not os.path.exists(executable):
                print(f"FATAL: wkhtmltoimage executable not found at the specified path: {executable}")
                return _generate_invoice_image_weasyprint(html_content, invoice_no)

            # wkhtmltoimage command with high-quality settings
            cmd = [
                executable,
                '--format', 'png',
                '--quality', '100',
                '--width', '1200',
                '--height', '1600',
                '--disable-smart-width',
                '--encoding', 'UTF-8',
                '--javascript-delay', '1000',
                '--no-stop-slow-scripts',
                '--debug-javascript',
                '--enable-local-file-access',
                html_file.name,
                output_path
            ]
            
            # Execute wkhtmltoimage and catch potential FileNotFoundError
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except FileNotFoundError:
                print(f"FATAL: The system could not find the executable, even though it exists at: {executable}. This might be a permissions issue.")
                return _generate_invoice_image_weasyprint(html_content, invoice_no)

            # Check for errors and log them
            if result.returncode != 0:
                error_log = result.stderr.strip()
                print(f"wkhtmltoimage error: {error_log}")
                # Try the fallback method
                return _generate_invoice_image_weasyprint(html_content, invoice_no)

            if os.path.exists(html_file.name.replace('.html', '.png')):
                # Read the generated PNG
                with open(html_file.name.replace('.html', '.png'), 'rb') as img_file:
                    image_data = img_file.read()
                
                # Clean up temporary files
                try:
                    os.unlink(html_file.name)
                    os.unlink(output_path)
                except OSError:
                    pass
                    
                return image_data
            else:
                print(f"wkhtmltoimage failed: {result.stderr}")
                return None
                
    except subprocess.TimeoutExpired:
        print("wkhtmltoimage timed out")
        return None
    except FileNotFoundError:
        print("wkhtmltoimage not found. Please install wkhtmltopdf package.")
        # Fallback to weasyprint method
        return _generate_invoice_image_weasyprint(html_content, invoice_no)
    except Exception as e:
        print(f"Error generating invoice image: {e}")
        return None


def _prepare_html_for_image(html_content):
    """Optimize HTML content for high-quality image generation.
    
    Args:
        html_content (str): Original HTML content
        
    Returns:
        str: Optimized HTML with print-specific CSS
    """
    # Add print-optimized CSS
    print_css = """
    <style>
        @media print, screen {
            html, body {
                -webkit-print-color-adjust: exact !important;
                color-adjust: exact !important;
                print-color-adjust: exact !important;
                background: white !important;
                font-family: system-ui, -apple-system, sans-serif !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            .max-w-4xl {
                max-width: 1024px !important; /* Tailwind's max-w-4xl is 56rem = 896px, but we give it more room */
                margin: 0 auto !important;
            }
            .no-print, .btn-sig, .btn-sig-clear {
                display: none !important;
            }
            .bg-blue-600 {
                background-color: #2563eb !important;
            }
            .text-blue-600 {
                color: #2563eb !important;
            }
            .border-blue-600 {
                border-color: #2563eb !important;
            }
            .bg-amber-50 {
                background-color: #fffbeb !important;
            }
            .border-amber-400 {
                border-color: #f59e0b !important;
            }
            .text-amber-500 {
                color: #f59e0b !important;
            }
            .text-gray-800 { color: #1f2937 !important; }
            .text-gray-600 { color: #4b5563 !important; }
            .text-gray-500 { color: #6b7280 !important; }
            .bg-gray-50 { background-color: #f9fafb !important; }
            .border-gray-200 { border-color: #e5e7eb !important; }
            .signature-container img {
                max-height: 64px !important;
                display: block !important;
            }
        }
    </style>
    """
    
    # Insert the print CSS before the closing head tag
    if '</head>' in html_content:
        html_content = html_content.replace('</head>', f'{print_css}</head>')
    else:
        # If no head tag, add it
        html_content = f'<head>{print_css}</head>' + html_content
    
    return html_content


def _generate_invoice_image_weasyprint(html_content, invoice_no):
    """Fallback method using WeasyPrint to generate PNG image.
    
    Args:
        html_content (str): The complete HTML content
        invoice_no (str): Invoice number for filename
        
    Returns:
        bytes: PNG image data, or None if generation fails
    """
    try:
        from weasyprint import HTML

        # Prepare HTML for WeasyPrint
        optimized_html = _prepare_html_for_image(html_content)

        # Use WeasyPrint to write directly to a PNG in memory
        # This removes the dependency on pdf2image and poppler
        png_buffer = BytesIO()
        HTML(string=optimized_html).write_png(png_buffer)
        png_buffer.seek(0)
        image_data = png_buffer.read()

        if image_data:
            return image_data
        else:
            print("WeasyPrint fallback failed to generate image data.")
            return None

    except ImportError:
        print("WeasyPrint library not found. Cannot generate image.")
        return None
    except Exception as e:
        # Catching other potential errors from WeasyPrint
        print(f"An error occurred during the WeasyPrint fallback: {e}")
        return None


def generate_invoice_number() -> str:
    """Return next incremental invoice number formatted as BI00000001, BI00000002, ..."""
    last = BillingInvoice.objects.order_by('-id').first()
    if last and last.invoice_no.startswith('BI') and last.invoice_no[2:].isdigit():
        next_num = int(last.invoice_no[2:]) + 1
    else:
        next_num = 1
    return f"BI{next_num:08d}"


@login_required
def create_invoice(request, tranche_id):
    """Create invoice for given TranchePayment and redirect to invoice page."""
    tranche = get_object_or_404(TranchePayment, pk=tranche_id)
    existing = tranche.invoices.first()
    if existing:
        return redirect('invoice_view', invoice_id=existing.id)

    # The reference number can be based on the tranche record ID for uniqueness
    reference_no = f"Tranche-{tranche.tranche_record.id}"

    invoice = BillingInvoice.objects.create(
        tranche=tranche,
        invoice_no=generate_invoice_number(),
        reference_no=f"SERVICE INVOICE {reference_no}",
        due_date=tranche.expected_date,
        # store net amount (unit price) so that invoice columns match schedule
        # Calculate net commission before withholding tax so invoice and schedule align
        unit_price=(tranche.expected_amount / (1 - (tranche.tranche_record.deduction_tax_rate / Decimal('100')))).quantize(Decimal('0.01')),
        vat_rate=tranche.tranche_record.deduction_tax_rate,
        prepared_by=request.user,
        prepared_by_date=now()
    )
    return redirect('invoice_view', invoice_id=invoice.id)


def _get_invoice_context(invoice, request):
    """Generate the context dictionary for an invoice view."""
    # --- Default compute financials ---
    data = _compute(invoice)
    qty = data["qty"]
    net_price = data["net_price"]
    vat_amount = data["vat_amount"]
    subtotal = data["subtotal"]
    amount_net_vat = net_price

    # --- Check if this is a Loan Take Out invoice and override with LTO data ---
    lto_tranches = []
    is_lto_invoice = False
    
    if invoice.tranche and invoice.tranche.tranche_record and invoice.tranche.is_lto:
        record = invoice.tranche.tranche_record
        is_lto_invoice = True
        
        # Get LTO tranche data
        lto_payment = record.payments.filter(is_lto=True).first()
        if lto_payment:
            # Calculate LTO values (similar to view_tranche logic)
            vat_rate_decimal = record.vat_rate / Decimal(100)
            net_of_vat_base = record.total_contract_price / (Decimal(1) + vat_rate_decimal)
            less_process_fee = (record.total_contract_price * record.process_fee_percentage) / Decimal(100)
            total_selling_price = net_of_vat_base - less_process_fee
            gross_commission = total_selling_price * (record.commission_rate / Decimal(100))
            net_of_vat = gross_commission / (Decimal(1) + vat_rate_decimal)
            net_commission = gross_commission - (net_of_vat * (record.withholding_tax_rate / Decimal(100)))
            
            # Calculate LTO values
            option2_value = net_commission * (record.option2_percentage / Decimal(100))
            option2_tax_rate = record.option2_tax_rate / Decimal(100)
            lto_deduction_value = option2_value
            lto_deduction_tax = lto_deduction_value * option2_tax_rate
            lto_deduction_net = lto_deduction_value - lto_deduction_tax
            lto_expected_commission = lto_deduction_net.quantize(Decimal('0.01'))
            
            # Override invoice table data with LTO-specific values
            net_price = lto_deduction_value  # Net Commission (before tax)
            vat_amount = lto_deduction_tax   # Less Tax
            subtotal = lto_expected_commission  # Expected Commission (after tax)
            amount_net_vat = lto_deduction_value
            
            lto_tranches.append({
                'tranche': lto_payment,
                'tax_amount': lto_deduction_tax,
                'net_amount': lto_deduction_net,
                'expected_commission': lto_expected_commission,
                'balance': lto_expected_commission - lto_payment.received_amount,
                'initial_balance': lto_payment.initial_balance
            })

    # Default values for summary
    summary_gross_commission = Decimal('0.00')
    summary_net_of_vat = Decimal('0.00')
    summary_withholding_tax_amount = Decimal('0.00')
    summary_net_commission = Decimal('0.00')
    summary_vat_rate = Decimal('0.00')
    summary_vat_amount = Decimal('0.00')
    summary_withholding_tax_rate = Decimal('0.00')

    # Use the definitive tranche calculation logic for the summary section
    if invoice.tranche and invoice.tranche.tranche_record:
        record = invoice.tranche.tranche_record

        # Same base calculation for all invoices based on the same tranche record
        vat_rate_decimal = record.vat_rate / Decimal(100)
        net_of_vat_base = record.total_contract_price / (Decimal(1) + vat_rate_decimal)
        less_process_fee = (record.total_contract_price * record.process_fee_percentage) / Decimal(100)
        total_selling_price = net_of_vat_base - less_process_fee
        
        # Gross commission is based on the total selling price
        summary_gross_commission = total_selling_price * (record.commission_rate / Decimal(100))
        
        # VAT calculations
        summary_vat_rate = record.vat_rate
        summary_net_of_vat = summary_gross_commission / (Decimal(1) + vat_rate_decimal)
        summary_vat_amount = summary_gross_commission - summary_net_of_vat
        
        # Withholding tax calculations
        summary_withholding_tax_rate = record.withholding_tax_rate
        withholding_tax_rate_decimal = summary_withholding_tax_rate / Decimal(100)
        summary_withholding_tax_amount = summary_net_of_vat * withholding_tax_rate_decimal
        
        # Final net commission
        summary_net_commission = summary_gross_commission - summary_withholding_tax_amount

    # --- Prepare Billing Statement Data ---
    billing_statement_items = []
    if invoice.tranche and invoice.tranche.tranche_record:
        record = invoice.tranche.tranche_record
        all_tranches = record.payments.filter(status='Received').order_by('expected_date')
        
        # Calculate the total expected commission for the entire record to be used as the base for percentage calculation
        total_expected_commission = record.payments.aggregate(total=Sum('expected_amount'))['total'] or Decimal('1.0')
        if total_expected_commission == 0:
            total_expected_commission = Decimal('1.0') # Avoid division by zero

        for tranche_payment in all_tranches:
            # Calculate the percentage of this tranche relative to the total expected commission
            percentage = (tranche_payment.expected_amount / total_expected_commission) * 100
            
            billing_statement_items.append({
                'date_received': tranche_payment.date_received,
                'amount': tranche_payment.received_amount,
                'status': tranche_payment.status,
                'percentage': percentage,
            })

    # Check for previously released commissions for the same deal (TrancheRecord)
    previous_invoices = []
    if invoice.tranche and invoice.tranche.tranche_record:
        record = invoice.tranche.tranche_record
        # Find all other received payments for this record
        other_payments = record.payments.filter(status='Received').exclude(pk=invoice.tranche.pk).order_by('-date_received')

        total_expected_commission_for_record = record.payments.aggregate(total=Sum('expected_amount'))['total'] or Decimal('1.0')

        for payment in other_payments:
            # Find the invoice associated with that payment
            prev_invoice = payment.invoices.first()
            if prev_invoice:
                percentage = (payment.expected_amount / total_expected_commission_for_record) * 100 if total_expected_commission_for_record else 0
                
                previous_invoices.append({
                    'tranche_name': f"Tranche-{record.id}",  # Use the record ID for a consistent name
                    'release_date': payment.date_received,
                    'amount': payment.received_amount,
                    'percentage': percentage,
                    'invoice_no': prev_invoice.invoice_no,
                })

    context = {
        "invoice": invoice,
        "qty": qty,
        "net_price": net_price,
        "vat_amount": vat_amount,
        "subtotal": subtotal,
        "amount_net_vat": amount_net_vat,
        "total_due": subtotal,
        "payment_terms": invoice.tranche.tranche_record.tranche_option,
        "today": now().date(),
        "lto_tranches": lto_tranches,
        "is_lto_invoice": is_lto_invoice,  # Flag to identify LTO invoices
        "previous_invoices": previous_invoices,
        # Enhanced summary fields - Calculated from TrancheRecord
        "summary_gross_commission": summary_gross_commission,
        "summary_vat_rate": summary_vat_rate,
        "summary_vat_amount": summary_vat_amount,
        "summary_net_of_vat": summary_net_of_vat,
        "summary_withholding_tax_rate": summary_withholding_tax_rate,
        "summary_withholding_tax_amount": summary_withholding_tax_amount,
        "summary_net_commission": summary_net_commission,
        "billing_statement_items": billing_statement_items,
    }
    
    # Permissions
    can_edit_bill_to = request.user.is_staff
    can_check = request.user.is_staff
    can_approve = request.user.is_superuser
    can_prepare = request.user == invoice.prepared_by
    
    context.update({
        'can_edit_bill_to': can_edit_bill_to,
        'can_check': can_check,
        'can_approve': can_approve,
        'can_prepare': can_prepare,
    })
    
    return context


def invoice_view(request, invoice_id):
    """Render a printable invoice page for the given BillingInvoice."""
    invoice = get_object_or_404(BillingInvoice, pk=invoice_id)
    context = _get_invoice_context(invoice, request)
    return render(request, 'invoice.html', context)


@login_required
@require_POST
def sign_invoice(request, invoice_id, role):
    invoice = get_object_or_404(BillingInvoice, id=invoice_id)

    if role == 'checked_by' and request.user.is_staff and not invoice.checked_by:
        invoice.checked_by = request.user
        invoice.checked_by_date = now()
        invoice.save()
        messages.success(request, 'Invoice successfully marked as checked.')
    elif role == 'approved_by' and request.user.is_superuser and not invoice.approved_by:
        invoice.approved_by = request.user
        invoice.approved_by_date = now()
        invoice.save()
        messages.success(request, 'Invoice successfully marked as approved.')
    else:
        messages.error(request, 'You do not have permission to perform this action or it has already been signed.')

    return redirect('invoice_view', invoice_id=invoice.id)


@login_required
@require_POST
def upload_signature(request, invoice_id, role):
    invoice = get_object_or_404(BillingInvoice, id=invoice_id)
    action = request.POST.get('action', 'upload')

    # Permission checks
    if role == 'prepared_by' and request.user != invoice.prepared_by:
        return JsonResponse({'success': False, 'error': 'You do not have permission to sign as prepared by.'}, status=403)
    if role == 'checked_by' and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'You do not have permission to sign as checked by.'}, status=403)
    if role == 'approved_by' and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'You do not have permission to sign as approved by.'}, status=403)

    signature_field_name = f"{role}_signature"
    signature_field = getattr(invoice, signature_field_name, None)

    if action == 'clear':
        if signature_field and signature_field.name:
            # Delete the old file from storage
            if os.path.exists(signature_field.path):
                os.remove(signature_field.path)
            # Clear the field in the model
            setattr(invoice, signature_field_name, None)
            invoice.save()
            return JsonResponse({'success': True, 'message': 'Signature cleared.'})
        else:
            return JsonResponse({'success': False, 'error': 'No signature to clear.'}, status=400)

    elif 'signature_image' in request.FILES:
        signature_image = request.FILES['signature_image']

        # Delete old signature if it exists
        if signature_field and signature_field.name:
            if os.path.exists(signature_field.path):
                os.remove(signature_field.path)

        setattr(invoice, signature_field_name, signature_image)
        invoice.save()

        # We need to refresh the instance to get the new URL
        invoice.refresh_from_db()
        new_signature_field = getattr(invoice, signature_field_name)
        
        return JsonResponse({
            'success': True,
            'message': 'Signature uploaded successfully.',
            'signature_url': new_signature_field.url if new_signature_field else ''
        })

    return JsonResponse({'success': False, 'error': 'Invalid action.'}, status=400)


@login_required
def invoice_pdf(request, invoice_id):
    """Return invoice as downloadable PDF using WeasyPrint."""
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    try:
        from weasyprint import HTML
    except ImportError:
        return HttpResponse("WeasyPrint is not installed", status=500)

    invoice = get_object_or_404(BillingInvoice, pk=invoice_id)
    context = _get_invoice_context(invoice, request)

    # Provide the absolute path to the logo for WeasyPrint
    logo_path = os.path.join(settings.BASE_DIR, 'sparc', 'static', 'media', 'LOGO.png')
    context['company_logo_path'] = f'file://{logo_path}'

    # Read the CSS file
    css_path = os.path.join(settings.BASE_DIR, 'sparc', 'static', 'css', 'enhanced-styles.css')
    try:
        with open(css_path, 'r') as f:
            css_string = f.read()
    except FileNotFoundError:
        return HttpResponse("CSS file not found.", status=500)

    # Render the dedicated PDF template
    html_string = render_to_string("invoice_pdf.html", context)
    
    # Inject the CSS into the template
    final_html = html_string.replace('</head>', f'<style>{css_string}</style></head>')

    # Generate the PDF
    pdf_file = HTML(string=final_html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice_{invoice.invoice_no}.pdf"'
    return response


@login_required
def email_invoice(request, invoice_id):
    """Generate a static PNG image of the complete invoice and send as email attachment."""
    if request.method == 'POST':
        print("\n--- [EMAIL INVOICE PROCESS STARTED] ---")
        invoice = get_object_or_404(BillingInvoice, pk=invoice_id)
        recipient_email = request.POST.get('email')

        if not recipient_email:
            print("[ERROR] No recipient email provided.")
            return JsonResponse({'status': 'error', 'message': 'Email address not provided.'}, status=400)

        print(f"Step 1: Preparing to email invoice {invoice.invoice_no} to {recipient_email}")

        # Generate the complete invoice context with all data
        context = _get_invoice_context(invoice, request)
        html_body = render_to_string("invoice.html", context)

        # Make the HTML self-contained with absolute paths and embedded CSS
        final_html = _make_html_self_contained(html_body, request)



        subject = f"Invoice {invoice.invoice_no} from {getattr(settings, 'COMPANY_NAME', 'Inner Sparc Realty Services')}"
        
        text_body = f"""Dear Valued Client,\n\nPlease find attached your invoice #{invoice.invoice_no}.\n\nThank you for your business!\n\nBest regards,\nInner Sparc Realty Services"""
        
        email = EmailMessage(
            subject,
            body=text_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@innersparc.com'),
            to=[recipient_email],
        )
        
        print("Step 2: Generating invoice image...")
        image_data = _generate_invoice_image(final_html, invoice.invoice_no)

        json_status = 'error'
        message = ''

        if image_data:
            print(f"Step 3: Image generation SUCCEEDED. Size: {len(image_data)} bytes.")
            email.attach(
                f'Invoice_{invoice.invoice_no}.png',
                image_data,
                'image/png'
            )
            message = f"Invoice {invoice.invoice_no} with image attachment sent to {recipient_email}."
            json_status = 'success'
        else:
            print("Step 3: Image generation FAILED. Email will be sent with text body only.")
            message = f"Invoice {invoice.invoice_no} sent to {recipient_email}, but image generation failed. Please check server logs."
            json_status = 'warning'

        try:
            print("Step 4: Attempting to send email...")
            email.send()
            print("Step 5: Email sent SUCCESSFULLY.")
            if json_status == 'success':
                messages.success(request, message)
            else:
                messages.warning(request, message)
            return JsonResponse({'status': json_status, 'message': message})
        except Exception as e:
            error_message = f'An error occurred while sending the email: {e}'
            print(f"Step 5: Email sending FAILED. Error: {e}")
            messages.error(request, error_message)
            return JsonResponse({'status': 'error', 'message': error_message}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


def _make_html_self_contained(html_content, request):
    """
    Parses HTML, converts all static resource URLs to absolute paths,
    and injects the main CSS file to ensure proper rendering in wkhtmltoimage.
    """
    print("--- Making HTML self-contained for image generation ---")
    soup = BeautifulSoup(html_content, "html.parser")
    base_url = request.build_absolute_uri('/')

    # Convert all image and script URLs to absolute paths
    for tag in soup.find_all(['img', 'script']):
        if tag.get('src'):
            absolute_url = urljoin(base_url, tag['src'].lstrip('/'))
            tag['src'] = absolute_url
            print(f"Converted resource URL: {absolute_url}")

    # Remove existing stylesheet links to prevent conflicts
    for tag in soup.find_all('link', rel="stylesheet"):
        tag.decompose()

    # Inject the main CSS file directly into the head
    try:
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'dist', 'styles.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css_string = f.read()
        
        style_tag = soup.new_tag('style')
        style_tag.string = css_string
        
        if soup.head:
            soup.head.append(style_tag)
            print("CSS styles successfully injected into HTML head.")
        else:
            print("[WARNING] No <head> tag found to inject CSS into.")

    except FileNotFoundError:
        print("[WARNING] styles.css not found. The generated image may be unstyled.")
    except Exception as e:
        print(f"[WARNING] An error occurred while injecting CSS: {e}")

    return str(soup)


def invoice_csv(request, invoice_id):
    """Return invoice data as CSV so Excel can open it."""
    import csv
    from django.http import HttpResponse

    invoice = get_object_or_404(BillingInvoice, pk=invoice_id)
    data = _compute(invoice)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="invoice_{invoice.invoice_no}.csv"'

    writer = csv.writer(response)
    writer.writerow(["Invoice No", invoice.invoice_no])
    writer.writerow(["Issue Date", invoice.issue_date])
    writer.writerow(["Due Date", invoice.due_date])
    writer.writerow([])

    writer.writerow(["Item Code", "Description", "Quantity", "Net Commission", "Less Tax", "Expected Commission"])
    writer.writerow([
        "SC",
        f"Seller's Commission – {invoice.due_date.strftime('%B %Y')}",
        invoice.qty,
        f"{data['net_price']}",
        f"{data['vat_amount']}",
        f"{data['subtotal']}",
    ])

    writer.writerow([])
    writer.writerow(["TOTAL DUE", data['subtotal']])

    return response


@login_required
def update_bill_to(request, invoice_id):
    if request.method == 'POST':
        invoice = get_object_or_404(BillingInvoice, pk=invoice_id)
        invoice.client_name = request.POST.get('client_name', invoice.client_name)
        invoice.client_address = request.POST.get('client_address', invoice.client_address)
        invoice.client_tin = request.POST.get('client_tin', invoice.client_tin)
        invoice.save()
        messages.success(request, 'Billing information updated successfully.')
        return redirect('invoice_view', invoice_id=invoice.id)
    
    # Redirect to the invoice detail page if the request is not POST
    return redirect('invoice_view', invoice_id=invoice_id)
