from django.db import models
from django.contrib.auth.models import User  # Use Django's built-in User model
from django.db.models import Sum
from django.utils.timezone import now
from decimal import Decimal
Decimal('0.0')



class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100, unique=True, null=True, blank=True)  # Keep it nullable
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)  # To soft-delete teams

    def __str__(self):
        return self.display_name or self.name

    class Meta:
        ordering = ['name']

    @classmethod
    def get_active_choices(cls):
        return [(team.name, team.display_name or team.name) for team in cls.objects.filter(is_active=True)]

    def total_sales(self):
        """Calculate total sales for the entire team"""
        return Sale.objects.filter(agent__team=self).aggregate(Sum('price'))['price__sum'] or 0

class Developer(models.Model):
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Property(models.Model):
    name = models.CharField(max_length=200)
    developer = models.ForeignKey(Developer, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Properties"
        unique_together = ['name', 'developer']  # Prevent duplicate properties for same developer

    def __str__(self):
        if self.developer:
            return f"{self.name} - {self.developer.name}"
        return self.name
    
# models.py
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='profile_images/', default='default.jpg')
    bio = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)  # Add this field
    joining_date = models.DateField(null=True, blank=True)  # Add this field
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Add this field
    total_commission_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0) 

    role = models.CharField(max_length=50, choices=[
        ('Sales Agent', 'Sales Agent'),
        ('Sales Supervisor', 'Sales Supervisor'),
        ('Sales Manager', 'Sales Manager'),
    ])
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    
    def can_approve_user(self, other_user):
        """Check if this user can approve another user"""
        if not self.user.is_staff or self.role != 'Sales Manager':
            return False
        return self.team == other_user.profile.team
        
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_total_sales(self):
        return Sale.objects.filter(user=self.user).aggregate(
            total=Sum('amount')
        )['total'] or 0
    
    def get_active_sales(self):
        return Sale.objects.filter(
            user=self.user, 
            status='Active'
        ).aggregate(total=Sum('amount'))['total'] or 0


class Sale(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(null=True, blank=True)
    property_name = models.CharField(max_length=200, null=True, blank=True)  # Store selected property name
    developer = models.CharField(max_length=200, null=True, blank=True)  # Store selected developer name
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=[
        ('Reserved', 'Reserved'),
        ('Active', 'Active'),
        ('Cancelled', 'Cancelled')
    ])

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.property_name} - {self.amount}"
    property = models.CharField(max_length=255)
    developer = models.CharField(max_length=255)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ('Active', 'Active'),
        ('Cancelled', 'Cancelled'),
        ('Reserved', 'Reserved'),
    ])
    

class CommissionSlip(models.Model):
    sales_agent_name = models.CharField(max_length=100)    
    buyer_name = models.CharField(max_length=255)
    project_name = models.CharField(max_length=255)
    unit_id = models.CharField(max_length=100)
    total_selling_price = models.FloatField(null=True, blank=True)
    commission_rate = models.FloatField(null=True, blank=True)
    incentive_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_advance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_advance_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_slips')
    created_at = models.DateTimeField(null=True, blank=True)
    is_full_breakdown = models.BooleanField(default=False)
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # Agent tax rate
    team_leader_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # Team Leader tax rate
    operation_manager_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # Operation Manager tax rate
    co_founder_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # Co-Founder tax rate
    founder_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # Founder tax rate

    def __str__(self):
        return f"Commission Slip for {self.sales_agent_name}"
    
class CommissionSlip2(models.Model):
    total_selling_price_manager = models.DecimalField(max_digits=12, decimal_places=2)
    team_leader_rate = models.DecimalField(max_digits=5, decimal_places=2)
    operation_manager_rate = models.DecimalField(max_digits=5, decimal_places=2)
    co_founder_rate = models.DecimalField(max_digits=5, decimal_places=2)
    founder_rate = models.DecimalField(max_digits=5, decimal_places=2)
    funds_rate = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Commission Slip - {self.id}"

class CommissionDetail(models.Model):
    slip = models.ForeignKey(CommissionSlip, on_delete=models.CASCADE, related_name='details')
    position = models.CharField(max_length=100, default="N/A")
    particulars = models.CharField(max_length=255, default="N/A")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    base_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_commission = models.DecimalField(max_digits=12, decimal_places=2)
    withholding_tax = models.DecimalField(max_digits=12, decimal_places=2)
    net_commission = models.DecimalField(max_digits=12, decimal_places=2)
    agent_name = models.CharField(max_length=100, null=True, blank=True)
    partial_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # Add this field

    def __str__(self):
        return f"{self.position} - {self.particulars}"






class Commission(models.Model):
    date_released = models.DateField()
    release_number = models.CharField(max_length=50)
    project_name = models.CharField(max_length=200)
    developer = models.CharField(max_length=200)
    buyer = models.CharField(max_length=200)
    agent = models.ForeignKey(User, on_delete=models.CASCADE)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.release_number} - {self.project_name}"

    class Meta:
        ordering = ['-date_released']



    

class TrancheRecord(models.Model):
    project_name = models.CharField(max_length=255)
    agent_name = models.CharField(max_length=255)
    phase = models.CharField(max_length=100)
    unit_id = models.CharField(max_length=100)
    buyer_name = models.CharField(max_length=255)
    reservation_date = models.DateField()
    total_contract_price = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    process_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    option1_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    option2_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    option1_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    option2_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    tranche_option = models.CharField(max_length=20)
    number_months = models.IntegerField()
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00)
    deduction_type = models.CharField(max_length=50, null=True, blank=True)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deduction_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tranches')

    def __str__(self):
        return f"{self.project_name} - {self.buyer_name}"

class TranchePayment(models.Model):
    tranche_record = models.ForeignKey(TrancheRecord, on_delete=models.CASCADE, related_name='payments')
    tranche_number = models.IntegerField()
    expected_date = models.DateField()
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_received = models.DateField(null=True, blank=True)
    is_lto = models.BooleanField(default=False)  # To distinguish between DP and LTO tranches
    status = models.CharField(max_length=20, default='On Process')  # On Process, Partial, Received
    initial_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Add initial balance field

    def __str__(self):
        return f"Tranche {self.tranche_number} for {self.tranche_record.project_name}"

    class Meta:
        ordering = ['tranche_number']

class CommissionSlip3(models.Model):
    sales_agent_name = models.CharField(max_length=100)    
    supervisor_name = models.CharField(max_length=100)
    buyer_name = models.CharField(max_length=255)
    project_name = models.CharField(max_length=255)
    unit_id = models.CharField(max_length=100)
    total_selling_price = models.FloatField(null=True, blank=True)
    incentive_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_advance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_advance_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_slips3')
    created_at = models.DateTimeField(null=True, blank=True)
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # Agent tax rate
    supervisor_withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # New supervisor tax rate

    def __str__(self):
        return f"Commission Slip for {self.sales_agent_name} with Supervisor {self.supervisor_name}"

class CommissionDetail3(models.Model):
    slip = models.ForeignKey(CommissionSlip3, on_delete=models.CASCADE, related_name='details')
    position = models.CharField(max_length=100, default="N/A")
    particulars = models.CharField(max_length=255, default="N/A")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    base_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_commission = models.DecimalField(max_digits=12, decimal_places=2)
    withholding_tax = models.DecimalField(max_digits=12, decimal_places=2)
    net_commission = models.DecimalField(max_digits=12, decimal_places=2)
    agent_name = models.CharField(max_length=100, null=True, blank=True)
    partial_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    is_supervisor = models.BooleanField(default=False)  # New field to distinguish supervisor from agent

    def __str__(self):
        return f"{self.position} - {self.particulars}"




    
