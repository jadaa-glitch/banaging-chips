from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from app.routes.auth import login_required, get_current_user
from app.database import get_db, query_db
from datetime import date
import csv
import io

history_bp = Blueprint('history', __name__)

@history_bp.route('/deleted-records')
@login_required
def deleted_records():
    user = get_current_user()
    
    # Query parameters
    search = request.args.get('search', '').strip()
    flavor_id = request.args.get('flavor', '').strip()
    time_filter = request.args.get('time', 'all').strip()

    # Base WHERE
    where_clauses = ['1=1']
    params = []

    if search:
        where_clauses.append('(c.customer_name LIKE %s OR ds.delete_reason LIKE %s OR CONCAT("REC-", LPAD(ds.sale_id, 4, "0")) LIKE %s)')
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if flavor_id and flavor_id != 'all':
        where_clauses.append('ds.product_id = %s')
        params.append(flavor_id)
    if time_filter == 'month':
        where_clauses.append('YEAR(ds.deleted_at) = YEAR(CURRENT_DATE()) AND MONTH(ds.deleted_at) = MONTH(CURRENT_DATE())')

    where_sql = ' AND '.join(where_clauses)

    # 4 Top Stats
    stat_row = query_db('''
        SELECT 
            COUNT(*) AS archived_count,
            COALESCE(SUM(amount_paid), 0) AS adjusted_value,
            COALESCE(SUM(quantity), 0) AS reclaimed_packs,
            COUNT(DISTINCT deleted_by) AS audited_staff_count
        FROM deleted_sales
    ''', one=True)

    archived_count = stat_row['archived_count'] if stat_row else 0
    adjusted_value = float(stat_row['adjusted_value']) if stat_row else 0.0
    reclaimed_packs = int(stat_row['reclaimed_packs']) if stat_row else 0
    audited_staff_count = stat_row['audited_staff_count'] if stat_row else 0

    # Staff officers list
    officers = query_db('''
        SELECT DISTINCT u.full_name
        FROM deleted_sales ds
        JOIN users u ON ds.deleted_by = u.user_id
    ''')
    officer_names = ' • '.join([o['full_name'] for o in officers]) if officers else user['full_name']

    # Query deleted records
    rows = query_db(f'''
        SELECT 
            ds.*,
            c.customer_name,
            p.flavor_name,
            p.display_name,
            p.badge_color,
            u_del.full_name AS deleted_by_name
        FROM deleted_sales ds
        JOIN customers c ON ds.customer_id = c.customer_id
        JOIN products p ON ds.product_id = p.product_id
        JOIN users u_del ON ds.deleted_by = u_del.user_id
        WHERE {where_sql}
        ORDER BY ds.deleted_at DESC
    ''', tuple(params))

    for r in rows:
        r['formatted_id'] = f"REC-{r['sale_id']:04d}"
        names = r['customer_name'].strip().split()
        r['initials'] = (names[0][0] + names[-1][0]).upper() if len(names) >= 2 else names[0][:2].upper()
        d_names = r['deleted_by_name'].strip().split()
        r['deleted_initials'] = (d_names[0][0] + d_names[-1][0]).upper() if len(d_names) >= 2 else d_names[0][:2].upper()

    # Deletion Breakdown by Cause
    causes = query_db('''
        SELECT 
            delete_reason,
            COUNT(*) AS count
        FROM deleted_sales
        GROUP BY delete_reason
    ''')

    total_causes = sum([c['count'] for c in causes]) or 1
    cause_breakdown = []
    cause_colors = {
        'Customer Cancelled': '#E53935',
        'Cashier Punch Errors': '#FB8C00',
        'Quality Return / Reseal': '#43A047',
        'Wrong Flavor': '#8E24AA',
        'Other': '#757575'
    }

    for c in causes:
        reason = c['delete_reason'] or 'Other'
        cnt = c['count']
        pct = round((cnt / total_causes) * 100)
        cause_breakdown.append({
            'reason': reason,
            'count': cnt,
            'percentage': pct,
            'color': cause_colors.get(reason, '#FB8C00')
        })

    all_flavors = query_db('SELECT product_id, flavor_name, display_name FROM products WHERE is_active = 1')

    return render_template(
        'deleted_records.html',
        user=user,
        active_tab='deleted_records',
        records=rows,
        all_flavors=all_flavors,
        archived_count=archived_count,
        adjusted_value=adjusted_value,
        reclaimed_packs=reclaimed_packs,
        audited_staff_count=audited_staff_count,
        officer_names=officer_names,
        cause_breakdown=cause_breakdown,
        search=search,
        selected_flavor=flavor_id,
        time_filter=time_filter
    )

@history_bp.route('/deleted-records/restore/<int:archive_id>', methods=['POST'])
@login_required
def restore(archive_id):
    """Allows restoring an archived record back to the active ledger."""
    user = get_current_user()
    archived = query_db('SELECT * FROM deleted_sales WHERE archive_id = %s', (archive_id,), one=True)
    if not archived:
        flash('Archived record not found.', 'danger')
        return redirect(url_for('history.deleted_records'))

    db = get_db()
    with db.cursor() as cur:
        # Re-insert into sales
        cur.execute('''
            INSERT INTO sales (
                sale_id, sale_date, customer_id, product_id, quantity,
                unit_price, amount_paid, payment_method, notes, batch_reference, recorded_by
            ) VALUES (%s, %s, %s, %s, %s, 50.00, %s, 'Cash on Hand', 'Restored from archive', 'BATCH-RESTORE', %s)
        ''', (
            archived['sale_id'],
            archived['sale_date'],
            archived['customer_id'],
            archived['product_id'],
            archived['quantity'],
            archived['amount_paid'],
            user['user_id']
        ))
        # Remove from archive
        cur.execute('DELETE FROM deleted_sales WHERE archive_id = %s', (archive_id,))
        db.commit()

    flash(f"Record REC-{archived['sale_id']:04d} restored successfully to active ledger!", 'success')
    return redirect(url_for('history.deleted_records'))

@history_bp.route('/deleted-records/export/csv')
@login_required
def export_archive_csv():
    rows = query_db('''
        SELECT 
            ds.sale_id,
            ds.sale_date,
            c.customer_name,
            p.display_name AS flavor,
            ds.quantity,
            ds.amount_paid,
            u.full_name AS deleted_by,
            ds.deleted_at,
            ds.delete_reason
        FROM deleted_sales ds
        JOIN customers c ON ds.customer_id = c.customer_id
        JOIN products p ON ds.product_id = p.product_id
        JOIN users u ON ds.deleted_by = u.user_id
        ORDER BY ds.deleted_at DESC
    ''')

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Original ID', 'Transaction Date', 'Customer Name', 'Flavor', 'Quantity', 'Amount Paid', 'Deleted By', 'Deleted Timestamp', 'Audit Reason'])
    for r in rows:
        writer.writerow([
            f"REC-{r['sale_id']:04d}",
            r['sale_date'],
            r['customer_name'],
            r['flavor'],
            r['quantity'],
            f"PHP {r['amount_paid']:.2f}",
            r['deleted_by'],
            r['deleted_at'],
            r['delete_reason']
        ])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    filename = f"Banaging_Chips_Deleted_Archive_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
