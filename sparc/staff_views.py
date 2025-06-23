from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms

from .models import Team, CommissionSlip, CommissionSlip3
from .forms import CommissionSlipForm3

# Helper to restrict to staff or superusers
def _staff_or_super(user):
    return user.is_staff or user.is_superuser

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ("name", "display_name")
        widgets = {
            "name": forms.TextInput(attrs={"class": "w-full border-gray-300 rounded-lg shadow-sm p-2"}),
            "display_name": forms.TextInput(attrs={"class": "w-full border-gray-300 rounded-lg shadow-sm p-2"}),
        }

@login_required
@user_passes_test(_staff_or_super)
def edit_team(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == "POST":
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, "Team updated successfully.")
            return redirect("manage_teams")
    else:
        form = TeamForm(instance=team)
    return render(request, "edit_team.html", {"form": form, "team": team})

@login_required
@user_passes_test(_staff_or_super)
def edit_commission(request, pk):
    """Universal edit view that attempts to locate a commission slip across the
    various slip models we use (standard, full-breakdown, supervisor/agent)."""

    model_form_pairs = [
        (CommissionSlip3, CommissionSlipForm3),
    ]

    # CommissionSlip (original) may not have a dedicated form class; build one on the fly
    from django.forms import modelform_factory
    from .models import CommissionSlip as _CS
    try:
        CSForm = modelform_factory(_CS, exclude=("created_by",))
        model_form_pairs.append((_CS, CSForm))
    except Exception:
        pass

    record = None
    form_class = None
    for model_cls, form_cls in model_form_pairs:
        try:
            record = model_cls.objects.get(pk=pk)
            form_class = form_cls
            break
        except model_cls.DoesNotExist:
            continue

    if record is None:
        # No matching slip found
        raise Http404("Commission slip not found")

    if request.method == "POST":
        form = form_class(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "Commission slip updated successfully.")
            # Determine where to redirect – ideally back to the view page for this slip
            next_param = request.GET.get("next")
            if next_param:
                return redirect(next_param)

            from django.urls import reverse
            # Decide URL based on slip type / model
            if isinstance(record, CommissionSlip3):
                view_name = "commission3"
            elif getattr(record, "is_full_breakdown", False):
                view_name = "commission2"
            else:
                view_name = "commission"
            return redirect(reverse(view_name, args=[record.id]))
    else:
        form = form_class(instance=record)

    return render(request, "edit_commission.html", {"form": form, "record": record})
