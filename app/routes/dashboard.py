from flask import Blueprint, render_template, session
from app.routes.auth import login_required, get_current_user
from app.services.analytics_service import get_dashboard_metrics

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    user = get_current_user()
    metrics = get_dashboard_metrics()
    return render_template('dashboard.html', user=user, metrics=metrics, active_tab='dashboard')
