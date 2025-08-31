from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .forms import ExcelUploadForm
from decimal import Decimal
import pandas as pd
import io


@login_required(login_url='signin')
def process_excel_upload(request):
    """Process uploaded Excel file for tranche calculations"""
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')
    
    excel_results = None
    error_message = None
    
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                excel_file = form.cleaned_data['excel_file']
                
                # Read Excel file using pandas with openpyxl engine
                df = pd.read_excel(
                    io.BytesIO(excel_file.read()),
                    engine='openpyxl'
                )
                
                # Validate required columns
                required_columns = [
                    'agent_name', 'buyer_name', 'project_name', 'unit_id',
                    'total_contract_price', 'commission_rate'
                ]
                
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    error_message = f"Missing required columns: {', '.join(missing_columns)}"
                else:
                    # Process each row and perform tranche calculations
                    processed_results = []
                    
                    for index, row in df.iterrows():
                        try:
                            # Extract data from row
                            agent_name = str(row['agent_name']).strip()
                            buyer_name = str(row['buyer_name']).strip()
                            project_name = str(row['project_name']).strip()
                            unit_id = str(row['unit_id']).strip()
                            total_contract_price = Decimal(str(row['total_contract_price']))
                            commission_rate = Decimal(str(row['commission_rate']))
                            
                            # Optional fields with defaults
                            vat_rate = Decimal(str(row.get('vat_rate', 12)))
                            withholding_tax_rate = Decimal(str(row.get('withholding_tax_rate', 10)))
                            process_fee_percentage = Decimal(str(row.get('process_fee_percentage', 0)))
                            option1_percentage = Decimal(str(row.get('option1_percentage', 50)))
                            option2_percentage = Decimal(str(row.get('option2_percentage', 50)))
                            other_deductions = Decimal(str(row.get('other_deductions', 0)))
                            
                            # Perform tranche calculations
                            calculations = perform_tranche_calculations(
                                total_contract_price=total_contract_price,
                                commission_rate=commission_rate,
                                vat_rate=vat_rate,
                                withholding_tax_rate=withholding_tax_rate,
                                process_fee_percentage=process_fee_percentage,
                                option1_percentage=option1_percentage,
                                option2_percentage=option2_percentage,
                                other_deductions=other_deductions
                            )
                            
                            # Add row data to calculations
                            calculations.update({
                                'row_number': index + 1,
                                'agent_name': agent_name,
                                'buyer_name': buyer_name,
                                'project_name': project_name,
                                'unit_id': unit_id,
                                'total_contract_price': float(total_contract_price),
                                'commission_rate': float(commission_rate),
                            })
                            
                            processed_results.append(calculations)
                            
                        except Exception as row_error:
                            processed_results.append({
                                'row_number': index + 1,
                                'error': f"Error processing row {index + 1}: {str(row_error)}",
                                'agent_name': row.get('agent_name', 'N/A'),
                                'buyer_name': row.get('buyer_name', 'N/A'),
                                'project_name': row.get('project_name', 'N/A'),
                            })
                    
                    excel_results = {
                        'total_rows': len(df),
                        'processed_rows': len(processed_results),
                        'results': processed_results,
                        'filename': excel_file.name
                    }
                    
                    messages.success(request, f'Successfully processed {len(processed_results)} rows from {excel_file.name}')
                    
            except Exception as e:
                error_message = f"Error processing Excel file: {str(e)}"
                messages.error(request, error_message)
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = ExcelUploadForm()
    
    # Return JSON response for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': excel_results is not None,
            'results': excel_results,
            'error': error_message
        })
    
    context = {
        'excel_form': form,
        'excel_results': excel_results,
        'error_message': error_message,
    }
    
    return render(request, 'tranches.html', context)


def perform_tranche_calculations(total_contract_price, commission_rate, vat_rate=12, 
                                withholding_tax_rate=10, process_fee_percentage=0, 
                                option1_percentage=50, option2_percentage=50, other_deductions=0):
    """
    Perform tranche calculations similar to the existing tranches_view logic
    Returns a dictionary with all calculated values
    """
    try:
        # Convert percentages to decimals
        vat_rate_decimal = vat_rate / Decimal(100)
        commission_rate_decimal = commission_rate / Decimal(100)
        withholding_tax_rate_decimal = withholding_tax_rate / Decimal(100)
        process_fee_percentage_decimal = process_fee_percentage / Decimal(100)
        option1_percentage_decimal = option1_percentage / Decimal(100)
        option2_percentage_decimal = option2_percentage / Decimal(100)
        
        # Calculate Net of VAT base (TCP / (1 + VAT))
        net_of_vat_base = total_contract_price / (Decimal(1) + vat_rate_decimal)
        
        # Calculate process fee deduction
        less_process_fee = net_of_vat_base * process_fee_percentage_decimal
        
        # Calculate commissionable amount
        commissionable_amount = net_of_vat_base - less_process_fee
        
        # Calculate gross commission
        gross_commission = commissionable_amount * commission_rate_decimal
        
        # Calculate commission net of VAT
        commission_net_vat = gross_commission / (Decimal(1) + vat_rate_decimal)
        
        # Calculate withholding tax
        withholding_tax = commission_net_vat * withholding_tax_rate_decimal
        
        # Calculate net commission before splits
        net_commission_before_splits = gross_commission - withholding_tax - other_deductions
        
        # Calculate commission splits
        dp_period_commission = net_commission_before_splits * option1_percentage_decimal
        lto_commission = net_commission_before_splits * option2_percentage_decimal
        
        # Calculate taxes for each split
        dp_period_tax = dp_period_commission * withholding_tax_rate_decimal
        lto_tax = lto_commission * withholding_tax_rate_decimal
        
        # Calculate net amounts for each split
        dp_period_net = dp_period_commission - dp_period_tax
        lto_net = lto_commission - lto_tax
        
        return {
            'net_of_vat_base': float(net_of_vat_base),
            'less_process_fee': float(less_process_fee),
            'commissionable_amount': float(commissionable_amount),
            'gross_commission': float(gross_commission),
            'commission_net_vat': float(commission_net_vat),
            'withholding_tax': float(withholding_tax),
            'other_deductions': float(other_deductions),
            'net_commission_before_splits': float(net_commission_before_splits),
            'dp_period_commission': float(dp_period_commission),
            'lto_commission': float(lto_commission),
            'dp_period_tax': float(dp_period_tax),
            'lto_tax': float(lto_tax),
            'dp_period_net': float(dp_period_net),
            'lto_net': float(lto_net),
            'total_net_commission': float(dp_period_net + lto_net),
        }
        
    except Exception as e:
        return {'error': f"Calculation error: {str(e)}"}
