from django.urls import path
from . import views, staff_views, invoice_views, excel_views
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from .views import CustomPasswordResetView, CustomPasswordResetDoneView, CustomPasswordResetConfirmView, CustomPasswordResetCompleteView
from .problem_views import report_problem, problem_dashboard, problem_detail, delete_problem

urlpatterns = [
    path('create-invoice/<int:tranche_id>/', invoice_views.create_invoice, name='create_invoice'),
    path('create-combined-invoice/', invoice_views.create_combined_invoice, name='create_combined_invoice'),
    path('invoice/<int:invoice_id>/', invoice_views.invoice_view, name='invoice_view'),
    path('invoice/<int:invoice_id>/email/', invoice_views.email_invoice, name='email_invoice'),
    path('invoice/<int:invoice_id>/pdf/', invoice_views.invoice_pdf, name='invoice_pdf'),
    path('invoice/<int:invoice_id>/excel/', invoice_views.invoice_csv, name='invoice_csv'),
    path('invoice/<int:invoice_id>/update-bill-to/', invoice_views.update_bill_to, name='update_bill_to'),
    path('invoice/<int:invoice_id>/update-billing-details/', invoice_views.update_billing_details, name='update_billing_details'),
    path('invoice/<int:invoice_id>/update-invoice-items/', invoice_views.update_invoice_items, name='update_invoice_items'),
    path('invoice/<int:invoice_id>/update/', invoice_views.update_invoice, name='update_invoice'),
    path('invoice/<int:invoice_id>/sign/<str:role>/', invoice_views.sign_invoice, name='sign_invoice'),
    path('invoice/<int:invoice_id>/upload-signature/<str:role>/', invoice_views.upload_signature, name='upload_signature'),
    path('sales/export/', views.export_sales_excel, name='export_sales_excel'),
    path('top5/export/', views.export_top5_excel, name='export_top5_excel'),

    path('report-problem/', report_problem, name='report_problem'),
    path('problem-dashboard/', problem_dashboard, name='problem_dashboard'),
    path('problem/<int:problem_id>/', problem_detail, name='problem_detail'),
    path('problem/<int:problem_id>/delete/', delete_problem, name='delete_problem'),
    
    path('', views.home, name='home'),  
    path('navbar/', views.navbar, name='navbar'), 
    path('signin/', views.signin, name='signin'),  
    path('signout/', views.signout, name='signout'), 
    path('create-user/', views.create_user_by_superuser, name='create_user'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/edit/<int:profile_id>/', views.edit_profile_view, name='edit_user_profile'),
    path('approve/', views.approve_users_list, name='approve'),
    path('approve/<int:profile_id>/', views.approve_user, name='approve_user'),
    path('reject/<int:profile_id>/', views.reject_user, name='reject_user'),
    path('change-role/<int:profile_id>/', views.change_role, name='change_role'),
    path('change-team/<int:profile_id>/', views.change_team, name='change_team'),
    path('delete-profile/<int:profile_id>/', views.delete_profile, name='delete_profile'),
    path('toggle-staff/<int:user_id>/', views.toggle_staff_status, name='toggle_staff_status'),
    path('create-commission-slip/', views.create_commission_slip, name='create_commission_slip'),
    path('create-commission-slip2/', views.create_commission_slip2, name='create_commission_slip2'),
    path('create-commission-slip3/', views.create_commission_slip3, name='create_commission_slip3'),
    path('commission/', views.commission_view, name='commission'),  # Default view without slip_id
    path('commission/<int:slip_id>/', views.commission_view, name='commission'),
    path('commission2/', views.commission, name='commission2'),
    path('commission2/<int:slip_id>/', views.commission_view2, name='commission2'),
    path('commission2/<str:slip_id>/edit/', views.edit_commission_slip, name='edit_commission_slip'),
    path('commission2/<str:slip_id>/delete/', views.delete_commission_slip, name='delete_commission_slip'),
    path('commission/<str:slip_id>/delete/', views.delete_commission_slip, name='delete_commission_slip'),
    path('commission3/<int:slip_id>/', views.commission3, name='commission3'),
    path('save-signature/', views.save_signature, name='save_signature'),
    path('tranches/', views.tranches_view, name='tranches'),
    path('process-excel-upload/', excel_views.process_excel_upload, name='process_excel_upload'),
    path('tranche-history/', views.tranche_history, name='tranche_history'),
    path('tranche/<int:tranche_id>/', views.view_tranche, name='view_tranche'),
    path('tranche-voucher/<int:tranche_id>/', views.view_tranche_voucher, name='view_tranche_voucher'),
    path('tranche/<int:tranche_id>/edit/', views.edit_tranche, name='edit_tranche'),
    path('tranche/<int:tranche_id>/delete/', views.delete_tranche, name='delete_tranche'),
    path('update-tranche/', views.update_tranche, name='update_tranche'),
    path('add-sale/', views.add_sale, name='add_sale'), 
    path('delete-sale/<int:sale_id>/', views.delete_sale, name='delete_sale'),
    path('profile/', views.profile, name='profile'),
    path('add-sale/', views.add_sale, name='add_sale'),
    path('get-sale/<int:sale_id>/', views.get_sale, name='get_sale'),
    path('edit-sale/<int:sale_id>/', views.edit_sale, name='edit_sale'),
    path('delete-sale/<int:sale_id>/', views.delete_sale, name='delete_sale'),
    path('receivables/', views.receivables, name='receivables'),
    path('receivable-voucher/<str:release_number>/', views.view_receivable_voucher, name='view_receivable_voucher'),
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'), name='password_change_done'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate_account'),
    path('commission-history/', views.commission_history, name='commission_history'),
    path('add-property/', views.add_property, name='add_property'),
    path('add-developer/', views.add_developer, name='add_developer'),
    path('delete-property/<int:property_id>/', views.delete_property, name='delete_property'),
    path('delete-developer/<int:developer_id>/', views.delete_developer, name='delete_developer'),
    path('manage-teams/', views.manage_teams, name='manage_teams'),
    path('add-team/', views.add_team, name='add_team'),
    path('delete-team/<int:team_id>/', views.delete_team, name='delete_team'),
    # Superuser edit other user profile

    path('team/<int:pk>/edit/', staff_views.edit_team, name='edit_team'),
    path('commission/<int:pk>/edit/', staff_views.edit_commission, name='edit_commission'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
