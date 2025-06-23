from django.utils import timezone


def notification_counts(request):
    """Return counts used for notification badges in navbar."""
    if not request.user.is_authenticated:
        return {}

    # If the user is currently on the list page, don't show its own badge
    current_url = getattr(request, "resolver_match", None)
    current_name = current_url.url_name if current_url else None

    # Initialize counts
    unapproved_users_count = 0
    new_commissions_count = 0
    pending_receivables_count = 0
    new_tranches_count = 0

    # Import models lazily to avoid circular imports / missing models
    try:
        from .models import Profile
        unapproved_users_count = Profile.objects.filter(is_approved=False).count()
    except Exception:
        pass

    try:
        from .models import CommissionSlip
        last_seen = request.session.get('last_seen_commissions')
        if last_seen:
            from django.utils.dateparse import parse_datetime
            ts = parse_datetime(last_seen)
            if ts is not None:
                new_commissions_count = CommissionSlip.objects.filter(created_at__gt=ts).exclude(created_by=request.user).count()
            else:
                new_commissions_count = CommissionSlip.objects.exclude(created_by=request.user).count()
        else:
            new_commissions_count = CommissionSlip.objects.exclude(created_by=request.user).count()
    except Exception:
        pass

    # Receivable model may not exist in all installs
    try:
        from .models import Commission
        ts_str = request.session.get('last_seen_receivables')
        from django.utils.dateparse import parse_datetime
        ts = parse_datetime(ts_str) if ts_str else None
        base_qs = Commission.objects.all()
        if ts is not None:
            base_qs = base_qs.filter(created_at__gt=ts)
        pending_receivables_count = base_qs.count()
    except Exception:
        pass

    # Tranche model may be TrancheRecord; adjust if necessary
    try:
        from .models import Tranche
        ts_str = request.session.get('last_seen_tranches')
        if ts_str:
            from django.utils.dateparse import parse_datetime
            ts = parse_datetime(ts_str)
            if ts:
                new_tranches_count = Tranche.objects.filter(created_at__gt=ts).count()
            else:
                new_tranches_count = Tranche.objects.count()
        else:
            new_tranches_count = Tranche.objects.count()
    except Exception:
        # Attempt fallback name
        try:
            from .models import TrancheRecord
            ts_str = request.session.get('last_seen_tranches')
            from django.utils.dateparse import parse_datetime
            ts = parse_datetime(ts_str) if ts_str else None
            if ts:
                new_tranches_count = TrancheRecord.objects.filter(created_at__gt=ts).count()
            else:
                new_tranches_count = TrancheRecord.objects.count()
        except Exception:
            pass

    return {
        "unapproved_users_count": unapproved_users_count if current_name != "approve" else 0,
        "new_commissions_count": new_commissions_count if current_name != "commission_history" else 0,
        "pending_receivables_count": 0 if current_name == "receivables" else pending_receivables_count,
        "new_tranches_count": new_tranches_count if current_name != "tranche_history" else 0,
    }
