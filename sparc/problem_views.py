from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.utils import timezone
from .models import ProblemReport


def report_problem(request):
    """View for users to report login/access problems"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        category = request.POST.get('category')
        subject = request.POST.get('subject')
        description = request.POST.get('description')
        
        # Get client info
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = request.META.get('REMOTE_ADDR')
        
        # Create problem report
        problem = ProblemReport.objects.create(
            name=name,
            email=email,
            phone=phone,
            category=category,
            subject=subject,
            description=description,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        messages.success(request, 'Your problem report has been submitted successfully. We will contact you soon.')
        return redirect('signin')
    
    return render(request, 'report_problem.html')


@user_passes_test(lambda u: u.is_superuser)
def problem_dashboard(request):
    """Dashboard for superusers to view and manage problem reports"""
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    category_filter = request.GET.get('category', 'all')
    
    problems = ProblemReport.objects.all()
    
    if status_filter != 'all':
        problems = problems.filter(status=status_filter)
    if priority_filter != 'all':
        problems = problems.filter(priority=priority_filter)
    if category_filter != 'all':
        problems = problems.filter(category=category_filter)
    
    # Pagination
    paginator = Paginator(problems, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total': ProblemReport.objects.count(),
        'open': ProblemReport.objects.filter(status='open').count(),
        'in_progress': ProblemReport.objects.filter(status='in_progress').count(),
        'resolved': ProblemReport.objects.filter(status='resolved').count(),
        'high_priority': ProblemReport.objects.filter(priority='high').count(),
    }
    
    return render(request, 'problem_dashboard.html', {
        'page_obj': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'status_choices': ProblemReport.STATUS_CHOICES,
        'priority_choices': ProblemReport.PRIORITY_CHOICES,
        'category_choices': ProblemReport.CATEGORY_CHOICES,
    })


@user_passes_test(lambda u: u.is_superuser)
def problem_detail(request, problem_id):
    """View and update a specific problem report"""
    problem = get_object_or_404(ProblemReport, id=problem_id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        priority = request.POST.get('priority')
        admin_notes = request.POST.get('admin_notes')
        
        problem.status = status
        problem.priority = priority
        problem.admin_notes = admin_notes
        problem.updated_at = timezone.now()
        
        if status == 'resolved' and not problem.resolved_at:
            problem.resolved_by = request.user
            problem.resolved_at = timezone.now()
        
        problem.save()
        messages.success(request, 'Problem report updated successfully.')
        return redirect('problem_dashboard')
    
    return render(request, 'problem_detail.html', {
        'problem': problem,
        'status_choices': ProblemReport.STATUS_CHOICES,
        'priority_choices': ProblemReport.PRIORITY_CHOICES,
    })


@user_passes_test(lambda u: u.is_superuser)
def delete_problem(request, problem_id):
    """Delete a specific problem report."""
    problem = get_object_or_404(ProblemReport, id=problem_id)
    if request.method == 'POST':
        problem.delete()
        messages.success(request, 'Problem report has been deleted successfully.')
        return redirect('problem_dashboard')
    
    # If it's a GET request, you could render a confirmation page, 
    # but for now we'll just redirect. A POST request is expected for deletion.
    return redirect('problem_dashboard')
