from app.database import query_db
from datetime import datetime, date, timedelta
import calendar

def get_dashboard_metrics():
    """Calculates all KPI cards and charts required by the Figma Dashboard."""
    
    # 1. Total Sales and Trends
    total_sales_row = query_db('''
        SELECT 
            COALESCE(SUM(amount_paid), 0) AS total_revenue,
            COALESCE(SUM(quantity), 0) AS total_quantity,
            COUNT(*) AS total_transactions
        FROM sales
    ''', one=True)
    
    total_revenue = float(total_sales_row['total_revenue']) if total_sales_row else 0.0
    total_quantity = int(total_sales_row['total_quantity']) if total_sales_row else 0
    total_transactions = int(total_sales_row['total_transactions']) if total_sales_row else 0
    avg_packs_per_order = round(total_quantity / total_transactions, 1) if total_transactions > 0 else 0.0

    # Current vs Last Month Growth
    today = date.today()
    cur_year = today.year
    cur_month = today.month
    
    cur_month_revenue_row = query_db('''
        SELECT COALESCE(SUM(amount_paid), 0) AS rev
        FROM sales
        WHERE YEAR(sale_date) = %s AND MONTH(sale_date) = %s
    ''', (cur_year, cur_month), one=True)
    cur_month_rev = float(cur_month_revenue_row['rev']) if cur_month_revenue_row else 0.0
    
    # Prev month
    prev_month = 12 if cur_month == 1 else cur_month - 1
    prev_month_year = cur_year - 1 if cur_month == 1 else cur_year
    prev_month_revenue_row = query_db('''
        SELECT COALESCE(SUM(amount_paid), 0) AS rev
        FROM sales
        WHERE YEAR(sale_date) = %s AND MONTH(sale_date) = %s
    ''', (prev_month_year, prev_month), one=True)
    prev_month_rev = float(prev_month_revenue_row['rev']) if prev_month_revenue_row else 0.0
    
    growth_rate = 0.0
    has_comparison_data = False
    if prev_month_rev > 0:
        growth_rate = round(((cur_month_rev - prev_month_rev) / prev_month_rev) * 100, 1)
        has_comparison_data = True
    elif cur_month_rev > 0:
        growth_rate = 0.0
        has_comparison_data = False

    # Top-Selling Flavor
    top_flavor_row = query_db('''
        SELECT 
            p.product_id,
            p.display_name,
            p.flavor_name,
            COALESCE(SUM(s.quantity), 0) AS packs_sold,
            COALESCE(SUM(s.amount_paid), 0) AS revenue
        FROM products p
        LEFT JOIN sales s ON p.product_id = s.product_id
        GROUP BY p.product_id, p.display_name, p.flavor_name
        ORDER BY revenue DESC, packs_sold DESC
        LIMIT 1
    ''', one=True)
    
    top_flavor_name = top_flavor_row['display_name'] if top_flavor_row and top_flavor_row['packs_sold'] > 0 else "Cheese Delight"
    top_flavor_packs = top_flavor_row['packs_sold'] if top_flavor_row else 0
    top_flavor_share = round((top_flavor_packs / total_quantity * 100), 1) if total_quantity > 0 else 37.7

    # 2. Monthly Sales Trend (Line Chart across current year)
    monthly_data = query_db('''
        SELECT 
            MONTH(sale_date) AS month_num,
            COALESCE(SUM(amount_paid), 0) AS month_revenue
        FROM sales
        WHERE YEAR(sale_date) = %s
        GROUP BY MONTH(sale_date)
        ORDER BY month_num
    ''', (cur_year,))
    
    months_map = {r['month_num']: float(r['month_revenue']) for r in monthly_data}
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May (Current)', 'Jun (Est.)']
    monthly_series = []
    running_ytd = 0.0
    for m in range(1, 7):
        rev = months_map.get(m, 0.0)
        monthly_series.append(rev)
        running_ytd += rev
    
    # If no data yet, provide friendly empty baseline
    ytd_total = total_revenue

    # 3. Sales by Flavor (Bar Chart) & Flavor Share (Donut Chart)
    flavor_stats = query_db('''
        SELECT 
            p.product_id,
            p.flavor_name,
            p.display_name,
            p.badge_color,
            COALESCE(SUM(s.quantity), 0) AS total_packs,
            COALESCE(SUM(s.amount_paid), 0) AS total_revenue
        FROM products p
        LEFT JOIN sales s ON p.product_id = s.product_id
        GROUP BY p.product_id, p.flavor_name, p.display_name, p.badge_color
        ORDER BY p.product_id
    ''')
    
    flavor_labels = []
    flavor_revenues = []
    flavor_packs = []
    flavor_colors = []
    flavor_shares = []
    
    for f in flavor_stats:
        p_name = f['flavor_name']
        d_name = f['display_name']
        rev = float(f['total_revenue'])
        pk = int(f['total_packs'])
        col = f['badge_color'] or '#F5A623'
        
        flavor_labels.append(p_name)
        flavor_revenues.append(rev)
        flavor_packs.append(pk)
        flavor_colors.append(col)
        share = round((pk / total_quantity * 100), 1) if total_quantity > 0 else 0.0
        flavor_shares.append(share)

    # 4. Daily Sales (Last 14 Days)
    fourteen_days_ago = today - timedelta(days=13)
    daily_records = query_db('''
        SELECT 
            DATE(sale_date) AS s_date,
            COALESCE(SUM(amount_paid), 0) AS daily_rev
        FROM sales
        WHERE sale_date >= %s
        GROUP BY DATE(sale_date)
        ORDER BY s_date
    ''', (fourteen_days_ago,))
    
    daily_map = {r['s_date'].strftime('%Y-%m-%d') if isinstance(r['s_date'], (date, datetime)) else str(r['s_date']): float(r['daily_rev']) for r in daily_records}
    daily_labels = []
    daily_values = []
    fourteen_day_total = 0.0
    
    for i in range(14):
        d = fourteen_days_ago + timedelta(days=i)
        d_str = d.strftime('%Y-%m-%d')
        val = daily_map.get(d_str, 0.0)
        daily_values.append(val)
        fourteen_day_total += val
        
        if i == 13:
            daily_labels.append('Today')
        else:
            daily_labels.append(d.strftime('%d'))

    # 5. Recent Records (Latest 5)
    recent_sales = query_db('''
        SELECT 
            s.sale_id,
            s.sale_date,
            s.quantity,
            s.amount_paid,
            c.customer_name,
            p.display_name AS flavor_display,
            p.flavor_name,
            p.badge_color,
            u.full_name AS cashier_name
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN products p ON s.product_id = p.product_id
        JOIN users u ON s.recorded_by = u.user_id
        ORDER BY s.sale_date DESC, s.sale_id DESC
        LIMIT 5
    ''')
    
    for r in recent_sales:
        r['formatted_id'] = f"REC-{r['sale_id']:04d}"
        names = r['customer_name'].strip().split()
        r['initials'] = (names[0][0] + names[-1][0]).upper() if len(names) >= 2 else names[0][:2].upper()

    has_monthly_data = any(v > 0 for v in monthly_series)
    has_daily_data = any(v > 0 for v in daily_values)
    daily_date_range = f"{fourteen_days_ago.strftime('%b %d')} – {today.strftime('%b %d, %Y')}"

    return {
        'total_revenue': total_revenue,
        'growth_rate': growth_rate,
        'has_comparison_data': has_comparison_data,
        'total_quantity': total_quantity,
        'batch_target_pct': min(100, round((total_quantity / 3160) * 100, 1)) if total_quantity > 0 else 0.0,
        'total_transactions': total_transactions,
        'avg_packs_per_order': avg_packs_per_order,
        'top_flavor_name': top_flavor_name,
        'top_flavor_packs': top_flavor_packs,
        'top_flavor_share': top_flavor_share,
        
        # Monthly chart
        'month_labels': month_labels,
        'monthly_series': monthly_series,
        'has_monthly_data': has_monthly_data,
        'ytd_total': ytd_total,
        
        # Flavor chart
        'flavor_labels': flavor_labels,
        'flavor_revenues': flavor_revenues,
        'flavor_packs': flavor_packs,
        'flavor_colors': flavor_colors,
        'flavor_shares': flavor_shares,
        'flavor_stats': flavor_stats,
        
        # Daily chart
        'daily_labels': daily_labels,
        'daily_values': daily_values,
        'has_daily_data': has_daily_data,
        'daily_date_range': daily_date_range,
        'fourteen_day_total': fourteen_day_total,
        
        # Recent records
        'recent_sales': recent_sales
    }
