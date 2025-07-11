from django.urls import path
from . import views, staff_views
from django.conf import settings
from django.conf.urls.static import static
from .views import CustomPasswordResetView, CustomPasswordResetDoneView, CustomPasswordResetConfirmView, CustomPasswordResetCompleteView

urlpatterns = [
    path('sales/export/', views.export_sales_excel, name='export_sales_excel'),
    path('top5/export/', views.export_top5_excel, name='export_top5_excel'),
    path('', views.home, name='home'),  
    path('navbar/', views.navbar, name='navbar'), 
    path('signin/', views.signin, name='signin'),  
    path('signout/', views.signout, name='signout'), 
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
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
    path('commission2/<int:slip_id>/edit/', views.edit_commission_slip, name='edit_commission_slip'),
    path('commission2/<int:slip_id>/delete/', views.delete_commission_slip, name='delete_commission_slip'),
    path('commission/<int:slip_id>/delete/', views.delete_commission_slip, name='delete_commission_slip'),
    path('commission3/<int:slip_id>/', views.commission3, name='commission3'),
    path('tranches/', views.tranches_view, name='tranches'),
    path('tranche-history/', views.tranche_history, name='tranche_history'),
    path('tranche/<int:tranche_id>/', views.view_tranche, name='view_tranche'),
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
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('commission-history/', views.commission_history, name='commission_history'),
    path('team-dashboard/<str:team_name>/', views.team_dashboard, name='team_dashboard'),
    path('add-property/', views.add_property, name='add_property'),
    path('add-developer/', views.add_developer, name='add_developer'),
    path('delete-property/<int:property_id>/', views.delete_property, name='delete_property'),
    path('delete-developer/<int:developer_id>/', views.delete_developer, name='delete_developer'),
    path('manage-teams/', views.manage_teams, name='manage_teams'),
    path('add-team/', views.add_team, name='add_team'),
    path('delete-team/<int:team_id>/', views.delete_team, name='delete_team'),
    path('team/<int:pk>/edit/', staff_views.edit_team, name='edit_team'),
    path('commission/<int:pk>/edit/', staff_views.edit_commission, name='edit_commission'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
