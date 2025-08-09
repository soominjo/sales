from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import *
from .models import TrancheRecord
from decimal import Decimal
from .models import *
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.db.models import Sum, Q
from django.urls import reverse, reverse_lazy
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta
from django.db import IntegrityError
from django.utils import timezone
from django.db.models.functions import Coalesce, TruncMonth
from django.db.models import DecimalField
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator
import json
from collections import OrderedDict
from django.template.defaulttags import register
from .models import Property, Developer, BillingInvoice
from django.contrib.auth.decorators import user_passes_test
from .models import Team
from django.contrib.admin.views.decorators import staff_member_required

# ---------------- Email confirmation helpers -----------------

def send_activation_email(request, user):
    """Send activation link to the user's email address."""
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    activation_link = request.build_absolute_uri(
        reverse('activate_account', kwargs={'uidb64': uid, 'token': token})
    )
    subject = 'Confirm your Inner SPARC account'
    message = f"""Hi {user.get_full_name() or user.username},

Thank you for registering with Inner SPARC!

To complete your registration and start using your account, please confirm your email address by clicking the link below:

{activation_link}

This link will verify your email and activate your account so you can:
• Access your personalized dashboard
• View and manage your sales monitoring data
• Create and view commission slips and tranches
• Stay updated with the latest announcements and features

If you did not sign up for Inner SPARC, please ignore this email. Your account will not be activated unless you click the confirmation link.

If you have any questions or need assistance, feel free to contact our support team at innersparc07@gmail.com.

Welcome aboard, and we look forward to working with you!

Best regards,
Inner SPARC Team"""

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def send_approval_email(request, user):
    """Send account approval email to user."""
    sign_in_link = request.build_absolute_uri(reverse('signin'))
    subject = 'Your Inner SPARC Account Has Been Approved'
    message = f"""Hi {user.get_full_name() or user.username},

Great news! Your account has been successfully approved by Inner SPARC Realty Corporation.

You can now sign in and start accessing your account to:
• View and manage your sales records
• Generate and print commission slips
• Monitor tranches and incentive reports
• Stay updated with the latest company announcements and tools

To get started, please log in using the link below:

{sign_in_link}

If you have any questions or need assistance with your account, please contact our support team at innersparc07@gmail.com.

Welcome to Inner SPARC! We look forward to supporting your success.

Best regards,
Inner SPARC Team"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def activate_account(request, uidb64, token):
    """Activate user account after verifying email token."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Congratulations! Your email has been verified. You can now sign in once an administrator approves your account.')
    else:
        messages.error(request, 'Activation link is invalid or has expired.')
    return redirect('signin')





def home(request):
    # If the visitor is not logged in, send them to the sign-in page instead of showing the main app shell
    if not request.user.is_authenticated:
        return render(request, 'index.html')

def navbar(request):
    return render(request, 'navbar.html')

def signin(request):
    if request.user.is_authenticated:
        return redirect("profile")  # Redirect to profile if already logged in

    if request.method == "POST":
        username_or_email = request.POST.get("username_or_email")
        password = request.POST.get("password")

        if not username_or_email or not password:
            messages.error(request, 'Both username/email and password are required')
            return render(request, "signin.html")
        
        try:
            if '@' in username_or_email:
                user = User.objects.get(email=username_or_email)
            else:
                user = User.objects.get(username=username_or_email)
            
            # Now authenticate with the found user's username
            auth_user = authenticate(request, username=user.username, password=password)
            
            if auth_user is None:
                messages.error(request, 'Invalid password')
                return render(request, "signin.html")
            
            # Skip approval check for superusers
            if auth_user.is_superuser:
                login(request, auth_user)
                return redirect("profile")
            
            # Check if user is approved
            if hasattr(auth_user, 'profile'):
                if auth_user.profile.is_approved:
                    login(request, auth_user)
                    # Show welcome back message for approved users
                    messages.success(request, f'Welcome back, {auth_user.get_full_name() or auth_user.username}!')
                    return redirect("profile")
                else:
                    messages.warning(request, 'Your account is pending approval. Please wait for administrator approval.')
                    return render(request, "signin.html")
            else:
                messages.error(request, 'User profile not found')
                return render(request, "signin.html")
                
        except User.DoesNotExist:
            messages.error(request, 'No account found with this username/email')
            return render(request, "signin.html")

    return render(request, "signin.html")

@login_required
def signout(request):
    logout(request)
    return redirect("signin")

def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = False  # Require email confirmation
                # Set password directly using set_password
                user.set_password(form.cleaned_data['password1'])
                # Save first and last name to built-in User model fields
                user.first_name = form.cleaned_data.get('first_name', '')
                user.last_name = form.cleaned_data.get('last_name', '')
                user.save()
                # Send confirmation email
                send_activation_email(request, user)
                
                # Create profile
                Profile.objects.create(
                    user=user,
                    role=form.cleaned_data.get('role'),
                    team=form.cleaned_data.get('team'),
                    phone_number=form.cleaned_data.get('phone_number'),
                    first_name=form.cleaned_data.get('first_name'),
                    last_name=form.cleaned_data.get('last_name'),
                    is_approved=False  # Set initial approval status
                )
                
                messages.success(request, 'Account created successfully! Please confirm your email address. Check your inbox for the activation link.')
                return redirect('signin')
            except IntegrityError:
                messages.error(request, 'This username is already taken. Please choose a different username.')
                return render(request, 'signup.html', {'form': form})
    else:
        form = SignUpForm()

    return render(request, 'signup.html', {'form': form})

def signup_view(request):
    if request.method == 'POST':
        user_form = SignUpForm(request.POST)
        profile_form = ProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.save()

            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()

            login(request, user)
            return redirect('profile')
    else:
        user_form = SignUpForm()
        profile_form = ProfileForm()

    return render(request, 'signup.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

@login_required
def export_sales_excel(request):
    """Download current user's sales as an Excel workbook."""
    sales_qs = Sale.objects.filter(user=request.user).order_by('-date')
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    # Header
    ws.append(["Date", "Property", "Developer", "Amount", "Status"])
    for s in sales_qs:
        ws.append([
            s.date.strftime('%Y-%m-%d') if s.date else '',
            getattr(s, 'property_name', getattr(s, 'property', '')),
            s.developer,
            float(s.amount),
            s.status,
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=sales_transactions.xlsx'
    wb.save(response)
    return response


@login_required
def export_top5_excel(request):
    """Export top 5 members by role to Excel. Query param role expected."""
    role = request.GET.get('role', 'Sales Agent')
    from django.contrib.auth.models import User
    from django.db.models import Sum
    # Aggregate sales per user
    sales = Sale.objects.filter(user__profile__role=role)
    sales_totals = sales.values('user').annotate(total=Sum('amount')).order_by('-total')[:5]
    user_ids = [item['user'] for item in sales_totals]
    users = User.objects.filter(id__in=user_ids)
    wb = Workbook()
    ws = wb.active
    ws.title = f"Top5 {role}"
    ws.append(["Name", "Role", "Total Sales"])
    for item in sales_totals:
        user = users.get(id=item['user'])
        ws.append([
            user.get_full_name() or user.username,
            role,
            float(item['total'] or 0)
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=top5_{role.replace(" ", "_").lower()}.xlsx'
    wb.save(response)
    return response


def profile(request):
    # Get sales list
    if request.user.is_superuser:
        sales = Sale.objects.all().order_by('-date')
    else:
        sales = Sale.objects.filter(user=request.user).order_by('-date')
    
    # Get commission slips for the current user
    if request.user.is_superuser or request.user.profile.role == 'Sales Manager':
        commission_slips = CommissionSlip.objects.all().order_by('-date')
    else:
        commission_slips = CommissionSlip.objects.filter(
            sales_agent_name=request.user.get_full_name()
        ).order_by('-date')
    
    # Calculate sales summary directly from sales transactions
    total_cancelled = sales.filter(status='Cancelled').aggregate(
        Sum('amount'))['amount__sum'] or Decimal('0')
    
    total_active = sales.filter(status='Active').aggregate(
        Sum('amount'))['amount__sum'] or Decimal('0')
    
    # Calculate total sales (sum of active and cancelled)
    total_sales = total_active + total_cancelled

    # Calculate percentages
    active_percentage = (total_active / total_sales * 100) if total_sales > 0 else 0
    cancelled_percentage = (total_cancelled / total_sales * 100) if total_sales > 0 else 0
    
    # Calculate active sales count (units sold)
    active_count = sales.filter(status='Active').count()
    
    # Paginate sales
    page = request.GET.get('page', 1)
    paginator = Paginator(sales, 10)  # Show 10 sales per page
    try:
        paginated_sales = paginator.page(page)
    except:
        paginated_sales = paginator.page(1)
    
    # Add properties and developers to context
    properties = Property.objects.all().order_by('name')
    developers = Developer.objects.all().order_by('name')
    # Get commission data from receivables
    # Get commission data from receivables
    if request.user.is_superuser:
        commissions = Commission.objects.all().order_by('-date_released')
        tranche_records = TrancheRecord.objects.all()
    else:
        commissions = Commission.objects.filter(agent=request.user).order_by('-date_released')
        tranche_records = TrancheRecord.objects.filter(agent_name=request.user.get_full_name())

    total_commission_received = commissions.aggregate(Sum('commission_amount'))['commission_amount__sum'] or Decimal('0')

    # Calculate total expected commission from all tranches
    total_expected = Decimal('0')
    for record in tranche_records:
        total_expected += record.payments.aggregate(Sum('expected_amount'))['expected_amount__sum'] or Decimal('0')

    total_commission_remaining = total_expected - total_commission_received
    commission_count = commissions.count()

    # Get recent commissions for the table
    recent_commissions = commissions[:10]  # Get the 10 most recent

    context = {
        'sales': paginated_sales,
        'properties': properties,
        'developers': developers,
        'commission_slips': commission_slips,
        'total_active': total_active,
        'total_sales': total_sales,
        'total_cancelled': total_cancelled,
        'active_percentage': active_percentage,
        'cancelled_percentage': cancelled_percentage,
        'active_count': active_count,
        'properties': properties,
        'developers': developers,  # Add developers to context
        'total_commission_received': total_commission_received,
        'total_commission_remaining': total_commission_remaining,
        'commission_count': commission_count,
        'recent_commissions': recent_commissions,
    }
    return render(request, 'profile.html', context)


@login_required(login_url='signin')
def edit_profile_view(request):
    # Create profile if it doesn't exist
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update User model fields
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        
        # Handle profile image upload
        if request.FILES.get('image'):
            profile.image = request.FILES['image']
        
        # Update Profile model fields
        profile.phone_number = request.POST.get('phone_number', '')
        profile.address = request.POST.get('address', '')
        profile.city = request.POST.get('city', '')
        profile.state = request.POST.get('state', '')
        profile.zip_code = request.POST.get('zip_code', '')
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'edit_profile.html')


@login_required(login_url='signin')
@user_passes_test(lambda u: u.is_superuser)
def edit_user_profile(request, profile_id):
    """Allow a superuser to edit another user's profile."""
    profile = get_object_or_404(Profile, id=profile_id)
    user_obj = profile.user

    if request.method == 'POST':
        # Update User model fields
        user_obj.first_name = request.POST.get('first_name', '')
        user_obj.last_name = request.POST.get('last_name', '')
        user_obj.email = request.POST.get('email', '')
        user_obj.save()

        # Handle profile image upload
        if request.FILES.get('image'):
            profile.image = request.FILES['image']

        # Update Profile model fields
        profile.phone_number = request.POST.get('phone_number', '')
        profile.address = request.POST.get('address', '')
        profile.city = request.POST.get('city', '')
        profile.state = request.POST.get('state', '')
        profile.zip_code = request.POST.get('zip_code', '')
        profile.save()

        messages.success(request, f"{user_obj.username}'s profile updated successfully!")
        return redirect('approve')
    else:
        # For GET requests, show a confirmation page
        return render(request, 'edit_user_profile.html', {
            'target_user': user_obj,
            'target_profile': profile,
        })

@login_required(login_url='signin')
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('signin')

    # Get filter parameters
    period = request.GET.get('period', 'all')
    month = request.GET.get('month')
    year = request.GET.get('year')

    # Get all users and their sales
    team_members = User.objects.filter(
        profile__is_approved=True
    ).prefetch_related('sale_set')
    
    # Base query for all sales
    team_sales = Sale.objects.all()
    
    # Apply time period filters
    if period == 'monthly' and month:
        # If year is not specified, use current year
        filter_year = year if year else timezone.now().year
        team_sales = team_sales.filter(
            date__year=filter_year,
            date__month=int(month)
        )
    elif period == 'yearly' and year:
        team_sales = team_sales.filter(date__year=int(year))
    
    # Get count of all approved members
    approved_members_count = team_members.count()
    
    # Get active teams
    teams = Team.objects.filter(is_active=True)
    
    # Calculate total sales and recent sales growth for each member
    team_members_with_sales = []
    for member in team_members:
        member_sales = team_sales.filter(user=member)
        active_sales = member_sales.filter(status='Active')
        
        if member_sales.exists(): 
            latest_sale = member_sales.last()
            previous_total = member_sales.exclude(id=latest_sale.id).aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            # Default growth percentage
            if previous_total == 0:
                # First sale scenario: treat as +100% or -100% based on status
                growth_percentage = 100 if latest_sale.status == 'Active' else -100
            else:
                growth_percentage = (latest_sale.amount / previous_total) * 100
                if latest_sale.status == 'Cancelled':
                    growth_percentage = -growth_percentage
            
            team_members_with_sales.append({
                'user': member,
                'total_sales': member_sales.aggregate(total=Sum('amount'))['total'] or 0,
                'latest_sale': latest_sale.amount if latest_sale else 0,
                'growth_percentage': growth_percentage,
                'active_count': active_sales.count()
            })
        else:
            team_members_with_sales.append({
                'user': member,
                'total_sales': 0,
                'latest_sale': 0,
                'growth_percentage': 0,
                'previous_total': 0,
                'latest_sale_status': None,
                'active_count': 0
            })

    # Sort team members by total sales in descending order
    team_members_with_sales.sort(key=lambda x: x['total_sales'], reverse=True)
    
    # Calculate overall statistics
    total_sales = team_sales.aggregate(total=Sum('amount'))['total'] or 0
    active_sales = team_sales.filter(status='Active').aggregate(total=Sum('amount'))['total'] or 0
    cancelled_sales = team_sales.filter(status='Cancelled').aggregate(total=Sum('amount'))['total'] or 0
    
    # Calculate percentages
    active_percentage = (active_sales / total_sales * 100) if total_sales > 0 else 0
    cancelled_percentage = (cancelled_sales / total_sales * 100) if total_sales > 0 else 0

    # Get developer-specific sales data
    developer_sales = (
        team_sales
        .values('developer')
        .annotate(
            active=Sum('amount', filter=Q(status='Active')),
            cancelled=Sum('amount', filter=Q(status='Cancelled'))
        )
        .order_by('-active')
    )

    # Filter out developers with no sales
    developer_sales = [d for d in developer_sales if d['active'] or d['cancelled']]
    
    # Prepare data for developer chart
    developers = [item['developer'] for item in developer_sales]
    developer_active = [float(item['active'] or 0) for item in developer_sales]
    developer_cancelled = [float(item['cancelled'] or 0) for item in developer_sales]

    # --- PROPERTY/PROJECT SALES BREAKDOWN ---
    property_sales = (
        team_sales
        .values('property_name')
        .annotate(
            active=Sum('amount', filter=Q(status='Active')),
            cancelled=Sum('amount', filter=Q(status='Cancelled'))
        )
        .order_by('-active')
    )

    # Filter out properties with no sales
    property_sales = [p for p in property_sales if p['active'] or p['cancelled']]

    # Prepare data for property chart
    properties = [item['property_name'] for item in property_sales]
    property_active = [float(item['active'] or 0) for item in property_sales]
    property_cancelled = [float(item['cancelled'] or 0) for item in property_sales]

    # --- TOP DEVELOPERS & PROPERTIES FOR HIGHLIGHT SECTIONS ---
    # Compute developer totals (active + cancelled) then get top 5
    developer_totals_qs = (
        team_sales
        .values('developer')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )
    top_developers = []
    for row in developer_totals_qs:
        name = row['developer'] or 'Unknown'
        total = float(row['total'] or 0)
        dev_obj = Developer.objects.filter(name=name).first()
        if dev_obj:
            dev_obj.total_sales = total  # attach dynamic attribute for template
            top_developers.append(dev_obj)
        else:
            # Create a lightweight object with needed attrs when Developer record missing
            top_developers.append(type('Dev', (), {'name': name, 'image': None, 'total_sales': total}))

    # Compute property/project totals
    property_totals_qs = (
        team_sales
        .values('property_name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )
    top_properties = []
    for row in property_totals_qs:
        name = row['property_name'] or 'Unknown'
        total = float(row['total'] or 0)
        prop_obj = Property.objects.filter(name=name).first()
        if prop_obj:
            prop_obj.total_sales = total
            top_properties.append(prop_obj)
        else:
            top_properties.append(type('Prop', (), {'name': name, 'image': None, 'total_sales': total}))
    
    # Monthly sales trend/breakdown data
    monthly_sales = (
        team_sales
        .annotate(month=TruncMonth('date'))
        .values('month', 'status')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    # Organize monthly data
    month_dict = OrderedDict()
    for entry in monthly_sales:
        month_label = entry['month'].strftime('%b %Y') if entry['month'] else 'Unknown'
        if month_label not in month_dict:
            month_dict[month_label] = {'Active': 0, 'Cancelled': 0}
        month_dict[month_label][entry['status']] = float(entry['total'])

    # Filter out months with no sales
    month_dict = {k: v for k, v in month_dict.items() if v['Active'] > 0 or v['Cancelled'] > 0}
    
    months = list(month_dict.keys())
    monthly_active = [vals['Active'] for vals in month_dict.values()]
    monthly_cancelled = [vals['Cancelled'] for vals in month_dict.values()]

    selected_role = request.GET.get('role', 'Sales Manager')
    filtered_members = [m for m in team_members_with_sales if m['user'].profile.role == selected_role]

    context = {
        'total_sales': total_sales,
        'active_sales': active_sales,
        'cancelled_sales': cancelled_sales,
        'active_percentage': active_percentage,
        'cancelled_percentage': cancelled_percentage,
        'team_members': team_members_with_sales,
        'approved_members_count': approved_members_count,
        'months': months,
        'monthly_active': monthly_active,
        'monthly_cancelled': monthly_cancelled,
        'developers': developers,
        'developer_totals': developer_active,
        'developer_active': developer_active,
        'developer_cancelled': developer_cancelled,
        'properties_json': json.dumps(properties),
        'property_active_json': json.dumps(property_active),
        'property_cancelled_json': json.dumps(property_cancelled),
        'top_developers': top_developers,
        'top_properties': top_properties,
        'months_json': json.dumps(months),
        'monthly_active_json': json.dumps(monthly_active),
        'monthly_cancelled_json': json.dumps(monthly_cancelled),
        'developers_json': json.dumps(developers),
        'developer_active_json': json.dumps(developer_active),
        'developer_cancelled_json': json.dumps(developer_cancelled),
        'is_superuser': request.user.is_superuser,
        'teams': teams,
        'filtered_members': filtered_members[:5],
        'selected_role': selected_role,
        'available_roles': ['Sales Agent', 'Sales Supervisor', 'Sales Manager'],
        'selected_period': period,
        'selected_month': month,
        'selected_year': year,
        'has_data': total_sales > 0,  # Add flag to check if there's any data
        'current_year': timezone.now().year  # Add current year for default filtering
    }
    return render(request, 'dashboard.html', context)



@register.filter
def month_name(month_number):
    try:
        return {
            '1': 'January',
            '2': 'February',
            '3': 'March',
            '4': 'April',
            '5': 'May',
            '6': 'June',
            '7': 'July',
            '8': 'August',
            '9': 'September',
            '10': 'October',
            '11': 'November',
            '12': 'December'
        }[str(month_number)]
    except (KeyError, TypeError):
        return ''

@login_required(login_url='signin')
@login_required(login_url='signin')
def team_dashboard(request, team_name):
    # Get team object
    team = get_object_or_404(Team, name=team_name, is_active=True)
    
    # Get team-specific data
    team_members = Profile.objects.filter(team=team, is_approved=True)
    team_users = User.objects.filter(profile__in=team_members)
    
    # Get filter parameters
    period = request.GET.get('period', 'monthly')  # Default to 'monthly' instead of 'all'
    month = request.GET.get('month')
    year = request.GET.get('year')
    
    # If period is monthly and month/year not specified, use current month/year
    if period == 'monthly' and not (month and year):
        today = timezone.now()
        month = today.month
        year = today.year
        
        # Only redirect if no month/year was provided to avoid infinite redirects
        if not request.GET.get('month') and not request.GET.get('year'):
            return redirect(f"{request.path}?period=monthly&month={month}&year={year}")
    
    # Base query for team sales
    team_sales = Sale.objects.filter(user__in=team_users)
    
    # Apply time period filters
    if period == 'monthly' and month:
        # If year is not specified, use current year
        filter_year = year if year else timezone.now().year
        team_sales = team_sales.filter(
            date__year=filter_year,
            date__month=int(month)
        )
    elif period == 'yearly' and year:
        team_sales = team_sales.filter(date__year=int(year))
    
    # Calculate team sales statistics
    total_sales = team_sales.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    active_sales = team_sales.filter(status='Active').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    cancelled_sales = team_sales.filter(status='Cancelled').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    # Calculate percentages
    active_percentage = (active_sales / total_sales * 100) if total_sales > 0 else 0
    cancelled_percentage = (cancelled_sales / total_sales * 100) if total_sales > 0 else 0
    
    # Get top 5 team members with sales data (filtered by period)
    team_members_data = []
    for member in team_members:
        member_sales = team_sales.filter(user=member.user)
        total_member_sales = member_sales.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        latest_sale = member_sales.order_by('-date').first()
        growth_percentage = 0
        if latest_sale:
            # Sum of all sales before the latest one
            previous_total = member_sales.filter(date__lt=latest_sale.date).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            if previous_total == 0:
                # First sale scenario: +100% for active, -100% for cancelled
                growth_percentage = 100 if latest_sale.status.strip() == 'Active' else -100
            else:
                # Compare the latest sale amount to previous total
                growth_percentage = (latest_sale.amount / previous_total) * 100
                if latest_sale.status.strip() == 'Cancelled':
                    growth_percentage = -growth_percentage
        
        team_members_data.append({
            'user': member.user,
            'total_sales': total_member_sales,
            'latest_sale': latest_sale.amount if latest_sale else 0,
            'growth_percentage': growth_percentage,
            'active_count': member_sales.filter(status='Active').count()
        })
    
    # Sort team members by total sales
    team_members_data.sort(key=lambda x: x['total_sales'], reverse=True)
    
    # Prepare monthly sales data
    monthly_sales = team_sales.annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        active=Sum('amount', filter=Q(status='Active')),
        cancelled=Sum('amount', filter=Q(status='Cancelled'))
    ).order_by('month')  # Changed to chronological order
    
    # Prepare project sales data for the selected period
    project_sales = team_sales.values('property_name').annotate(
        active=Sum('amount', filter=Q(status='Active')),
        cancelled=Sum('amount', filter=Q(status='Cancelled'))
    ).order_by('-active')
    
    # Filter out months with no sales
    monthly_sales = [m for m in monthly_sales if m['active'] or m['cancelled']]

    monthly_data = {
        'labels': [d['month'].strftime('%B %Y') for d in monthly_sales],
        'datasets': [
            {
                'label': 'Active Sales',
                'data': [float(d['active'] or 0) for d in monthly_sales],
                'backgroundColor': '#22c55e'
            },
            {
                'label': 'Cancelled Sales',
                'data': [float(d['cancelled'] or 0) for d in monthly_sales],
                'backgroundColor': '#ef4444'
            }
        ]
    }
    
    # Prepare project sales data for the chart
    project_data = {
        'labels': [p['property_name'] or 'Unspecified' for p in project_sales],
        'datasets': [
            {
                'label': 'Active Sales',
                'data': [float(p['active'] or 0) for p in project_sales],
                'backgroundColor': '#3b82f6',
                'borderColor': '#1d4ed8',
                'borderWidth': 1
            },
            {
                'label': 'Cancelled Sales',
                'data': [float(p['cancelled'] or 0) for p in project_sales],
                'backgroundColor': '#f59e0b',
                'borderColor': '#d97706',
                'borderWidth': 1
            }
        ]
    }
    
    # Prepare developer sales data (filtered by period)
    developer_sales = team_sales.values('developer').annotate(
        active=Sum('amount', filter=Q(status='Active')),
        cancelled=Sum('amount', filter=Q(status='Cancelled'))
    ).order_by('-active')
    
    # Filter out developers with no sales
    developer_sales = [d for d in developer_sales if d['active'] or d['cancelled']]
    
    # Convert developer sales data to lists for the chart
    developers = [d['developer'] for d in developer_sales]
    developer_active = [float(d['active'] or 0) for d in developer_sales]
    developer_cancelled = [float(d['cancelled'] or 0) for d in developer_sales]
    
    context = {
        'team_name': team_name,
        'total_sales': total_sales,
        'active_sales': active_sales,
        'cancelled_sales': cancelled_sales,
        'active_percentage': active_percentage,
        'cancelled_percentage': cancelled_percentage,
        'approved_members_count': team_members.count(),
        'team_members': team_members_data,
        'monthly_data': json.dumps(monthly_data),
        'project_data': json.dumps(project_data),
        'developers_json': json.dumps(developers),
        'developer_active_json': json.dumps(developer_active),
        'developer_cancelled_json': json.dumps(developer_cancelled),
        'selected_period': period,
        'selected_month': month,
        'selected_year': year,
        'has_data': total_sales > 0  # Add flag to check if there's any data
    }
    
    return render(request, 'team_dashboard.html', context)


@login_required(login_url='signin')
def approve_users_list(request):
    if not (request.user.is_superuser or request.user.profile.role == 'Sales Manager'):
        return HttpResponseForbidden("You don't have permission to approve users.")

    if request.user.is_superuser:
        # Superusers can see all users
        unapproved_accounts = Profile.objects.filter(is_approved=False)
        approved_accounts_list = Profile.objects.filter(is_approved=True)
    else:
        # Managers can only see users from their team
        user_team = request.user.profile.team
        unapproved_accounts = Profile.objects.filter(
            is_approved=False,
            role__in=['Sales Supervisor', 'Sales Agent'],
            team=user_team
        )
        approved_accounts_list = Profile.objects.filter(
            is_approved=True,
            role__in=['Sales Supervisor', 'Sales Agent'],
            team=user_team
        )

    # Get all active teams for the team change modal
    active_teams = Team.objects.filter(is_active=True)

    # Pagination for approved accounts
    page = request.GET.get('page', 1)
    paginator = Paginator(approved_accounts_list, 10)  # Show 10 users per page
    try:
        approved_accounts = paginator.page(page)
    except:
        approved_accounts = paginator.page(1)

    return render(request, 'approve.html', {
        'unapproved_accounts': unapproved_accounts,
        'approved_accounts': approved_accounts,
        'teams': active_teams
    })

@login_required
def approve_user(request, profile_id):
    # Get the profile to approve
    profile_to_approve = get_object_or_404(Profile, id=profile_id)
    
    # Check if user has permission to approve
    user_profile = request.user.profile
    can_approve = (
        request.user.is_superuser or  # Superuser can approve anyone
        (user_profile.role == 'Sales Manager' and  # Sales Manager can approve their team members
         user_profile.team == profile_to_approve.team and  # Must be same team
         profile_to_approve.role in ['Sales Agent', 'Sales Supervisor'])  # Can only approve agents and supervisors
    )
    
    if not can_approve:
        messages.error(request, "You don't have permission to approve this user.")
        return redirect('approve')
    
    if request.method == "POST":
        profile_to_approve.is_approved = True
        profile_to_approve.save()
        
        # Send approval email with updated message
        send_approval_email(request, profile_to_approve.user)
        messages.success(request, f'User {profile_to_approve.user.username} has been approved successfully.')
        return redirect('approve')
    else:
        # For GET requests, show a confirmation page
        return render(request, 'confirm_approve.html', {
            'profile': profile_to_approve
        })

@login_required
def reject_user(request, profile_id):
    # Get the profile to reject
    profile_to_reject = get_object_or_404(Profile, id=profile_id)
    
    # Check if user has permission to reject
    user_profile = request.user.profile
    can_reject = (
        request.user.is_superuser or  # Superuser can reject anyone
        (user_profile.role == 'Sales Manager' and  # Sales Manager can reject their team members
         user_profile.team == profile_to_reject.team and  # Must be same team
         profile_to_reject.role in ['Sales Agent', 'Sales Supervisor'])  # Can only reject agents and supervisors
    )
    
    if not can_reject:
        messages.error(request, "You don't have permission to reject this user.")
        return redirect('approve')
    
    # Store the username before deletion for the message
    username = profile_to_reject.user.username
    
    # Delete the user (this will cascade delete the profile as well)
    profile_to_reject.user.delete()
    
    messages.success(request, f"User {username} has been rejected.")
    return redirect('approve')


def commission(request):
    # Add your logic for the commission view here
    return render(request, 'commission.html')

def commission_slip_view(request, slip_id):
    # Fetch the commission slip by ID
    slip = get_object_or_404(CommissionSlip, id=slip_id)
    return render(request, 'commission.html', {'slip': slip})

@login_required(login_url='signin')
def create_commission_slip(request):
    if request.method == 'POST':
        slip_form = CommissionSlipForm(request.POST)
        if slip_form.is_valid():
            slip = slip_form.save(commit=False)
            slip.created_by = request.user
            slip.created_at = timezone.now()
            
            # Get form data
            total_selling_price = Decimal(request.POST.get('total_selling_price', '0'))
            commission_rate = Decimal(request.POST.get('commission_rate', '0'))
            particulars = request.POST.get('particulars[]', 'FULL COMM')
            partial_percentage = Decimal(request.POST.get('partial_percentage', '100'))
            incentive_amount = Decimal(request.POST.get('incentive_amount', '0'))
            cash_advance = Decimal(request.POST.get('cash_advance', '0'))
            withholding_tax_rate = Decimal(request.POST.get('withholding_tax_rate', '10.00'))
            
            # Calculate cash advance tax (10%)
            cash_advance_tax = cash_advance * Decimal('0.10')
            net_cash_advance = cash_advance - cash_advance_tax
            
            # Calculate adjusted total
            adjusted_total = total_selling_price - net_cash_advance
            
            # Calculate base commission
            base_commission = adjusted_total * (commission_rate / 100) 
            
            # Apply partial percentage if applicable
            if particulars == 'PARTIAL COMM':
                base_commission = base_commission * (partial_percentage / 100)
            
            # Calculate gross commission
            gross_commission = base_commission
            if particulars == 'INCENTIVES':
                gross_commission = base_commission + incentive_amount
            
            # Calculate tax
            tax_rate = withholding_tax_rate / 100
            withholding_tax = gross_commission * tax_rate
            net_commission = gross_commission - withholding_tax
            
            # Get sales manager data
            sales_manager_name = request.POST.get('sales_manager_name')
            manager_commission_rate = Decimal(request.POST.get('manager_commission_rate', '0'))

            # Save the slip with all calculated values
            slip.total_selling_price = total_selling_price
            slip.cash_advance = cash_advance
            slip.cash_advance_tax = cash_advance_tax
            slip.incentive_amount = incentive_amount
            slip.withholding_tax_rate = withholding_tax_rate
            slip.sales_manager_name = sales_manager_name
            slip.manager_commission_rate = manager_commission_rate
            slip.save()

            # Create agent commission detail
            CommissionDetail.objects.create(
                slip=slip,
                position=request.POST.get('position[]', 'Sales Agent'),
                particulars=particulars,
                commission_rate=commission_rate,
                base_commission=base_commission,
                gross_commission=gross_commission,
                withholding_tax=withholding_tax,
                net_commission=net_commission,
                agent_name=request.POST.get('sales_agent_name'),
                partial_percentage=partial_percentage,
                withholding_tax_rate=withholding_tax_rate
            )

            # Create manager commission detail if applicable
            if manager_commission_rate > 0 and sales_manager_name:
                manager_base_commission = total_selling_price * (manager_commission_rate / 100)
                if particulars == 'PARTIAL COMM':
                    manager_base_commission = manager_base_commission * (partial_percentage / 100)
                
                manager_gross_commission = manager_base_commission
                manager_withholding_tax = manager_gross_commission * tax_rate
                manager_net_commission = manager_gross_commission - manager_withholding_tax

                CommissionDetail.objects.create(
                    slip=slip,
                    position='Sales Manager',
                    particulars=particulars,
                    commission_rate=manager_commission_rate,
                    base_commission=manager_base_commission,
                    gross_commission=manager_gross_commission,
                    withholding_tax=manager_withholding_tax,
                    net_commission=manager_net_commission,
                    agent_name=sales_manager_name,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=withholding_tax_rate
                )

            messages.success(request, "Commission slip created successfully!")
            return redirect('commission_history')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        slip_form = CommissionSlipForm()

    # Get users based on permissions
    if request.user.is_superuser or request.user.is_staff:
        # Superusers and staff can see all approved users from all teams
        sales_agents = User.objects.filter(
            profile__is_approved=True, profile__role='Sales Agent'
        ).select_related('profile', 'profile__team').order_by('username')
        sales_managers = User.objects.filter(
            profile__is_approved=True, profile__role='Sales Manager'
        ).select_related('profile', 'profile__team').order_by('username')
    else:
        # Regular users can only see their team members
        user_team = request.user.profile.team
        sales_agents = User.objects.filter(
            profile__is_approved=True,
            profile__team=user_team,
            profile__role='Sales Agent'
        ).select_related('profile', 'profile__team').order_by('username')
        sales_managers = User.objects.filter(
            profile__is_approved=True,
            profile__team=user_team,
            profile__role='Sales Manager'
        ).select_related('profile', 'profile__team').order_by('username')

    context = {
        'slip_form': slip_form,
        'sales_agents': sales_agents,
        'sales_managers': sales_managers,
        'user_is_staff': request.user.is_staff,
        'user_is_superuser': request.user.is_superuser
    }
    return render(request, 'create_commission_slip.html', context)

def commission_history(request):
    if not request.user.is_authenticated:
        return redirect('signin')

    # Get search parameters
    search_agent = request.GET.get('search_agent', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    # Query CommissionSlip
    commission_slips = CommissionSlip.objects.all().order_by('-date')
    # Query CommissionSlip3
    commission_slips3 = CommissionSlip3.objects.all().order_by('-date')

    # Apply filters to both
    if search_agent:
        commission_slips = commission_slips.filter(
            Q(sales_agent_name__icontains=search_agent) |
            Q(buyer_name__icontains=search_agent) |
            Q(project_name__icontains=search_agent)
        )
        commission_slips3 = commission_slips3.filter(
            Q(sales_agent_name__icontains=search_agent) |
            Q(supervisor_name__icontains=search_agent) |
            Q(buyer_name__icontains=search_agent) |
            Q(project_name__icontains=search_agent)
        )

    if start_date:
        commission_slips = commission_slips.filter(date__gte=start_date)
        commission_slips3 = commission_slips3.filter(date__gte=start_date)
    if end_date:
        commission_slips = commission_slips.filter(date__lte=end_date)
        commission_slips3 = commission_slips3.filter(date__lte=end_date)

    # Filter based on user role and permissions
    if request.user.is_superuser or request.user.is_staff:
        # Superusers and staff can see all commission slips
        pass
    elif request.user.profile.role == 'Sales Manager':
        # Sales Managers can see their team's slips and slips they created
        user_team = request.user.profile.team
        commission_slips = commission_slips.filter(
            Q(created_by=request.user) |
            Q(sales_agent_name=request.user.get_full_name()) |
            Q(created_by__profile__team=user_team)
        )
        commission_slips3 = commission_slips3.filter(
            Q(created_by=request.user) |
            Q(sales_agent_name=request.user.get_full_name()) |
            Q(supervisor_name=request.user.get_full_name()) |
            Q(created_by__profile__team=user_team)
        )
    else:
        # Regular users can only see their own commission slips
        commission_slips = commission_slips.filter(
            Q(sales_agent_name=request.user.get_full_name()) |
            Q(created_by=request.user)
        )
        commission_slips3 = commission_slips3.filter(
            Q(sales_agent_name=request.user.get_full_name()) |
            Q(supervisor_name=request.user.get_full_name()) |
            Q(created_by=request.user)
        )

    # Initialize all commission variables
    total_gross_commission = 0
    sales_agents_commission = 0
    supervisors_commission = 0
    managers_commission = 0
    team_leader_commission = 0
    operations_commission = 0
    cofounder_commission = 0
    founder_commission = 0
    funds_commission = 0
    user_commission = 0  # For regular users
    sales_team_total = 0  # For total breakdown
    management_team_total = 0  # For total breakdown
    
    # Get commission details based on user permissions
    if request.user.is_superuser or request.user.is_staff:
        # For superusers and staff, show all commissions
        commission_details = CommissionDetail.objects.all()
        commission_details3 = CommissionDetail3.objects.all()
        
        # Calculate role-based commissions from CommissionDetail
        sales_agents_commission = commission_details.filter(
            position='Sales Agent'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        supervisors_commission = commission_details.filter(
            position='Sales Supervisor'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        managers_commission = commission_details.filter(
            position='Sales Manager'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0

        team_leader_commission = commission_details.filter(
            position='Team Leader'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        operations_commission = commission_details.filter(
            position='Operation Manager'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        cofounder_commission = commission_details.filter(
            position='Co-Founder'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        founder_commission = commission_details.filter(
            position='Founder'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        funds_commission = commission_details.filter(
            position='Funds'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        # Add commissions from CommissionDetail3
        sales_agents_commission += commission_details3.filter(
            position='Sales Agent'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0
        
        supervisors_commission += commission_details3.filter(
            position='Sales Supervisor'
        ).aggregate(total=models.Sum('gross_commission'))['total'] or 0

        # Calculate team totals
        sales_team_total = sales_agents_commission + supervisors_commission + managers_commission
        management_team_total = team_leader_commission + operations_commission + cofounder_commission + founder_commission + funds_commission
        
        # Calculate grand total (sum of both team totals)
        total_gross_commission = sales_team_total + management_team_total
        
    else:
        # For regular users, only show their commissions
        # Get commission details where they are specifically mentioned
        commission_details = CommissionDetail.objects.filter(
            Q(slip__sales_agent_name=request.user.get_full_name()) &
            Q(position=request.user.profile.role)  # Only get their specific role's commission
        )
        commission_details3 = CommissionDetail3.objects.filter(
            (Q(slip__sales_agent_name=request.user.get_full_name()) & Q(position='Sales Agent')) |
            (Q(slip__supervisor_name=request.user.get_full_name()) & Q(position='Sales Supervisor'))
        )
        
        # Calculate user's total commission from their specific role's commission
        user_commission = (
            commission_details.aggregate(total=models.Sum('gross_commission'))['total'] or 0
        ) + (
            commission_details3.aggregate(total=models.Sum('gross_commission'))['total'] or 0
        )
        total_gross_commission = user_commission

    # Count commission types
    regular_commission_count = commission_slips.filter(is_full_breakdown=False).count()
    management_commission_count = commission_slips.filter(is_full_breakdown=True).count()
    supervisor_agent_commission_count = commission_slips3.count()

    # Create a list of all slips with their type
    all_slips = []
    
    # Add regular commission slips
    for slip in commission_slips:
        slip.slip_type = 'regular'
        all_slips.append(slip)
    
    # Add supervisor-agent commission slips
    for slip in commission_slips3:
        slip.slip_type = 'supervisor_agent'
        all_slips.append(slip)

    # Sort all slips by date (descending)
    all_slips.sort(key=lambda slip: slip.date if slip.date else slip.created_at, reverse=True)

    # Paginate merged slips
    page = request.GET.get('page', 1)
    paginator = Paginator(all_slips, 10)  # Show 10 slips per page
    try:
        paginated_slips = paginator.page(page)
    except:
        paginated_slips = paginator.page(1)

    # Get all active users for team information
    team_members = User.objects.filter(is_active=True).select_related('profile')

    # Attach details and agent_role for each slip
    for slip in paginated_slips:
        if slip.slip_type == 'supervisor_agent':  # CommissionSlip3
            setattr(slip, 'custom_details', CommissionDetail3.objects.filter(slip=slip))
            # For agent role, use the agent's role if possible
            slip.agent_role = 'Sales Agent'
        else:  # CommissionSlip
            setattr(slip, 'custom_details', CommissionDetail.objects.filter(slip=slip))
            detail = slip.custom_details.first()
            if detail:
                slip.agent_role = detail.position
            else:
                # Try to find the user by their full name
                name_parts = slip.sales_agent_name.split()
                agent = User.objects.filter(
                    Q(first_name__in=name_parts) & Q(last_name__in=name_parts)
                ).first()
                if agent and hasattr(agent, 'profile'):
                    slip.agent_role = agent.profile.role
                else:
                    slip.agent_role = "Unknown Role"

    context = {
        'commission_slips': paginated_slips,
        'search_agent': search_agent,
        'start_date': start_date,
        'end_date': end_date,
        'is_superuser': request.user.is_superuser,
        'regular_commission_count': regular_commission_count,
        'management_commission_count': management_commission_count,
        'supervisor_agent_commission_count': supervisor_agent_commission_count,
        'team_members': team_members,
        'total_gross_commission': total_gross_commission,
        # Role-based commission totals
        'sales_agents_commission': sales_agents_commission,
        'supervisors_commission': supervisors_commission,
        'managers_commission': managers_commission,
        'team_leader_commission': team_leader_commission,
        'operations_commission': operations_commission,
        'cofounder_commission': cofounder_commission,
        'founder_commission': founder_commission,
        'funds_commission': funds_commission,
        # Team totals
        'sales_team_total': sales_team_total,
        'management_team_total': management_team_total,
        # User-specific commission
        'user_commission': user_commission,
    }
    return render(request, 'commission_history.html', context)

def commission_view(request, slip_id=None):
    if not request.user.is_authenticated:
        return redirect('signin')

    if slip_id:
        slip = get_object_or_404(CommissionSlip, id=slip_id)
        
        # For superusers, allow viewing all commission slips
        if request.user.is_superuser:
            details = CommissionDetail.objects.filter(slip=slip)
            all_slips = CommissionSlip.objects.all().order_by('-id')

            # Calculate totals
            total_gross = sum(detail.gross_commission for detail in details)
            total_tax = sum(detail.withholding_tax for detail in details)
            total_net = sum(detail.net_commission for detail in details)

            return render(request, 'commission.html', {
                'slip': slip,
                'details': details,
                'total_gross': total_gross,
                'total_tax': total_tax,
                'total_net': total_net,
                'all_slips': all_slips,
                'viewing_as_creator': True
            })

        # For regular agents, supervisors, and managers
        if request.user.profile.role in ['Sales Agent', 'Sales Supervisor', 'Sales Manager']:
            # Check if the user is the creator or the slip belongs to them
            is_creator = slip.created_by == request.user
            is_agent = slip.sales_agent_name == request.user.get_full_name()
            
            if not (is_creator or is_agent):
                messages.error(request, 'You do not have permission to view this slip.')
                return redirect('commission_history')
            
            # Get all details for this slip
            details = CommissionDetail.objects.filter(slip=slip)
            
            # If viewing as creator (manager/supervisor), show agent's details
            if is_creator and not is_agent:
                # Filter details to show only those matching the sales agent's position
                agent_details = details.filter(agent_name=slip.sales_agent_name)
                if agent_details.exists():
                    details = agent_details
            else:
                # Show their own commission details when viewing as agent
                details = details.filter(position=request.user.profile.role)
            
            if not details.exists():
                messages.error(request, 'No commission details found.')
                return redirect('commission_history')

            # Calculate totals only for visible details
            total_gross = sum(detail.gross_commission for detail in details)
            total_tax = sum(detail.withholding_tax for detail in details)
            total_net = sum(detail.net_commission for detail in details)

            # Get all slips for the current user (either created or assigned)
            all_slips = CommissionSlip.objects.filter(
                Q(created_by=request.user) | Q(sales_agent_name=request.user.get_full_name())
            ).order_by('-id')

            return render(request, 'commission.html', {
                'slip': slip,
                'details': details,
                'total_gross': total_gross,
                'total_tax': total_tax,
                'total_net': total_net,
                'all_slips': all_slips,
                'viewing_as_creator': is_creator and not is_agent
            })
        else:
            messages.error(request, 'You do not have permission to view commission slips.')
            return redirect('commission_history')
    
    return redirect('commission_history')



def commission2(request, slip_id):
    if not request.user.is_authenticated:
        return redirect('signin')

    slip = get_object_or_404(CommissionSlip, id=slip_id)
    
    # Check if user has permission to view this commission2 slip
    can_view = (
        request.user.is_superuser or
        request.user.is_staff or  # Add staff permission
        slip.created_by == request.user or
        slip.sales_agent_name == request.user.get_full_name()
    )

    if not can_view:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('home')

    # Only show all details to superuser/staff, otherwise filter to user's own commission
    if request.user.is_superuser or request.user.is_staff:
        details = CommissionDetail.objects.filter(slip=slip)
    else:
        # Only show the detail for the user's role and name
        details = CommissionDetail.objects.filter(
            slip=slip,
            position=request.user.profile.role,
            agent_name=request.user.get_full_name()
        )

    # Get slips based on user role
    if request.user.is_superuser:
        # Superusers can see all slips
        all_slips = CommissionSlip.objects.all().order_by('-id')
    elif request.user.is_staff:
        # Staff can see all slips they created or where they are the agent
        all_slips = CommissionSlip.objects.filter(
            Q(created_by=request.user) | 
            Q(sales_agent_name=request.user.get_full_name())
        ).order_by('-id')
    else:
        # Others can only see their own slips
        all_slips = CommissionSlip.objects.filter(
            sales_agent_name=request.user.get_full_name()
        ).order_by('-id')

    # Calculate totals
    total_gross = sum(detail.gross_commission for detail in details)
    total_tax = sum(detail.withholding_tax for detail in details)
    total_net = sum(detail.net_commission for detail in details)

    return render(request, "commission2.html", {
        "slip": slip,
        "details": details,
        "total_gross": total_gross,
        "total_tax": total_tax,
        "total_net": total_net,
        "all_slips": all_slips,
    })

def commission_slip_view(request, slip_id):
    # Fetch the commission slip by ID
    slip = get_object_or_404(CommissionSlip, id=slip_id)
    return render(request, 'commission2.html', {'slip': slip})

@login_required(login_url='signin')
def create_commission_slip2(request):
    # Check if user has permission (only staff and superuser)
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You don't have permission to create commission slips.")
        return redirect('commission_history')

    if request.method == 'POST':
        slip_form = CommissionSlipForm(request.POST)
        if slip_form.is_valid():
            # Get form data
            sales_agent_name = request.POST.get('sales_agent_name')
            buyer_name = request.POST.get('buyer_name')
            project_name = request.POST.get('project_name')
            unit_id = request.POST.get('unit_id')
            total_selling_price = Decimal(request.POST.get('total_selling_price_manager', '0'))
            cash_advance = Decimal(request.POST.get('cash_advance', '0'))
            date = request.POST.get('date')
            withholding_tax_rate = Decimal(request.POST.get('withholding_tax_rate', '10.00'))
            team_leader_tax_rate = Decimal(request.POST.get('team_leader_tax_rate') or 0)
            operation_manager_tax_rate = Decimal(request.POST.get('operation_manager_tax_rate') or 0)
            co_founder_tax_rate = Decimal(request.POST.get('co_founder_tax_rate') or 0)
            founder_tax_rate = Decimal(request.POST.get('founder_tax_rate') or 0)
            funds_tax_rate = Decimal(request.POST.get('funds_tax_rate') or 0)
            particulars = request.POST.get('particulars', 'FULL COMM')
            partial_percentage = Decimal(request.POST.get('partial_percentage', '100'))

            # Get commission rates for each position
            commission_rates = request.POST.getlist('commission_rate[]')
            positions = request.POST.getlist('position[]')
            gross_commissions = request.POST.getlist('gross_commission[]')
            withholding_taxes = request.POST.getlist('withholding_tax[]')
            net_commissions = request.POST.getlist('net_commission[]')

            # Create commission slip with is_full_breakdown set to True
            slip = CommissionSlip.objects.create(
                sales_agent_name=sales_agent_name,
                buyer_name=buyer_name,
                project_name=project_name,
                unit_id=unit_id,
                total_selling_price=total_selling_price,
                cash_advance=cash_advance,
                date=date,
                withholding_tax_rate=withholding_tax_rate,
                team_leader_tax_rate=team_leader_tax_rate,
                operation_manager_tax_rate=operation_manager_tax_rate,
                co_founder_tax_rate=co_founder_tax_rate,
                founder_tax_rate=founder_tax_rate,
                created_by=request.user,
                created_at=timezone.now(),
                is_full_breakdown=True  # Set this to True for management commission
            )
                    
            # Create commission details for each position
            for idx, position in enumerate(positions):
                # Safely get the matching values; default to 0 if the list is shorter
                rate_str = commission_rates[idx] if idx < len(commission_rates) else ''
                rate = Decimal(rate_str) if rate_str else 0
                if rate == 0:
                    # Skip positions with zero/blank rate but keep index alignment
                    continue
                # Use a separate pointer for financial arrays since they only exist for rows with rate>0
                if 'fin_ptr' not in locals():
                    fin_ptr = 0
                
                gross = Decimal(gross_commissions[fin_ptr]) if fin_ptr < len(gross_commissions) and gross_commissions[fin_ptr] else Decimal('0')
                wt = Decimal(withholding_taxes[fin_ptr]) if fin_ptr < len(withholding_taxes) and withholding_taxes[fin_ptr] else Decimal('0')
                net = Decimal(net_commissions[fin_ptr]) if fin_ptr < len(net_commissions) and net_commissions[fin_ptr] else Decimal('0')

                # Determine the correct tax rate for this position
                applied_tax_rate = (
                    withholding_tax_rate if position == 'Sales Agent' else
                    team_leader_tax_rate if position == 'Team Leader' else
                    operation_manager_tax_rate if position == 'Operation Manager' else
                    co_founder_tax_rate if position == 'Co-Founder' else
                    founder_tax_rate if position == 'Founder' else
                    funds_tax_rate if position == 'Funds' else Decimal('0')
                )

                # If the frontend didn't send calculated amounts (e.g., Funds row), compute them here
                if gross == 0:
                    # Recreate adjusted total used in JS preview
                    net_cash_advance = cash_advance - (cash_advance * Decimal('0.10'))
                    adjusted_total = total_selling_price - net_cash_advance
                    
                    # Calculate base commission
                    base_commission = adjusted_total * (rate) * (partial_percentage / 100)
                    
                    # Apply partial percentage if applicable
                    if particulars == 'PARTIAL COMM':
                        base_commission = base_commission * (partial_percentage / 100)
                    
                    # Calculate gross commission
                    gross = base_commission
                    if particulars == 'INCENTIVES':
                        gross = base_commission + Decimal(request.POST.get('incentive_amount', '0'))
                    
                    # Calculate tax
                    tax_rate = applied_tax_rate / 100
                    withholding_tax = gross * tax_rate
                    net = gross - withholding_tax

                # Advance financial pointer since we've consumed this set
                fin_ptr += 1

                # Round values to 2 decimal places for storage consistency
                gross = gross.quantize(Decimal('0.01'))
                wt = wt.quantize(Decimal('0.01'))
                net = net.quantize(Decimal('0.01'))

                CommissionDetail.objects.create(
                    slip=slip,
                    position=position,
                    particulars=particulars,
                    commission_rate=rate,
                    gross_commission=gross,
                    withholding_tax=wt,
                    net_commission=net,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=applied_tax_rate
                )

            messages.success(request, "Commission slip created successfully!")
            return redirect('commission_history')
    else:
        slip_form = CommissionSlipForm()

    context = {
        'slip_form': slip_form,
        'active_users': User.objects.filter(profile__is_approved=True)
    }
    return render(request, 'create_commission_slip2.html', context)




def commission_view2(request, slip_id):
    if not request.user.is_authenticated:
        return redirect('signin')

    # Check if user has permission to view commission slip 2
    if not (request.user.is_superuser or request.user.profile.role in ['Sales Manager', 'Sales Supervisor']):
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('home')

    slip = get_object_or_404(CommissionSlip, id=slip_id)
    details = CommissionDetail.objects.filter(slip=slip)

    # Get slips based on user role
    if request.user.is_superuser:
        # Superusers can see all slips
        all_slips = CommissionSlip.objects.all().order_by('-id')
    elif request.user.profile.role == 'Sales Manager':
        # Managers can see their team's slips
        all_slips = CommissionSlip.objects.filter(
            Q(created_by=request.user) | 
            Q(sales_agent_name=request.user.get_full_name())
        ).order_by('-id')
    else:
        # Supervisors can only see their own slips
        all_slips = CommissionSlip.objects.filter(
            sales_agent_name=request.user.get_full_name()
        ).order_by('-id')

    total_gross = sum(detail.gross_commission for detail in details)
    total_tax = sum(detail.withholding_tax for detail in details)
    total_net = sum(detail.net_commission for detail in details)

    return render(request, "commission2.html", {
        "slip": slip,
        "details": details,
        "total_gross": total_gross,
        "total_tax": total_tax,
        "total_net": total_net,
        "all_slips": all_slips,
    })

def edit_commission_slip(request, slip_id):
    slip = get_object_or_404(CommissionSlip, id=slip_id)

    if request.method == "POST":
        # Update Commission Slip fields
        slip.sales_agent_name = request.POST.get("sales_agent_name")
        slip.buyer_name = request.POST.get("buyer_name")
        slip.project_name = request.POST.get("project_name")
        slip.unit_id = request.POST.get("unit_id")
        slip.total_selling_price = float(request.POST.get("total_selling_price") or 0)
        slip.commission_rate = float(request.POST.get("commission_rate") or 0)
        slip.save()

        # Loop through each detail
        for detail in CommissionDetail.objects.filter(slip=slip):
            commission_rate_str = request.POST.get(f"commission_rate_{detail.id}")
            if commission_rate_str is not None:
                detail.commission_rate = float(commission_rate_str)

            particulars_val = request.POST.get(f"particulars_{detail.id}")
            if particulars_val is not None:
                detail.particulars = particulars_val

            is_incentive = detail.particulars == "INCENTIVES" and detail.position == "dynamic_position"

            if is_incentive:
                # Preserve incentive amount and compute from it
                incentive_amount = request.POST.get(f"incentive_amount_{detail.id}")
                if incentive_amount:
                    detail.incentive_amount = float(incentive_amount)
                else:
                    detail.incentive_amount = 0

                detail.gross_commission = detail.incentive_amount
            else:
                # Recompute for regular items
                detail.incentive_amount = 0
                detail.gross_commission = slip.total_selling_price * (detail.commission_rate / 100)

            # Always recalculate tax and net commission
            detail.withholding_tax = detail.gross_commission * 0.10
            detail.net_commission = detail.gross_commission - detail.withholding_tax

            detail.save()

        return redirect('commission2', slip_id=slip.id)

    # For GET request, load the form
    details = CommissionDetail.objects.filter(slip=slip)
    total_gross = sum(d.gross_commission for d in details)
    total_tax = sum(d.withholding_tax for d in details)
    total_net = sum(d.net_commission for d in details)
    all_slips = CommissionSlip.objects.order_by('-id')

    return render(request, "commission2.html", {
        "slip": slip,
        "details": details,
        "total_gross": total_gross,
        "total_tax": total_tax,
        "total_net": total_net,
        "all_slips": all_slips,
        "edit_mode": True,
    })


@login_required(login_url='signin')
def delete_commission_slip(request, slip_id):
    # Try to get the commission slip from all possible models
    slip = None
    for model in [CommissionSlip, CommissionSlip3]:
        try:
            slip = model.objects.get(id=slip_id)
            break
        except model.DoesNotExist:
            continue
    
    if not slip:
        messages.error(request, 'Commission slip not found.')
        return redirect('commission_history')
    
    # Check if user has permission to delete the slip
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'You do not have permission to delete commission slips.')
        return redirect('commission_history')
    
    if request.method == "POST":
        try:
            # Delete associated commission details first
            if hasattr(slip, 'details'):
                slip.details.all().delete()
            
            # Delete associated commission records
            Commission.objects.filter(
                project_name=slip.project_name,
                buyer=slip.buyer_name
            ).delete()
            
            # Delete the commission slip
            slip.delete()
            messages.success(request, 'Commission slip deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting commission slip: {str(e)}')
        
    return redirect('commission_history')







@login_required(login_url='signin')
def tranches_view(request):
    # Check if user has permission
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')

    # Get all approved users
    approved_users = User.objects.filter(
        profile__is_approved=True,
        profile__role__in=['Sales Agent', 'Sales Supervisor', 'Sales Manager']
    ).select_related('profile')

    if request.method == 'POST':
        form = CommissionForm(request.POST)
        if form.is_valid():
            try:
                # Compute Net of VAT based on Total Contract Price and VAT rate
                vat_rate_decimal = form.cleaned_data.get('vat_rate', Decimal(12)) / Decimal(100)
                net_of_vat_base = form.cleaned_data['total_contract_price'] / (Decimal(1) + vat_rate_decimal)

                # Create TrancheRecord
                tranche_record = TrancheRecord.objects.create(
                    project_name=form.cleaned_data['project_name'],
                    agent_name=form.cleaned_data['agent_name'].get_full_name(),
                    phase=form.cleaned_data['phase'],
                    unit_id=form.cleaned_data['unit_id'],
                    buyer_name=form.cleaned_data['buyer_name'],
                    reservation_date=form.cleaned_data['reservation_date'],
                    total_contract_price=form.cleaned_data['total_contract_price'],
                    commission_rate=form.cleaned_data['commission_rate'],
                    process_fee_percentage=form.cleaned_data.get('process_fee_percentage', 0),
                    withholding_tax_rate=form.cleaned_data['withholding_tax_rate'],
                    option1_percentage=form.cleaned_data['option1_percentage'],
                    option2_percentage=form.cleaned_data['option2_percentage'],
                    option1_tax_rate=form.cleaned_data['option1_tax_rate'],
                    option2_tax_rate=form.cleaned_data['option2_tax_rate'],
                    tranche_option=form.cleaned_data['tranche_option'],
                    number_months=form.cleaned_data['number_months'],
                    deduction_type=form.cleaned_data.get('deduction_type'),
                    other_deductions=form.cleaned_data.get('other_deductions', 0),
                    # Store computed Net of VAT in the record so it can be displayed later
                    net_of_vat_amount=net_of_vat_base,
                    vat_rate=form.cleaned_data['vat_rate'],
                    deduction_tax_rate=form.cleaned_data.get('deduction_tax_rate', 10),
                    created_by=request.user
                )
                print("Created TrancheRecord:", tranche_record.id)

                # Calculate base values using the new Net of VAT computation (TCP / (1+VAT))
                less_process_fee = (form.cleaned_data['total_contract_price'] * form.cleaned_data.get('process_fee_percentage', 0)) / Decimal(100)
                net_of_vat_amount = net_of_vat_base
                total_selling_price = net_of_vat_base - less_process_fee
                tax_rate = form.cleaned_data['withholding_tax_rate'] / Decimal(100)
                gross_commission = total_selling_price * (form.cleaned_data['commission_rate'] / Decimal(100))

                # Incorporate VAT (default 12%) before withholding tax
                vat_rate_decimal = form.cleaned_data.get('vat_rate', Decimal(12)) / Decimal(100)
                vat_amount = gross_commission * vat_rate_decimal
                net_of_vat = gross_commission / (Decimal(1) + vat_rate_decimal)

                tax = net_of_vat * tax_rate
                net_commission = gross_commission - tax

                print("Base calculations completed")

                # Calculate tax rates for different components
                option1_tax_rate = form.cleaned_data['option1_tax_rate'] / Decimal(100)
                option2_tax_rate = form.cleaned_data['option2_tax_rate'] / Decimal(100)
                deduction_tax_rate = form.cleaned_data.get('deduction_tax_rate', Decimal(10)) / Decimal(100)

                print("Tax rates calculated:", {
                    "option1_tax_rate": option1_tax_rate,
                    "option2_tax_rate": option2_tax_rate,
                    "deduction_tax_rate": deduction_tax_rate
                })

                # Calculate deductions
                deduction_amount = form.cleaned_data.get('other_deductions', Decimal(0))
                deduction_tax = deduction_amount * deduction_tax_rate
                deduction_net = deduction_amount - deduction_tax

                print("Deductions calculated:", {
                    "amount": deduction_amount,
                    "tax": deduction_tax,
                    "net": deduction_net
                })

                # Calculate commission splits
                total_commission = net_commission
                option1_value_before_deduction = total_commission * (form.cleaned_data['option1_percentage'] / Decimal(100))
                option2_value = total_commission * (form.cleaned_data['option2_percentage'] / Decimal(100))

                # Apply deductions to option1_value (DP period)
                option1_value = option1_value_before_deduction - deduction_net
                option1_monthly = option1_value / Decimal(form.cleaned_data['number_months'])

                print("Commission splits calculated:", {
                    "option1_before_deduction": option1_value_before_deduction,
                    "option1_after_deduction": option1_value,
                    "option2_value": option2_value,
                    "monthly_value": option1_monthly
                })

                # Create payment schedule
                intervals = []
                current_date = form.cleaned_data['reservation_date']
                for i in range(form.cleaned_data['number_months']):
                    if form.cleaned_data['tranche_option'] == "bi_monthly":
                        current_date += timedelta(days=30)
                    elif form.cleaned_data['tranche_option'] == "quarterly":
                        current_date += timedelta(days=90)
                    elif form.cleaned_data['tranche_option'] == "bi_6_months":
                        current_date += timedelta(days=180)
                    elif form.cleaned_data['tranche_option'] == "bi_9_months":
                        current_date += timedelta(days=270)
                    else:
                        current_date += timedelta(days=30)
                    intervals.append(current_date)

                print(f"Created {len(intervals)} payment intervals")

                # Create DP tranches
                dp_tranches = []
                total_net = Decimal('0')
                total_dp_tax = Decimal('0')

                # Calculate totals first
                for i, date in enumerate(intervals, start=1):
                    net = option1_monthly
                    tax_amount = net * option1_tax_rate
                    total_net += net
                    total_dp_tax += tax_amount

                total_expected_commission = total_net - total_dp_tax
                remaining_balance = total_expected_commission

                print("DP period totals calculated:", {
                    "total_net": total_net,
                    "total_tax": total_dp_tax,
                    "expected_commission": total_expected_commission
                })

                # Create individual tranches
                for i, date in enumerate(intervals, start=1):
                    net = option1_monthly
                    tax_amount = net * option1_tax_rate
                    expected_commission = net - tax_amount
                    commission_received = Decimal(request.POST.get(f"commission_received_{i}", 0) or 0)
                    date_received = request.POST.get(f"date_received_{i}")

                    remaining_balance = remaining_balance - commission_received

                    tranche = TranchePayment.objects.create(
                        tranche_record=tranche_record,
                        tranche_number=i,
                        expected_date=date,
                        expected_amount=expected_commission,
                        received_amount=commission_received,
                        date_received=date_received if date_received else None,
                        is_lto=False,
                        initial_balance=total_expected_commission,
                        status="Received" if commission_received >= expected_commission else
                               "Partial" if commission_received > 0 else "On Process"
                    )
                    dp_tranches.append({
                        'tranche': tranche,
                        'tax_amount': tax_amount,
                        'net_amount': net,
                        'balance': remaining_balance,
                        'initial_balance': total_expected_commission,
                        'expected_commission': expected_commission
                    })

                print(f"Created {len(dp_tranches)} DP tranches")

                # Calculate LTO values
                total_commission_received = sum(t['tranche'].received_amount for t in dp_tranches)
                total_commission1 = total_expected_commission

                lto_deduction_value = option2_value
                lto_deduction_tax = lto_deduction_value * option2_tax_rate
                lto_deduction_net = lto_deduction_value - lto_deduction_tax
                lto_expected_commission = lto_deduction_net - lto_deduction_tax

                print("LTO calculations:", {
                    "deduction_value": lto_deduction_value,
                    "tax": lto_deduction_tax,
                    "net": lto_deduction_net,
                    "expected_commission": lto_expected_commission
                })

                # Create LTO tranche
                schedule2_gap_months = int(request.POST.get("schedule2_gap_months", 1))
                schedule2_start_date = intervals[-1] + timedelta(days=30 * schedule2_gap_months)

                commission_received2 = Decimal(request.POST.get("commission_received2_1", 0) or 0)
                date_received2 = request.POST.get("date_received2_1")

                lto_current_balance = lto_expected_commission - commission_received2

                lto_tranche = TranchePayment.objects.create(
                    tranche_record=tranche_record,
                    tranche_number=1,
                    expected_date=schedule2_start_date,
                    expected_amount=lto_expected_commission,
                    received_amount=commission_received2,
                    date_received=date_received2 if date_received2 else None,
                    is_lto=True,
                    initial_balance=lto_expected_commission,
                    status="Received" if commission_received2 >= lto_expected_commission else
                           "Partial" if commission_received2 > 0 else "On Process"
                )

                print("Created LTO tranche")

                lto_tranches = [{
                    'tranche': lto_tranche,
                    'tax_amount': lto_deduction_tax,
                    'net_amount': lto_deduction_net,
                    'expected_commission': lto_expected_commission,
                    'balance': lto_current_balance,
                    'initial_balance': lto_expected_commission
                }]

                # Calculate final totals
                total_commission2 = sum(t['tranche'].expected_amount for t in lto_tranches)
                total_commission_received2 = sum(t['tranche'].received_amount for t in lto_tranches)
                total_balance2 = total_commission2 - total_commission_received2
                percentage_received2 = (total_commission_received2 / total_commission2 * 100) if total_commission2 > 0 else 0
                percentage_remaining2 = 100 - percentage_received2

                total_dp_tax = sum(t['tax_amount'] for t in dp_tranches)

                # Calculate total tax for LTO tranche so it can be included in the context
                total_lto_tax = lto_deduction_tax

                print("Final calculations completed")

                # Prepare context with all calculated values
                context = {
                    "form": form,
                    "approved_users": approved_users,
                    "project_name": form.cleaned_data['project_name'],
                    "agent_name": form.cleaned_data['agent_name'].get_full_name(),
                    "phase": form.cleaned_data['phase'],
                    "unit_id": form.cleaned_data['unit_id'],
                    "buyer_name": form.cleaned_data['buyer_name'],
                    "reservation_date": form.cleaned_data['reservation_date'],
                    "total_contract_price": form.cleaned_data['total_contract_price'],
                    "less_process_fee": less_process_fee,
                    "total_selling_price": total_selling_price,
                    "commission_rate": form.cleaned_data['commission_rate'],
                    "gross_commission": gross_commission,
                    "vat_rate": tranche_record.vat_rate,
                    "net_of_vat": net_of_vat,
                    "vat_amount": vat_amount,
                    "tax": tax_rate * 100,
                    "tax_rate": tax,
                    "net_commission": net_commission,
                    "dp_tranches": dp_tranches,
                    "lto_tranches": lto_tranches,
                    "option1_value": option1_value,
                    "option1_value_before_deduction": option1_value_before_deduction,
                    "option2_value": option2_value,
                    "option1_percentage": form.cleaned_data['option1_percentage'],
                    "option2_percentage": form.cleaned_data['option2_percentage'],
                    "option1_tax_rate": option1_tax_rate,
                    "option2_tax_rate": option2_tax_rate,
                    "tranche_option": form.cleaned_data['tranche_option'],
                    "number_months": form.cleaned_data['number_months'],
                    "process_fee_percentage": form.cleaned_data.get('process_fee_percentage', Decimal(0)),
                    "withholding_tax_rate": form.cleaned_data['withholding_tax_rate'],
                    "option1_monthly": option1_monthly,
                    "total_commission1": total_commission1,
                    "total_commission_received": total_commission_received,
                    "total_balance": total_commission1 - total_commission_received,
                    "percentage_received": (total_commission_received / total_commission1 * 100) if total_commission1 > 0 else 0,
                    "percentage_remaining": 100 - (total_commission_received / total_commission1 * 100) if total_commission1 > 0 else 0,
                    "other_deductions": form.cleaned_data.get('other_deductions', Decimal(0)),
                    "deduction_type": form.cleaned_data.get('deduction_type'),
                    "deduction_tax": deduction_tax,
                    "deduction_net": deduction_net,
                    "deductions": option1_value,
                    "deduction_tax_rate": deduction_tax_rate * 100,
                    "schedule2_start_date": schedule2_start_date,
                    "schedule2_gap_months": schedule2_gap_months,
                    "total_commission2": total_commission2,
                    "total_commission_received2": total_commission_received2,
                    "total_balance2": total_balance2,
                    "percentage_received2": percentage_received2,
                    "percentage_remaining2": percentage_remaining2,
                    "total_dp_tax": total_dp_tax,
                    "total_lto_tax": total_lto_tax,
                    "lto_deduction_value": lto_deduction_value,
                    "lto_deduction_tax": lto_deduction_tax,
                    "lto_deduction_net": lto_deduction_net,
                }

                messages.success(request, 'Tranche record created successfully!')
                # Redirect to the tranche details page so the user can immediately review the generated report
                return redirect(reverse('view_tranche', args=[tranche_record.id]))

            except Exception as e:
                print("Error creating tranche record:", str(e))
                messages.error(request, f"Error creating tranche record: {str(e)}")
                return render(request, "tranches.html", {"form": form, "approved_users": approved_users})

    form = CommissionForm()
    context = {
        "form": form,
        "approved_users": approved_users,
        "option1_tax_rate": Decimal("0.10"),
        "option2_tax_rate": Decimal("0.10"),
        "option1_value": Decimal("0"),
        "option2_value": Decimal("0")
    }
    return render(request, "tranches.html", context)

@login_required(login_url='signin')
def add_sale(request):
    if request.method == 'POST':
        try:
            property_name = request.POST.get('property')
            developer = request.POST.get('developer')
            amount = request.POST.get('amount')
            status = request.POST.get('status')
            date = request.POST.get('date')

            # Validate that property and developer exist in our database
            if not Property.objects.filter(name=property_name).exists():
                messages.error(request, 'Selected property does not exist.')
                return redirect('profile')
                
            if not Developer.objects.filter(name=developer).exists():
                messages.error(request, 'Selected developer does not exist.')
                return redirect('profile')

            if all([property_name, developer, amount, status, date]):
                # Create the sale
                sale = Sale.objects.create(
                    user=request.user,
                    property_name=property_name,
                    developer=developer,
                    amount=amount,
                    status=status,
                    date=date
                )
                messages.success(request, 'Sale added successfully!')
            else:
                messages.error(request, 'Please fill all required fields.')
        except Exception as e:
            messages.error(request, f'Error adding sale: {str(e)}')
    
    return redirect('profile')

@login_required
def get_sale(request, sale_id):
    if request.user.is_superuser:
        sale = get_object_or_404(Sale, id=sale_id)
    else:
        sale = get_object_or_404(Sale, id=sale_id, user=request.user)
    return JsonResponse({
        'date': sale.date.strftime('%Y-%m-%d') if sale.date else '',
        'property_name': sale.property_name,
        'developer': sale.developer,
        'amount': str(sale.amount),
        'status': sale.status
    })

@login_required
def edit_sale(request, sale_id):
    if request.user.is_superuser:
        sale = get_object_or_404(Sale, id=sale_id)
    else:
        sale = get_object_or_404(Sale, id=sale_id, user=request.user)
    if request.method == 'POST':
        try:
            property_name = request.POST['property']
            developer = request.POST['developer']
            
            # Validate that property and developer exist
            if not Property.objects.filter(name=property_name).exists():
                messages.error(request, 'Selected property does not exist.')
                return redirect('profile')
                
            if not Developer.objects.filter(name=developer).exists():
                messages.error(request, 'Selected developer does not exist.')
                return redirect('profile')
            
            # Convert the date string to a datetime object
            sale_date = datetime.strptime(request.POST['date'], '%Y-%m-%d').date()
            
            # Update sale
            sale.date = sale_date
            sale.property_name = property_name
            sale.developer = developer
            sale.amount = request.POST['amount']
            sale.status = request.POST['status']
            sale.save()
            
            messages.success(request, 'Sale updated successfully!')
        except (ValueError, KeyError) as e:
            messages.error(request, f'Error updating sale: {str(e)}')
    return redirect('profile')

@login_required
def delete_sale(request, sale_id):
    if request.user.is_superuser: 
        sale = get_object_or_404(Sale, id=sale_id)
    else:
        sale = get_object_or_404(Sale, id=sale_id, user=request.user)
    sale.delete()
    return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def view_receivable_voucher(request, release_number):
    """Display receivable data in commission voucher format using tranche data"""
    if not request.user.is_authenticated:
        return redirect('signin')
    
    # Get the commission entry by release number
    try:
        commission_entry = Commission.objects.get(release_number=release_number)
    except Commission.DoesNotExist:
        messages.error(request, 'Receivable not found.')
        return redirect('receivables')
    
    # Check permissions - users can only view their own receivables unless superuser
    if not request.user.is_superuser and commission_entry.agent != request.user:
        messages.error(request, 'You do not have permission to view this receivable.')
        return redirect('receivables')
    
    # Get tranche information - this is now the primary data source
    tranche_id = None
    if 'DP-' in release_number:
        tranche_id = release_number.split('-')[1]
    elif 'LTO-' in release_number:
        tranche_id = release_number.split('-')[1]
    
    tranche_record = None
    if tranche_id:
        try:
            tranche_record = TrancheRecord.objects.get(id=tranche_id)
        except TrancheRecord.DoesNotExist:
            pass
    
    # If we have tranche data, use it for calculations (same as view_tranche)
    if tranche_record:
        # Calculate base values using the same logic as view_tranche
        vat_rate_decimal = tranche_record.vat_rate / Decimal(100)
        net_of_vat_base = tranche_record.total_contract_price / (Decimal(1) + vat_rate_decimal)
        less_process_fee = (tranche_record.total_contract_price * tranche_record.process_fee_percentage) / Decimal(100)
        total_selling_price = net_of_vat_base - less_process_fee
        tax_rate = tranche_record.withholding_tax_rate / Decimal(100)
        gross_commission = total_selling_price * (tranche_record.commission_rate / Decimal(100))
        
        vat_rate_decimal = tranche_record.vat_rate / Decimal(100)
        net_of_vat = gross_commission / (Decimal(1) + vat_rate_decimal)
        vat_amount = gross_commission - net_of_vat
        
        tax = net_of_vat * tax_rate
        withholding_tax_amount = tax
        net_of_withholding_tax = net_of_vat - withholding_tax_amount
        net_commission = gross_commission - tax
        
        # Get DP tranches and calculate values (same as view_tranche)
        dp_payments = tranche_record.payments.filter(is_lto=False).order_by('tranche_number')
        dp_tranches = []
        
        # Calculate option1 values (DP period)
        option1_value_before_deduction = net_commission * (tranche_record.option1_percentage / Decimal(100))
        option1_tax_rate = tranche_record.option1_tax_rate / Decimal(100)
        
        # Apply deductions
        deduction_tax_rate = tranche_record.deduction_tax_rate / Decimal(100)
        deduction_tax = tranche_record.other_deductions * deduction_tax_rate
        deduction_net = tranche_record.other_deductions - deduction_tax
        
        option1_value = option1_value_before_deduction - deduction_net
        option1_monthly = option1_value / Decimal(tranche_record.number_months)
        
        # Calculate totals for DP period
        total_expected_commission = Decimal('0')
        for payment in dp_payments:
            net = option1_monthly
            tax_amount = net * option1_tax_rate
            expected_commission = net - tax_amount
            total_expected_commission += expected_commission
            
            dp_tranches.append({
                'tranche': payment,
                'tax_amount': tax_amount,
                'net_amount': net,
                'expected_commission': expected_commission,
                'balance': expected_commission - payment.received_amount,
                'initial_balance': payment.initial_balance
            })
        
        # Calculate LTO values
        option2_value = net_commission * (tranche_record.option2_percentage / Decimal(100))
        option2_tax_rate = tranche_record.option2_tax_rate / Decimal(100)
        lto_deduction_value = option2_value
        lto_deduction_tax = lto_deduction_value * option2_tax_rate
        lto_deduction_net = lto_deduction_value - lto_deduction_tax
        lto_expected_commission = lto_deduction_net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Get LTO tranche
        lto_payment = tranche_record.payments.filter(is_lto=True).first()
        lto_tranches = []
        if lto_payment:
            lto_tranches.append({
                'tranche': lto_payment,
                'tax_amount': lto_deduction_tax,
                'net_amount': lto_deduction_net,
                'expected_commission': lto_expected_commission,
                'balance': lto_expected_commission - lto_payment.received_amount,
                'initial_balance': lto_payment.initial_balance
            })
        
        commission_rate = tranche_record.commission_rate
        unit_id = getattr(tranche_record, 'unit_id', f"Unit-{tranche_record.id}")
        tcp = tranche_record.total_contract_price
        lot_area = getattr(tranche_record, 'lot_area', 'N/A')
        floor_area = getattr(tranche_record, 'floor_area', 'N/A')
        
        # Determine which tranche data to use based on release number
        if 'DP-' in release_number and dp_tranches:
            # Use DP tranche data - as specified by user
            tranche_data_source = dp_tranches[0]  # Use first DP tranche
            gross_commission_value = tranche_data_source['net_amount']  # net_amount for DP
            withholding_tax_value = tranche_data_source['tax_amount']   # tax_amount for DP
            net_commission_value = tranche_data_source['expected_commission']  # expected_commission for DP
        elif 'LTO-' in release_number and lto_tranches:
            # Use LTO tranche data - as specified by user
            tranche_data_source = lto_tranches[0]
            gross_commission_value = lto_deduction_value  # lto_deduction_value for LTO
            withholding_tax_value = lto_deduction_tax     # lto_deduction_tax for LTO
            net_commission_value = lto_deduction_net      # lto_deduction_net for LTO
        else:
            # Fallback to calculated values
            gross_commission_value = net_commission
            withholding_tax_value = withholding_tax_amount
            net_commission_value = net_commission
            
    else:
        # Fallback to basic commission data if no tranche found
        total_selling_price = Decimal('0')
        net_amount = commission_entry.commission_amount
        tax_amount = Decimal('0')
        expected_commission = commission_entry.commission_amount
        commission_rate = 0
        unit_id = 'N/A'
        tcp = 0
        lot_area = 'N/A'
        floor_area = 'N/A'
    
    # Create a mock commission slip object for the template
    class MockCommissionSlip:
        def __init__(self, commission_entry, tranche_data):
            self.id = f"RCV-{commission_entry.id}"
            self.date = commission_entry.date_released.strftime('%B %d, %Y')
            self.sales_agent_name = commission_entry.agent.get_full_name() or commission_entry.agent.username
            self.buyer_name = commission_entry.buyer
            self.project_name = commission_entry.project_name
            self.developer = commission_entry.developer
            self.release_number = commission_entry.release_number
            self.payment_type = 'Loan Take Out' if 'LTO' in commission_entry.release_number else 'Down Payment'
            
            # Use tranche-based financial data
            self.unit_id = tranche_data['unit_id']
            self.total_selling_price = tranche_data['total_selling_price']
            self.cash_advance = Decimal('0')  # Receivables don't have cash advance
            self.incentive_amount = 0
            
            # Additional tranche-specific fields
            self.lot_area = tranche_data['lot_area']
            self.floor_area = tranche_data['floor_area']
            self.tcp = tranche_data['tcp']
    
    # Create mock commission details using tranche payment data
    class MockCommissionDetail:
        def __init__(self, commission_entry, tranche_data):
            self.position = 'Sales Agent'
            self.particulars = 'COMMISSION'
            self.commission_rate = tranche_data['commission_rate']
            self.gross_commission = tranche_data['gross_commission_value']  # Correct gross commission value
            self.withholding_tax = tranche_data['withholding_tax_value']   # Correct withholding tax value
            self.net_commission = tranche_data['net_commission_value']     # Correct net commission value
    
    # Package tranche data for mock objects
    tranche_data = {
        'unit_id': unit_id,
        'total_selling_price': total_selling_price,
        'tcp': tcp,
        'lot_area': lot_area,
        'floor_area': floor_area,
        'commission_rate': commission_rate,
        'gross_commission_value': gross_commission_value,    # Correct gross commission based on tranche type
        'withholding_tax_value': withholding_tax_value,     # Correct withholding tax based on tranche type
        'net_commission_value': net_commission_value        # Correct net commission based on tranche type
    }
    
    mock_slip = MockCommissionSlip(commission_entry, tranche_data)
    mock_details = [MockCommissionDetail(commission_entry, tranche_data)]
    
    context = {
        'slip': mock_slip,
        'details': mock_details,
        'is_receivable_view': True,  # Flag to indicate this is a receivable view
        'commission_entry': commission_entry,
        'tranche_record': tranche_record,
        'dp_tranches': dp_tranches if tranche_record else [],     # Pass DP tranches to template
        'lto_tranches': lto_tranches if tranche_record else [],   # Pass LTO tranches to template
        'lto_deduction_value': lto_deduction_value if tranche_record else 0,
        'lto_deduction_tax': lto_deduction_tax if tranche_record else 0,
        'lto_deduction_net': lto_deduction_net if tranche_record else 0,
    }
    
    return render(request, 'commission.html', context)

@login_required
def view_tranche_voucher(request, tranche_id):
    """Display tranche data in commission voucher format"""
    if not request.user.is_authenticated:
        return redirect('signin')
    
    # Get the tranche record
    record = get_object_or_404(TrancheRecord, id=tranche_id)
    
    # Check permissions - users can only view their own tranches unless superuser
    if not request.user.is_superuser and record.agent_name != request.user.get_full_name():
        messages.error(request, 'You do not have permission to view this tranche.')
        return redirect('tranche_history')
    
    # Calculate base values using the same logic as view_tranche
    vat_rate_decimal = record.vat_rate / Decimal(100)
    net_of_vat_base = record.total_contract_price / (Decimal(1) + vat_rate_decimal)
    less_process_fee = (record.total_contract_price * record.process_fee_percentage) / Decimal(100)
    total_selling_price = net_of_vat_base - less_process_fee
    tax_rate = record.withholding_tax_rate / Decimal(100)
    gross_commission = total_selling_price * (record.commission_rate / Decimal(100))
    
    vat_rate_decimal = record.vat_rate / Decimal(100)
    net_of_vat = gross_commission / (Decimal(1) + vat_rate_decimal)
    vat_amount = gross_commission - net_of_vat
    
    tax = net_of_vat * tax_rate
    withholding_tax_amount = tax
    net_commission = gross_commission - tax
    
    # Create a mock commission slip object for the template
    class MockTrancheSlip:
        def __init__(self, record, calculations):
            self.id = f"TRC-{record.id}"
            self.date = record.reservation_date.strftime('%B %d, %Y') if record.reservation_date else 'N/A'
            self.sales_agent_name = record.agent_name
            self.buyer_name = record.buyer_name
            self.project_name = record.project_name
            self.developer = record.project_name.split()[0] if record.project_name else 'N/A'  # Extract first word as developer
            self.release_number = f"TRC-{record.id}"
            self.payment_type = 'Tranche Payment'
            
            # Financial data from tranche calculations
            self.unit_id = getattr(record, 'unit_id', f"Unit-{record.id}")
            self.total_selling_price = calculations['total_selling_price']
            self.cash_advance = Decimal('0')  # Tranches don't have cash advance
            self.incentive_amount = 0
            
            # Additional tranche-specific fields
            self.lot_area = getattr(record, 'lot_area', 'N/A')
            self.floor_area = getattr(record, 'floor_area', 'N/A')
            self.tcp = record.total_contract_price
    
    # Create mock commission details
    class MockTrancheDetail:
        def __init__(self, record, calculations):
            self.position = 'Sales Agent'
            self.particulars = 'TRANCHE COMMISSION'
            self.commission_rate = record.commission_rate
            self.gross_commission = calculations['gross_commission']
            self.withholding_tax = calculations['withholding_tax_amount']
            self.net_commission = calculations['net_commission']
    
    # Prepare calculations for mock objects
    calculations = {
        'total_selling_price': total_selling_price,
        'gross_commission': gross_commission,
        'withholding_tax_amount': withholding_tax_amount,
        'net_commission': net_commission
    }
    
    mock_slip = MockTrancheSlip(record, calculations)
    mock_details = [MockTrancheDetail(record, calculations)]
    
    context = {
        'slip': mock_slip,
        'details': mock_details,
        'is_tranche_view': True,  # Flag to indicate this is a tranche view
        'tranche_record': record,
        'calculations': calculations,
    }
    
    return render(request, 'commission.html', context)

@login_required
def receivables(request):
    # Determine scope of data based on permissions
    if request.user.is_superuser:
        commission_entries = Commission.objects.all().order_by('-date_released')
        tranche_records = TrancheRecord.objects.all()
        user_full_name = None  # not used for superuser
    else:
        user_full_name = request.user.get_full_name()
        commission_entries = Commission.objects.filter(agent=request.user).order_by('-date_released')
        tranche_records = TrancheRecord.objects.filter(agent_name=user_full_name)

    # Calculate totals
    total_commission = sum(entry.commission_amount for entry in commission_entries)
    commission_count = commission_entries.count()

    # Calculate total remaining commission from tranches
    total_remaining = Decimal('0')

    # Create a dictionary to store project totals
    project_totals = {}

    # First pass: Calculate total expected commission for each project
    for record in tranche_records:
        project_key = f"{record.project_name}-{record.buyer_name}"
        if project_key not in project_totals:
            project_totals[project_key] = {
                'total_expected': Decimal('0'),
                'total_received': Decimal('0'),
                'payments': {}
            }

        # Get all payments for this tranche
        payments = record.payments.all()

        # Calculate total expected for this project
        project_total_expected = sum(payment.expected_amount for payment in payments)
        project_totals[project_key]['total_expected'] += project_total_expected

        # Store payment info and update received amounts
        for payment in payments:
            key = f"DP-{record.id}-{payment.tranche_number}" if not payment.is_lto else f"LTO-{record.id}-1"
            project_totals[project_key]['payments'][key] = {
                'expected': payment.expected_amount,
                'received': payment.received_amount
            }
            project_totals[project_key]['total_received'] += payment.received_amount

        # Update total remaining
        total_remaining += (project_total_expected - sum(payment.received_amount for payment in payments))

    # Prepare commission entries with payment type and completion percentage
    commissions_with_type = []
    for entry in commission_entries:
        # Get project key from release number
        project_id = entry.release_number.split('-')[1]  # Extract project ID from release number
        project_record = tranche_records.filter(id=project_id).first()

        if project_record:
            project_key = f"{project_record.project_name}-{project_record.buyer_name}"
            project_info = project_totals.get(project_key, {})

            # Calculate completion percentage based on total project commission
            completion_percentage = 0
            if project_info and project_info['total_expected'] > 0:
                completion_percentage = (project_info['total_received'] / project_info['total_expected']) * 100

            commissions_with_type.append({
                'date_released': entry.date_released,
                'release_number': entry.release_number,
                'project_name': entry.project_name,
                'developer': entry.developer,
                'buyer': entry.buyer,
                'agent_name': entry.agent.get_full_name() or entry.agent.username,
                'commission_amount': entry.commission_amount,
                'payment_type': 'Loan Take Out' if 'LTO' in entry.release_number else 'Down Payment',
                'completion_percentage': completion_percentage,
                'total_expected': project_info.get('total_expected', 0),
                'total_received': project_info.get('total_received', 0)
            })

    # --- Pagination ---
    paginator = Paginator(commissions_with_type, 25)  # 25 rows per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'commission_count': commission_count,
        'total_commission': total_commission,
        'total_remaining': total_remaining,
    }
    return render(request, 'receivables.html', context)

@login_required
def edit_commission(request, commission_id):
    commission = get_object_or_404(Commission, id=commission_id, agent=request.user)
    if request.method == 'POST':
        commission.date_released = request.POST.get('date_released')
        commission.release_number = request.POST.get('release_number')
        commission.project_name = request.POST.get('project_name')
        commission.developer = request.POST.get('developer')
        commission.buyer = request.POST.get('buyer')
        commission.commission_amount = request.POST.get('commission_amount')
        commission.save()
        messages.success(request, 'Commission updated successfully!')
        return redirect('receivables')
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)

class CustomPasswordResetView(PasswordResetView):
    template_name = 'password/password_reset.html'
    email_template_name = 'password/password_reset_email.html'
    subject_template_name = 'password/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    from_email = settings.DEFAULT_FROM_EMAIL

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'password/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'password/password_reset_complete.html'
    
    def get_success_url(self):
        return reverse_lazy('signin')

@csrf_protect
@require_http_methods(["POST"])
def update_tranche(request):
    try:
        data = json.loads(request.body)
        tranche_number = data.get('tranche_number')
        received_amount = data.get('received_amount')
        date_received = data.get('date_received')
        is_lto = data.get('is_lto')

        # Get the tranche payment
        tranche = TranchePayment.objects.get(
            tranche_number=tranche_number,
            is_lto=is_lto
        )

        # Update the tranche
        tranche.received_amount = received_amount
        tranche.date_received = datetime.strptime(date_received, '%Y-%m-%d').date()
        
        # Update status based on received amount
        if received_amount >= tranche.expected_amount:
            tranche.status = 'Received'
        elif received_amount > 0:
            tranche.status = 'Partial'
        else:
            tranche.status = 'On Process'
            
        tranche.save()

        return JsonResponse({
            'success': True,
            'message': 'Tranche updated successfully',
            'balance': float(tranche.expected_amount - tranche.received_amount)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

@login_required(login_url='signin')
def change_role(request, profile_id):
    if not (request.user.is_superuser or request.user.profile.role == 'Sales Manager'):
        return HttpResponseForbidden()

    profile = get_object_or_404(Profile, id=profile_id)
    
    if request.method == 'POST':
        new_role = request.POST.get('role')
        
        # Only superusers can assign Sales Manager role
        if new_role == 'Sales Manager' and not request.user.is_superuser:
            messages.error(request, 'Only superusers can assign Sales Manager role')
            return redirect('approve')
            
        # Sales Managers can only modify Sales Supervisor and Sales Agent roles
        if not request.user.is_superuser and profile.role not in ['Sales Supervisor', 'Sales Agent']:
            messages.error(request, 'You can only modify roles for Sales Supervisors and Sales Agents')
            return redirect('approve')
        
        # Validate the role
        if new_role in ['Sales Manager', 'Sales Supervisor', 'Sales Agent']:
            profile.role = new_role
            profile.save()
            messages.success(request, f'Role updated to {new_role}')
        else:
            messages.error(request, 'Invalid role selection')
    
    return redirect('approve')

@login_required(login_url='signin')
def change_team(request, profile_id):
    # Only superusers can change team
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    
    profile = get_object_or_404(Profile, id=profile_id)
    if request.method == 'POST':
        new_team_id = request.POST.get('team')
        try:
            new_team = Team.objects.get(id=new_team_id)
            profile.team = new_team
            profile.save()
            messages.success(request, f'Team updated to {new_team.display_name or new_team.name}')
        except Team.DoesNotExist:
            messages.error(request, 'Selected team does not exist')
    
    return redirect('approve')

@login_required
def toggle_staff_status(request, user_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        user.is_staff = not user.is_staff
        user.save()
        status = 'granted' if user.is_staff else 'removed'
        messages.success(request, f'Staff status {status} for {user.username}')
    return redirect('approve')

@login_required
@require_http_methods(["GET", "POST"])
def delete_profile(request, profile_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You don't have permission to delete profiles.")
    
    profile = get_object_or_404(Profile, id=profile_id)
    user = profile.user
    
    # Don't allow superusers to be deleted through this interface
    if user.is_superuser:
        messages.error(request, "Superuser accounts cannot be deleted through this interface.")
        return redirect('approve')
    
    if request.method == "POST":
        try:
            # Store username for the success message
            username = user.username
            
            # Delete the user (this will cascade delete the profile)
            user.delete()
            
            messages.success(request, f"Profile and user account for {username} have been deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting profile: {str(e)}")
    
        return redirect('approve')
    else:
        # Show confirmation page for GET request
        return render(request, 'confirm_delete.html', {
            'profile': profile,
            'user_to_delete': user
        })

@login_required(login_url='signin')
def tranche_history(request):
    # Base queryset
    tranche_records = TrancheRecord.objects.all()
    
    # Filter based on user role and permissions
    if request.user.is_superuser:
        # Superusers can see all records
        pass
    elif request.user.is_staff:
        # Staff can see:
        # 1. Records they created
        # 2. Records where they are the agent
        # 3. Records for agents in their team
        user_team = request.user.profile.team
        team_members = User.objects.filter(
            profile__team=user_team,
            profile__is_approved=True
        ).values_list('first_name', 'last_name')
        team_full_names = [f"{first} {last}".strip() for first, last in team_members]
        
        tranche_records = tranche_records.filter(
            Q(created_by=request.user) |  # Records they created
            Q(agent_name=request.user.get_full_name()) |  # Records where they are the agent
            Q(agent_name__in=team_full_names)  # Records for their team members
        ).distinct()
    else:
        # Regular users can only see their own records
        tranche_records = tranche_records.filter(
            agent_name=request.user.get_full_name()
        )
    
    # Order by most recent first
    tranche_records = tranche_records.order_by('-created_at')
    
    # Calculate payment statistics for each record
    records_with_stats = []
    for record in tranche_records:
        total_payments = record.payments.count()
        received_payments = record.payments.filter(status='Received').count()
        
        status = 'Pending'
        if received_payments == total_payments and total_payments > 0:
            status = 'Completed'
        elif received_payments > 0:
            status = 'In Progress'
            
        records_with_stats.append({
            'record': record,
            'total_payments': total_payments,
            'received_payments': received_payments,
            'status': status,
            'completion_percentage': (received_payments / total_payments * 100) if total_payments > 0 else 0
        })
    
    # Calculate overall statistics
    total_records = len(records_with_stats)
    active_tranches = sum(1 for r in records_with_stats if r['status'] == 'In Progress')
    total_contract_value = sum(r['record'].total_contract_price for r in records_with_stats)
    
    # --- Pagination ---
    paginator = Paginator(records_with_stats, 25)  # 25 rows per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_records': total_records,
        'active_tranches': active_tranches,
        'total_contract_value': total_contract_value,
        'user_full_name': request.user.get_full_name(),
        'user_team': request.user.profile.team if hasattr(request.user, 'profile') else None,
    }
    return render(request, 'tranche_history.html', context)

@register.filter
def format_tranche_option(value):
    """Convert tranche option from snake_case to Title Case"""
    return value.replace('_', ' ').title()

@login_required(login_url='signin')
def view_tranche(request, tranche_id):
    # Get the tranche record
    record = get_object_or_404(TrancheRecord, id=tranche_id)

    # Check if user has permission to view this tranche
    if request.user.profile.role == 'Sales Agent' and record.agent_name != request.user.get_full_name():
        messages.error(request, 'You do not have permission to view this tranche.')
        return redirect('tranche_history')

    # Format tranche option
    formatted_tranche_option = record.tranche_option.replace('_', ' ').title()

    # Calculate base values using the new Net of VAT computation (TCP / (1+VAT))
    vat_rate_decimal = record.vat_rate / Decimal(100)
    net_of_vat_base = record.total_contract_price / (Decimal(1) + vat_rate_decimal)
    less_process_fee = (record.total_contract_price * record.process_fee_percentage) / Decimal(100)
    total_selling_price = net_of_vat_base - less_process_fee
    tax_rate = record.withholding_tax_rate / Decimal(100)
    gross_commission = total_selling_price * (record.commission_rate / Decimal(100))

    vat_rate_decimal = record.vat_rate / Decimal(100)
    net_of_vat = gross_commission / (Decimal(1) + vat_rate_decimal)
    vat_amount = gross_commission - net_of_vat

    tax = net_of_vat * tax_rate
    withholding_tax_amount = tax
    net_of_withholding_tax = net_of_vat - withholding_tax_amount
    net_commission = gross_commission - tax

    # Get DP tranches and calculate values
    dp_payments = record.payments.filter(is_lto=False).order_by('tranche_number')
    dp_tranches = []
    total_net = Decimal('0')
    total_dp_tax = Decimal('0')

    # Calculate option1 values (DP period)
    option1_value_before_deduction = net_commission * (record.option1_percentage / Decimal(100))
    option1_tax_rate = record.option1_tax_rate / Decimal(100)

    # Apply deductions
    deduction_tax_rate = record.deduction_tax_rate / Decimal(100)
    deduction_tax = record.other_deductions * deduction_tax_rate
    deduction_net = record.other_deductions - deduction_tax

    option1_value = option1_value_before_deduction - deduction_net
    option1_monthly = option1_value / Decimal(record.number_months)

    # Calculate totals for DP period
    total_expected_commission = Decimal('0')
    for payment in dp_payments:
        net = option1_monthly
        tax_amount = net * option1_tax_rate
        expected_commission = net - tax_amount
        total_expected_commission += expected_commission

        dp_tranches.append({
            'tranche': payment,
            'tax_amount': tax_amount,
            'net_amount': net,
            'expected_commission': expected_commission,
            'balance': expected_commission - payment.received_amount,
            'initial_balance': payment.initial_balance
        })
        total_net += net
        total_dp_tax += tax_amount

    # Calculate LTO values
    option2_value = net_commission * (record.option2_percentage / Decimal(100))
    option2_tax_rate = record.option2_tax_rate / Decimal(100)
    lto_deduction_value = option2_value
    lto_deduction_tax = lto_deduction_value * option2_tax_rate
    # Net amount after tax deduction
    lto_deduction_net = lto_deduction_value - lto_deduction_tax
    # Expected commission for the LTO tranche should be the net amount (same value shown in templates)
    lto_expected_commission = lto_deduction_net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Get LTO tranche
    lto_payment = record.payments.filter(is_lto=True).first()
    lto_tranches = []
    if lto_payment:
        lto_tranches.append({
            'tranche': lto_payment,
            'tax_amount': lto_deduction_tax,
            'net_amount': lto_deduction_net,
            'expected_commission': lto_expected_commission,
            'balance': lto_expected_commission - lto_payment.received_amount,
            'initial_balance': lto_payment.initial_balance
        })

    # Calculate totals
    total_commission1 = total_expected_commission
    total_commission_received = sum(t['tranche'].received_amount for t in dp_tranches)
    total_balance = total_commission1 - total_commission_received
    percentage_received = (total_commission_received / total_commission1 * 100) if total_commission1 > 0 else 0
    percentage_remaining = 100 - percentage_received

    total_commission2 = sum(t['tranche'].expected_amount for t in lto_tranches)
    total_commission_received2 = sum(t['tranche'].received_amount for t in lto_tranches)
    total_balance2 = total_commission2 - total_commission_received2
    percentage_received2 = (total_commission_received2 / total_commission2 * 100) if total_commission2 > 0 else 0
    percentage_remaining2 = 100 - percentage_received2

    context = {
        'record': record,
        'total_contract_price': record.total_contract_price,
        'less_process_fee': less_process_fee,
        'net_of_vat_amount': record.net_of_vat_amount,
        'total_selling_price': total_selling_price,
        'commission_rate': record.commission_rate,
        'gross_commission': gross_commission,
        'vat_rate': record.vat_rate,
        'net_of_vat': net_of_vat,
        'withholding_tax_rate': record.withholding_tax_rate,
        'withholding_tax_amount': withholding_tax_amount,
        'net_of_withholding_tax': net_of_withholding_tax,
        'vat_amount': vat_amount,
        'tax': tax_rate * 100,
        'tax_rate': tax,
        'net_commission': net_commission,
        'dp_tranches': dp_tranches,
        'lto_tranches': lto_tranches,
        'option1_value': option1_value,
        'option1_value_before_deduction': option1_value_before_deduction,
        'option2_value': option2_value,
        'option1_percentage': record.option1_percentage,
        'option2_percentage': record.option2_percentage,
        'option1_tax_rate': option1_tax_rate,
        'option2_tax_rate': option2_tax_rate,
        'tranche_option': formatted_tranche_option,
        'number_months': record.number_months,
        'process_fee_percentage': record.process_fee_percentage,
        'option1_monthly': option1_monthly,
        'total_commission1': total_commission1,
        'total_commission_received': total_commission_received,
        'total_balance': total_balance,
        'percentage_received': percentage_received,
        'percentage_remaining': percentage_remaining,
        'other_deductions': record.other_deductions,
        'deduction_type': record.deduction_type,
        'deduction_tax': deduction_tax,
        'deduction_net': deduction_net,
        'deductions': option1_value,
        'deduction_tax_rate': deduction_tax_rate * 100,
        'total_commission2': total_commission2,
        'total_commission_received2': total_commission_received2,
        'total_balance2': total_balance2,
        'percentage_received2': percentage_received2,
        'percentage_remaining2': percentage_remaining2,
        'total_dp_tax': total_dp_tax,
        'lto_deduction_value': lto_deduction_value,
        'lto_deduction_tax': lto_deduction_tax,
        'lto_deduction_net': lto_deduction_net,
    }

    return render(request, 'view_tranche.html', context)

@login_required(login_url='signin')
def edit_tranche(request, tranche_id):
    # Get the tranche record
    record = get_object_or_404(TrancheRecord, id=tranche_id)

    # Check if user has permission to edit this tranche
    if not (request.user.is_superuser or request.user.profile.role in ['Sales Manager', 'Sales Supervisor']):
        messages.error(request, 'You do not have permission to edit tranches.')
        return redirect('tranche_history')

    if request.method == 'POST':
        try:
            # --- Update basic tranche details ---
            record.project_name = request.POST.get('project_name', record.project_name)
            record.agent_name = request.POST.get('agent_name', record.agent_name)
            record.buyer_name = request.POST.get('buyer_name', record.buyer_name)
            # Safely convert numeric fields
            from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
            def _to_decimal(val, default):
                try:
                    return Decimal(val)
                except (InvalidOperation, TypeError):
                    return default
            record.total_contract_price = _to_decimal(request.POST.get('total_contract_price'), record.total_contract_price)
            record.commission_rate = _to_decimal(request.POST.get('commission_rate'), record.commission_rate)
            record.save()

            # --- Update payment records and create commission entries ---
            for payment in record.payments.all():
                received_amount = request.POST.get(f'received_amount_{payment.id}')
                date_received = request.POST.get(f'date_received_{payment.id}')
                old_received_amount = payment.received_amount
                old_date_received = payment.date_received

                if received_amount:
                    payment.received_amount = Decimal(received_amount)
                    if date_received:
                        payment.date_received = datetime.strptime(date_received, '%Y-%m-%d').date()

                    # Update status based on received amount
                    if payment.received_amount >= payment.expected_amount:
                        payment.status = 'Received'
                    elif payment.received_amount > 0:
                        payment.status = 'Partial'
                    else:
                        payment.status = 'On Process'

                    payment.save()

                    # Only create/update commission if there's a new payment or date change
                    if (payment.received_amount != old_received_amount or
                        payment.date_received != old_date_received) and payment.received_amount > 0:

                        # Find the agent user
                        try:
                            agent_user = User.objects.filter(
                                Q(first_name__icontains=record.agent_name.split()[0]) &
                                Q(last_name__icontains=record.agent_name.split()[-1])
                            ).first()

                            if agent_user:
                                # Create or update commission record
                                release_code = f"LTO-{record.id}-1" if payment.is_lto else f"DP-{record.id}-{payment.tranche_number}"

                                # Check for existing commission
                                existing_commission = Commission.objects.filter(
                                    release_number=release_code,
                                    agent=agent_user
                                ).first()

                                if existing_commission:
                                    # Update existing commission with the actual received amount
                                    existing_commission.commission_amount = payment.received_amount
                                    existing_commission.date_released = payment.date_received
                                    existing_commission.save()
                                else:
                                    # Create new commission with the actual received amount
                                    Commission.objects.create(
                                        date_released=payment.date_received,
                                        release_number=release_code,
                                        project_name=record.project_name,
                                        developer=record.project_name.split()[0],  # Using first word as developer
                                        buyer=record.buyer_name,
                                        agent=agent_user,
                                        commission_amount=payment.received_amount
                                    )

                        except User.DoesNotExist:
                            messages.warning(request, f'Could not find user account for agent: {record.agent_name}')

            messages.success(request, 'Tranche record and commissions updated successfully!')
            return redirect('view_tranche', tranche_id=tranche_id)

        except Exception as e:
            messages.error(request, f'Error updating tranche record: {str(e)}')

    # For GET request or if there's an error in POST
    # ----- Recompute key financial figures for display (same as view_tranche) -----
    from decimal import Decimal, ROUND_HALF_UP
    vat_rate_decimal = record.vat_rate / Decimal(100)
    net_of_vat_base = record.total_contract_price / (Decimal(1) + vat_rate_decimal)
    less_process_fee = (record.total_contract_price * record.process_fee_percentage / Decimal(100)) if record.process_fee_percentage else Decimal(0)
    total_selling_price = net_of_vat_base - less_process_fee

    gross_commission = total_selling_price * (record.commission_rate / Decimal(100))
    vat_rate_decimal = record.vat_rate / Decimal(100)
    net_of_vat = gross_commission / (Decimal(1) + vat_rate_decimal)
    tax_amount = net_of_vat * (record.withholding_tax_rate / Decimal(100))
    net_commission = gross_commission - tax_amount

    option2_value      = net_commission * (record.option2_percentage / Decimal(100))
    option2_tax_rate   = record.option2_tax_rate / Decimal(100)
    lto_deduction_value = option2_value
    lto_deduction_tax   = lto_deduction_value * option2_tax_rate
    lto_deduction_net   = lto_deduction_value - lto_deduction_tax
    lto_expected_commission = lto_deduction_net.quantize(Decimal('0.01'), ROUND_HALF_UP)

    lto_payment = record.payments.filter(is_lto=True).first()
    if lto_payment:
        rounded_db_val = lto_payment.expected_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if rounded_db_val != lto_deduction_net:
            lto_payment.expected_amount = lto_deduction_net
            lto_payment.save(update_fields=['expected_amount'])

    return render(request, 'edit_tranche.html', {
        'record': record,
        'dp_payments': record.payments.filter(is_lto=False).order_by('tranche_number'),
        'lto_payment': record.payments.filter(is_lto=True).first(),
        'option2_percentage': record.option2_percentage,
        'option2_tax_rate': record.option2_tax_rate,
        'lto_deduction_value': lto_deduction_value,
        'lto_deduction_tax': lto_deduction_tax,
        'lto_deduction_net': lto_deduction_net,
        'lto_expected_commission': lto_expected_commission,

    })

@register.filter
def filter_received(tranches):
    return [t for t in tranches if t['tranche'].status == 'Received']

@register.filter
def next_due_tranche(tranches):
    for tranche in tranches:
        if tranche['tranche'].status != 'Received':
            return tranche['tranche']
    return None

@register.filter
def last_paid_tranche(tranches):
    paid_tranches = [t['tranche'] for t in tranches if t['tranche'].date_received]
    return max(paid_tranches, key=lambda x: x.date_received) if paid_tranches else None

@register.filter
def replace(value, arg):
    """Replace all instances of arg in the string with spaces"""
    return value.replace(arg, " ")

@login_required(login_url='signin')
def create_commission_slip3(request):
    if not request.user.is_active:
        messages.error(request, "Your account is not active.")
        return redirect('signin')

    # Get the current user's profile
    user_profile = request.user.profile

    # Filter users based on role and permissions
    if request.user.is_superuser or request.user.is_staff:
        # Superusers and staff can see all active agents and supervisors from all teams
        active_agents = User.objects.filter(
            is_active=True,
            profile__role='Sales Agent',
            profile__is_approved=True
        ).order_by('username')
        active_supervisors = User.objects.filter(
            is_active=True,
            profile__role='Sales Supervisor',
            profile__is_approved=True
        ).order_by('username')
        active_managers = User.objects.filter(
            is_active=True,
            profile__role='Sales Manager',
            profile__is_approved=True
        ).order_by('username')
    else:
        # Sales Managers can only see agents and supervisors from their team
        if user_profile.role == 'Sales Manager':
            active_agents = User.objects.filter(
                is_active=True,
                profile__role='Sales Agent',
                profile__team=user_profile.team,
                profile__is_approved=True
            ).order_by('username')
            active_supervisors = User.objects.filter(
                is_active=True,
                profile__role='Sales Supervisor',
                profile__team=user_profile.team,
                profile__is_approved=True
            ).order_by('username')
            active_managers = User.objects.filter(
                is_active=True,
                profile__role='Sales Manager',
                profile__team=user_profile.team,
                profile__is_approved=True
            ).order_by('username')
        else:
            messages.error(request, "You don't have permission to create commission slips.")
            return redirect('commission_history')

    if request.method == 'POST':
        slip_form = CommissionSlipForm3(request.POST)
        if slip_form.is_valid():
            # Get form data
            sales_agent_name = request.POST.get('sales_agent_name')
            supervisor_name = request.POST.get('supervisor_name')
            manager_name = request.POST.get('manager_name')
            buyer_name = request.POST.get('buyer_name')
            project_name = request.POST.get('project_name')
            unit_id = request.POST.get('unit_id')
            total_selling_price = Decimal(request.POST.get('total_selling_price', 0))
            cash_advance = Decimal(request.POST.get('cash_advance', 0))
            particulars = request.POST.get('particulars[]', 'FULL COMM')
            partial_percentage = Decimal(request.POST.get('partial_percentage', '100'))

            # Get separate tax rates for agent, supervisor and manager
            agent_tax_rate = Decimal(request.POST.get('withholding_tax_rate', 10.00))
            supervisor_tax_rate = Decimal(request.POST.get('supervisor_withholding_tax_rate', 10.00))
            manager_tax_rate = Decimal(request.POST.get('manager_tax_rate', 10.00))

            # Calculate cash advance tax (10%)
            cash_advance_tax = cash_advance * Decimal('0.10')
            net_cash_advance = cash_advance - cash_advance_tax

            # Calculate adjusted total
            adjusted_total = total_selling_price - net_cash_advance

            # Create commission slip
            slip = CommissionSlip3.objects.create(
                sales_agent_name=sales_agent_name,
                supervisor_name=supervisor_name,
                manager_name=manager_name,
                buyer_name=buyer_name,
                project_name=project_name,
                unit_id=unit_id,
                total_selling_price=total_selling_price,
                cash_advance=cash_advance,
                cash_advance_tax=cash_advance_tax,
                incentive_amount=Decimal(request.POST.get('incentive_amount', 0)),
                date=request.POST.get('date'),
                created_by=request.user,
                created_at=timezone.now(),
                withholding_tax_rate=agent_tax_rate,
                supervisor_withholding_tax_rate=supervisor_tax_rate,
                manager_tax_rate=manager_tax_rate
            )
                    
            # Get commission rates for agent, supervisor and manager
            agent_commission_rate = Decimal(request.POST.get('agent_commission_rate', 0))
            supervisor_commission_rate = Decimal(request.POST.get('supervisor_commission_rate', 0))
            manager_commission_rate = Decimal(request.POST.get('manager_commission_rate', 0))

            # Create commission details for agent
            if agent_commission_rate > 0:
                # Calculate base commission
                base_commission = adjusted_total * agent_commission_rate / 100

                # Apply partial percentage if applicable
                if particulars == 'PARTIAL COMM':
                    base_commission = base_commission * (partial_percentage / 100)

                # Calculate gross commission
                gross_commission = base_commission
                if particulars == 'INCENTIVES':
                    gross_commission = base_commission + Decimal(request.POST.get('incentive_amount', 0))

                # Calculate tax using agent tax rate
                tax_rate = agent_tax_rate / 100
                withholding_tax = gross_commission * tax_rate
                net_commission = gross_commission - withholding_tax

                # Create agent commission detail
                CommissionDetail3.objects.create(
                    slip=slip,
                    position='Sales Agent',
                    particulars=particulars,
                    commission_rate=agent_commission_rate,
                    base_commission=base_commission,
                    gross_commission=gross_commission,
                    withholding_tax=withholding_tax,
                    net_commission=net_commission,
                    agent_name=sales_agent_name,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=agent_tax_rate,
                    is_supervisor=False
                )

            # Create commission details for supervisor
            if supervisor_commission_rate > 0:
                # Calculate base commission
                base_commission = adjusted_total * supervisor_commission_rate / 100

                # Apply partial percentage if applicable
                if particulars == 'PARTIAL COMM':
                    base_commission = base_commission * (partial_percentage / 100)

                # Calculate gross commission
                gross_commission = base_commission
                if particulars == 'INCENTIVES':
                    gross_commission = base_commission + Decimal(request.POST.get('incentive_amount', 0))

                # Calculate tax using supervisor tax rate
                tax_rate = supervisor_tax_rate / 100
                withholding_tax = gross_commission * tax_rate
                net_commission = gross_commission - withholding_tax

                # Create supervisor commission detail
                CommissionDetail3.objects.create(
                    slip=slip,
                    position='Sales Supervisor',
                    particulars=particulars,
                    commission_rate=supervisor_commission_rate,
                    base_commission=base_commission,
                    gross_commission=gross_commission,
                    withholding_tax=withholding_tax,
                    net_commission=net_commission,
                    agent_name=supervisor_name,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=supervisor_tax_rate,
                    is_supervisor=True
                )

            # Create commission details for manager
            if manager_commission_rate > 0:
                # Calculate base commission
                base_commission = adjusted_total * manager_commission_rate / 100

                # Apply partial percentage if applicable
                if particulars == 'PARTIAL COMM':
                    base_commission = base_commission * (partial_percentage / 100)

                # Calculate gross commission
                gross_commission = base_commission
                if particulars == 'INCENTIVES':
                    gross_commission = base_commission + Decimal(request.POST.get('incentive_amount', 0))

                # Calculate tax using manager tax rate
                tax_rate = manager_tax_rate / 100
                withholding_tax = gross_commission * tax_rate
                net_commission = gross_commission - withholding_tax

                # Create manager commission detail
                CommissionDetail3.objects.create(
                    slip=slip,
                    position='Sales Manager',
                    particulars=particulars,
                    commission_rate=manager_commission_rate,
                    base_commission=base_commission,
                    gross_commission=gross_commission,
                    withholding_tax=withholding_tax,
                    net_commission=net_commission,
                    agent_name=manager_name,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=manager_tax_rate,
                    is_supervisor=False
                )

            messages.success(request, "Commission slip created successfully!")
            return redirect('commission_history')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        slip_form = CommissionSlipForm3()

    return render(request, 'create_commission_slip3.html', {
        'slip_form': slip_form,
        'active_agents': active_agents,
        'active_supervisors': active_supervisors,
        'active_managers': active_managers,
        'user_role': user_profile.role
    })

@login_required(login_url='signin')
def commission3(request, slip_id):
    # Get the commission slip
    slip = get_object_or_404(CommissionSlip3, id=slip_id)
    
    # Check if user has permission to view this slip
    can_view = (
        request.user.is_superuser or
        request.user.is_staff or
        slip.created_by == request.user or
        slip.sales_agent_name == request.user.get_full_name() or
        slip.supervisor_name == request.user.get_full_name() or
        slip.manager_name == request.user.get_full_name()
    )

    if not can_view:
        messages.error(request, 'You do not have permission to view this commission slip.')
        return redirect('commission_history')
    
    # Get all commission details
    details = CommissionDetail3.objects.filter(slip=slip)
    
    # Recalculate withholding tax and net commission for each detail using appropriate tax rate
    for detail in details:
        if detail.agent_name == slip.sales_agent_name:
            # Use agent tax rate
            tax_rate = slip.withholding_tax_rate / 100
        elif detail.agent_name == slip.supervisor_name:
            # Use supervisor tax rate
            tax_rate = slip.supervisor_withholding_tax_rate / 100
        else:
            # Use manager tax rate
            tax_rate = slip.manager_tax_rate / 100
            
        # Recalculate withholding tax and net commission
        detail.withholding_tax = detail.gross_commission * tax_rate
        detail.net_commission = detail.gross_commission - detail.withholding_tax
        detail.save()
    
    # Calculate totals
    total_gross = sum(detail.gross_commission for detail in details)
    total_tax = sum(detail.withholding_tax for detail in details)
    total_net = sum(detail.net_commission for detail in details)
    
    # Filter details based on user role and permissions
    user_role = request.user.profile.role
    user_name = request.user.get_full_name()
    
    if request.user.is_superuser or request.user.is_staff or (user_role == 'Sales Manager' and slip.created_by == request.user):
        # Staff, superusers, and managers who created the slip can see all details
        filtered_details = details
    elif user_role == 'Sales Supervisor' and user_name == slip.supervisor_name:
        # Supervisor can see both their own and their agent's details
        filtered_details = details
    elif user_role == 'Sales Agent' and user_name == slip.sales_agent_name:
        # Agent can only see their own details
        filtered_details = details.filter(agent_name=user_name)
    elif user_role == 'Sales Manager' and user_name == slip.manager_name:
        # Manager can only see their own details
        filtered_details = details.filter(agent_name=user_name)
    else:
        # For other cases, show only their own details
        filtered_details = details.filter(agent_name=user_name)
    
    return render(request, 'commission3.html', {
        'slip': slip,
        'details': filtered_details,
        'total_gross': total_gross,
        'total_tax': total_tax,
        'total_net': total_net,
        'user_role': user_role,
        'is_staff': request.user.is_staff,
        'is_superuser': request.user.is_superuser,
        'is_creator': slip.created_by == request.user
    })

@login_required(login_url='signin')
def delete_tranche(request, tranche_id):
    # Get the tranche record
    tranche = get_object_or_404(TrancheRecord, id=tranche_id)
    
    # Check if user has permission to delete
    if not (request.user.is_superuser or request.user.is_staff or request.user == tranche.created_by):
        messages.error(request, 'You do not have permission to delete this tranche record.')
        return redirect('tranche_history')
    
    if request.method == 'POST':
        try:
            # Delete associated payments first
            tranche.payments.all().delete()
            
            # Delete associated commission records
            Commission.objects.filter(
                project_name=tranche.project_name,
                buyer=tranche.buyer_name
            ).delete()
            
            # Delete the tranche record
            tranche.delete()
            messages.success(request, 'Tranche record deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting tranche record: {str(e)}')
    
    return redirect('tranche_history')

@login_required
def add_property(request):
    if not request.user.is_superuser:
        return JsonResponse({
            'status': 'error',
            'message': 'Only superusers can manage properties.'
        }, status=403)
        
    if request.method == 'POST':
        name = request.POST.get('name')
        developer_id = request.POST.get('developer')
        image = request.FILES.get('image')
        developer_obj = Developer.objects.filter(id=developer_id).first() if developer_id else None
        if name:
            try:
                property = Property.objects.create(name=name, developer=developer_obj, image=image)
                return JsonResponse({
                    'status': 'success',
                    'message': 'Property added successfully!',
                    'property_id': property.id,
                    'property_name': property.name
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def add_developer(request):
    if not request.user.is_superuser:
        return JsonResponse({
            'status': 'error',
            'message': 'Only superusers can manage developers.'
        }, status=403)
        
    if request.method == 'POST':
        name = request.POST.get('name')
        image = request.FILES.get('image')
        if name:
            try:
                developer = Developer.objects.create(name=name, image=image)
                return JsonResponse({
                    'status': 'success',
                    'message': 'Developer added successfully!',
                    'developer_id': developer.id,
                    'developer_name': developer.name
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def delete_property(request, property_id):
    if not request.user.is_superuser:
        return JsonResponse({
            'status': 'error',
            'message': 'Only superusers can delete properties.'
        }, status=403)
    
    try:
        property = get_object_or_404(Property, id=property_id)
        property.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Property deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def delete_developer(request, developer_id):
    if not request.user.is_superuser:
        return JsonResponse({
            'status': 'error',
            'message': 'Only superusers can delete developers.'
        }, status=403)
    
    try:
        developer = get_object_or_404(Developer, id=developer_id)
        developer.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Developer deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

def is_superuser(user):
    return user.is_superuser

@user_passes_test(is_superuser)
def manage_teams(request):
    teams = Team.objects.all().order_by('name')
    return render(request, 'manage_teams.html', {'teams': teams})

@user_passes_test(is_superuser)
def add_team(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        display_name = request.POST.get('display_name')
        
        if not name or not display_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Both name and display name are required.'
            })
            
        try:
            team = Team.objects.create(
                name=name,
                display_name=display_name
            )
            return JsonResponse({
                'status': 'success',
                'message': f'Team {display_name} created successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method.'
    })

@user_passes_test(is_superuser)
def delete_team(request, team_id):
    if request.method == 'DELETE':
        team = get_object_or_404(Team, id=team_id)
        try:
            team.delete()
            return JsonResponse({
                'status': 'success',
                'message': f'Team {team.display_name} deleted successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method.'
    })


@login_required(login_url='signin')
def create_commission_slip3(request):
    if not request.user.is_active:
        messages.error(request, "Your account is not active.")
        return redirect('signin')

    # Get the current user's profile
    user_profile = request.user.profile

    # Filter users based on role and permissions
    if request.user.is_superuser or request.user.is_staff:
        # Superusers and staff can see all active agents and supervisors from all teams
        active_agents = User.objects.filter(
            is_active=True,
            profile__role='Sales Agent',
            profile__is_approved=True
        ).order_by('username')
        active_supervisors = User.objects.filter(
            is_active=True,
            profile__role='Sales Supervisor',
            profile__is_approved=True
        ).order_by('username')
        active_managers = User.objects.filter(
            is_active=True,
            profile__role='Sales Manager',
            profile__is_approved=True
        ).order_by('username')
    else:
        # Sales Managers can only see agents and supervisors from their team
        if user_profile.role == 'Sales Manager':
            active_agents = User.objects.filter(
                is_active=True,
                profile__role='Sales Agent',
                profile__team=user_profile.team,
                profile__is_approved=True
            ).order_by('username')
            active_supervisors = User.objects.filter(
                is_active=True,
                profile__role='Sales Supervisor',
                profile__team=user_profile.team,
                profile__is_approved=True
            ).order_by('username')
            active_managers = User.objects.filter(
                is_active=True,
                profile__role='Sales Manager',
                profile__team=user_profile.team,
                profile__is_approved=True
            ).order_by('username')
        else:
            messages.error(request, "You don't have permission to create commission slips.")
            return redirect('commission_history')

    if request.method == 'POST':
        slip_form = CommissionSlipForm3(request.POST)
        if slip_form.is_valid():
            # Get form data
            sales_agent_name = request.POST.get('sales_agent_name')
            supervisor_name = request.POST.get('supervisor_name')
            manager_id = request.POST.get('manager_id')
            if manager_id:
                manager_user = User.objects.filter(id=manager_id).first()
                manager_name = manager_user.get_full_name() if manager_user else ''
            else:
                # Fallback to the readonly input value if provided
                manager_name = request.POST.get('sales_manager_name', '')
            buyer_name = request.POST.get('buyer_name')
            project_name = request.POST.get('project_name')
            unit_id = request.POST.get('unit_id')
            total_selling_price = Decimal(request.POST.get('total_selling_price', 0))
            cash_advance = Decimal(request.POST.get('cash_advance', 0))
            particulars = request.POST.get('particulars[]', 'FULL COMM')
            partial_percentage = Decimal(request.POST.get('partial_percentage', '100'))

            # Get separate tax rates for agent, supervisor and manager
            agent_tax_rate = Decimal(request.POST.get('withholding_tax_rate', 10.00))
            supervisor_tax_rate = Decimal(request.POST.get('supervisor_withholding_tax_rate', 10.00))
            manager_tax_rate = Decimal(request.POST.get('manager_tax_rate', 10.00))

            # Calculate cash advance tax (10%)
            cash_advance_tax = cash_advance * Decimal('0.10')
            net_cash_advance = cash_advance - cash_advance_tax

            # Calculate adjusted total
            adjusted_total = total_selling_price - net_cash_advance

            # Create commission slip
            slip = CommissionSlip3.objects.create(
                sales_agent_name=sales_agent_name,
                supervisor_name=supervisor_name,
                manager_name=manager_name,
                buyer_name=buyer_name,
                project_name=project_name,
                unit_id=unit_id,
                total_selling_price=total_selling_price,
                cash_advance=cash_advance,
                cash_advance_tax=cash_advance_tax,
                incentive_amount=Decimal(request.POST.get('incentive_amount', 0)),
                date=request.POST.get('date'),
                created_by=request.user,
                created_at=timezone.now(),
                withholding_tax_rate=agent_tax_rate,
                supervisor_withholding_tax_rate=supervisor_tax_rate,
                manager_tax_rate=manager_tax_rate
            )
                    
            # Get commission rates for agent, supervisor and manager
            agent_commission_rate = Decimal(request.POST.get('agent_commission_rate', 0))
            supervisor_commission_rate = Decimal(request.POST.get('supervisor_commission_rate', 0))
            manager_commission_rate = Decimal(request.POST.get('manager_commission_rate', 0))

            # Create commission details for agent
            if agent_commission_rate > 0:
                # Calculate base commission
                base_commission = adjusted_total * agent_commission_rate / 100

                # Apply partial percentage if applicable
                if particulars == 'PARTIAL COMM':
                    base_commission = base_commission * (partial_percentage / 100)

                # Calculate gross commission
                gross_commission = base_commission
                if particulars == 'INCENTIVES':
                    gross_commission = base_commission + Decimal(request.POST.get('incentive_amount', 0))

                # Calculate tax using agent tax rate
                tax_rate = agent_tax_rate / 100
                withholding_tax = gross_commission * tax_rate
                net_commission = gross_commission - withholding_tax

                # Create agent commission detail
                CommissionDetail3.objects.create(
                    slip=slip,
                    position='Sales Agent',
                    particulars=particulars,
                    commission_rate=agent_commission_rate,
                    base_commission=base_commission,
                    gross_commission=gross_commission,
                    withholding_tax=withholding_tax,
                    net_commission=net_commission,
                    agent_name=sales_agent_name,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=agent_tax_rate,
                    is_supervisor=False
                )

            # Create commission details for supervisor
            if supervisor_commission_rate > 0:
                # Calculate base commission
                base_commission = adjusted_total * supervisor_commission_rate / 100

                # Apply partial percentage if applicable
                if particulars == 'PARTIAL COMM':
                    base_commission = base_commission * (partial_percentage / 100)

                # Calculate gross commission
                gross_commission = base_commission
                if particulars == 'INCENTIVES':
                    gross_commission = base_commission + Decimal(request.POST.get('incentive_amount', 0))

                # Calculate tax using supervisor tax rate
                tax_rate = supervisor_tax_rate / 100
                withholding_tax = gross_commission * tax_rate
                net_commission = gross_commission - withholding_tax

                # Create supervisor commission detail
                CommissionDetail3.objects.create(
                    slip=slip,
                    position='Sales Supervisor',
                    particulars=particulars,
                    commission_rate=supervisor_commission_rate,
                    base_commission=base_commission,
                    gross_commission=gross_commission,
                    withholding_tax=withholding_tax,
                    net_commission=net_commission,
                    agent_name=supervisor_name,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=supervisor_tax_rate,
                    is_supervisor=True
                )

            # Create commission details for manager
            if manager_commission_rate > 0:
                # Calculate base commission
                base_commission = adjusted_total * manager_commission_rate / 100

                # Apply partial percentage if applicable
                if particulars == 'PARTIAL COMM':
                    base_commission = base_commission * (partial_percentage / 100)

                # Calculate gross commission
                gross_commission = base_commission
                if particulars == 'INCENTIVES':
                    gross_commission = base_commission + Decimal(request.POST.get('incentive_amount', 0))

                # Calculate tax using manager tax rate
                tax_rate = manager_tax_rate / 100
                withholding_tax = gross_commission * tax_rate
                net_commission = gross_commission - withholding_tax

                # Create manager commission detail
                CommissionDetail3.objects.create(
                    slip=slip,
                    position='Sales Manager',
                    particulars=particulars,
                    commission_rate=manager_commission_rate,
                    base_commission=base_commission,
                    gross_commission=gross_commission,
                    withholding_tax=withholding_tax,
                    net_commission=net_commission,
                    agent_name=manager_name,
                    partial_percentage=partial_percentage,
                    withholding_tax_rate=manager_tax_rate,
                    is_supervisor=False
                )

            messages.success(request, "Commission slip created successfully!")
            return redirect('commission_history')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        slip_form = CommissionSlipForm3()

    return render(request, 'create_commission_slip3.html', {
        'slip_form': slip_form,
        'active_agents': active_agents,
        'active_supervisors': active_supervisors,
        'active_managers': active_managers,
        'user_role': user_profile.role
    })
