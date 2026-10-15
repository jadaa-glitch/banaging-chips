from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response
from app.routes.auth import login_required, get_current_user
from app.database import get_db, query_db
from datetime import date, datetime
import csv
import io

sales_bp = Blueprint('sales', __name__)

@sales_bp.route('/records')
@login_required
def records():
    user = get_current_user()
    
    # Query parameters
    search = request.args.get('search', '').strip()
    flavor_id = request.args.get('flavor', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 7 # matching Figma's 7 active rows per page

    # Today's shift summary
    today = date.today().strftime('%Y-%m-%d')
    today_shift = query_db('''
        SELECT 
            COALESCE(SUM(amount_paid), 0) AS shift_revenue,
            COALESCE(SUM(quantity), 0) AS shift_units
        FROM sales
        WHERE sale_date = %s
    ''', (today,), one=True)
    
    shift_revenue = float(today_shift['shift_revenue']) if today_shift else 0.0
    shift_units = int(today_shift['shift_units']) if today_shift else 0

    # Build filtered query
    where_clauses = ['1=1']
    params = []

    if search:
        where_clauses.append('c.customer_name LIKE %s')
        params.append(f'%{search}%')
    if flavor_id and flavor_id != 'all':
        where_clauses.append('s.product_id = %s')
        params.append(flavor_id)
    if start_date:
        where_clauses.append('s.sale_date >= %s')
        params.append(start_date)
    if end_date:
        where_clauses.append('s.sale_date <= %s')
        params.append(end_date)

    where_sql = ' AND '.join(where_clauses)

    # Count total
    count_row = query_db(f'''
        SELECT COUNT(*) AS total_count
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN products p ON s.product_id = p.product_id
        WHERE {where_sql}
    ''', tuple(params), one=True)
    total_count = count_row['total_count'] if count_row else 0
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    # Query sales rows
    sales_rows = query_db(f'''
        SELECT 
            s.sale_id,
            s.sale_date,
            s.quantity,
            s.unit_price,
            s.amount_paid,
            s.payment_method,
            s.batch_reference,
            s.notes,
            c.customer_name,
            p.product_id,
            p.flavor_name,
            p.display_name,
            p.badge_color,
            u.full_name AS recorded_by_name
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN products p ON s.product_id = p.product_id
        JOIN users u ON s.recorded_by = u.user_id
        WHERE {where_sql}
        ORDER BY s.sale_date DESC, s.sale_id DESC
        LIMIT %s OFFSET %s
    ''', tuple(params + [per_page, offset]))

    for r in sales_rows:
        r['formatted_id'] = f"REC-{r['sale_id']:04d}"

    # Get all flavors for dropdown
    all_flavors = query_db('SELECT product_id, flavor_name, display_name FROM products WHERE is_active = 1')

    return render_template(
        'records.html',
        user=user,
        active_tab='records',
        sales=sales_rows,
        all_flavors=all_flavors,
        total_count=total_count,
        total_pages=total_pages,
        current_page=page,
        shift_revenue=shift_revenue,
        shift_units=shift_units,
        search=search,
        selected_flavor=flavor_id,
        start_date=start_date,
        end_date=end_date
    )

@sales_bp.route('/sales/add', methods=['GET', 'POST'])
@login_required
def add():
    user = get_current_user()
    products = query_db('SELECT * FROM products WHERE is_active = 1 ORDER BY product_id')
    today_str = date.today().strftime('%Y-%m-%d')
    
    # Calculate today's total batches
    batch_stat = query_db('''
        SELECT COALESCE(SUM(amount_paid), 0) AS total_today 
        FROM sales WHERE sale_date = %s
    ''', (today_str,), one=True)
    today_total = float(batch_stat['total_today']) if batch_stat else 0.0

    if request.method == 'POST':
        sale_date = request.form.get('transaction_date', today_str).strip()
        customer_name = request.form.get('customer_name', 'Walk-in Customer').strip()
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity', 1))
        payment_method = request.form.get('payment_method', 'Cash on Hand')
        notes = request.form.get('notes', '').strip()

        # Find product
        product = query_db('SELECT * FROM products WHERE product_id = %s', (product_id,), one=True)
        unit_price = float(product['unit_price']) if product else 50.00
        amount_paid = round(quantity * unit_price, 2)

        db = get_db()
        with db.cursor() as cur:
            # 1. Customer
            cur.execute('SELECT customer_id FROM customers WHERE customer_name = %s', (customer_name,))
            c_row = cur.fetchone()
            if c_row:
                customer_id = c_row['customer_id']
            else:
                cur.execute('INSERT INTO customers (customer_name) VALUES (%s)', (customer_name,))
                customer_id = cur.lastrowid

            # 2. Insert sale
            cur.execute('''
                INSERT INTO sales (
                    sale_date, customer_id, product_id, quantity, unit_price,
                    amount_paid, payment_method, notes, batch_reference, recorded_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                sale_date, customer_id, product_id, quantity, unit_price,
                amount_paid, payment_method, notes, 'BATCH-2025-05B', user['user_id']
            ))
            db.commit()

        flash('Sales record saved successfully!', 'success')
        return redirect(url_for('sales.records'))

    return render_template(
        'add_sale.html',
        user=user,
        active_tab='add_record',
        products=products,
        today_str=today_str,
        today_total=today_total
    )

@sales_bp.route('/sales/edit/<int:sale_id>', methods=['GET', 'POST'])
@login_required
def edit(sale_id):
    user = get_current_user()
    sale = query_db('''
        SELECT 
            s.*,
            c.customer_name,
            p.flavor_name,
            p.display_name,
            u.full_name AS cashier_name
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN products p ON s.product_id = p.product_id
        JOIN users u ON s.recorded_by = u.user_id
        WHERE s.sale_id = %s
    ''', (sale_id,), one=True)

    if not sale:
        flash('Record not found.', 'danger')
        return redirect(url_for('sales.records'))

    sale['formatted_id'] = f"REC-{sale['sale_id']:04d}"
    products = query_db('SELECT * FROM products WHERE is_active = 1 ORDER BY product_id')

    if request.method == 'POST':
        sale_date = request.form.get('transaction_date', sale['sale_date']).strip()
        customer_name = request.form.get('customer_name', sale['customer_name']).strip()
        product_id = request.form.get('product_id', sale['product_id'])
        quantity = int(request.form.get('quantity', sale['quantity']))
        payment_method = request.form.get('payment_method', sale['payment_method'])
        notes = request.form.get('notes', '').strip()

        product = query_db('SELECT * FROM products WHERE product_id = %s', (product_id,), one=True)
        unit_price = float(product['unit_price']) if product else 50.00
        amount_paid = round(quantity * unit_price, 2)

        db = get_db()
        with db.cursor() as cur:
            # Check customer
            cur.execute('SELECT customer_id FROM customers WHERE customer_name = %s', (customer_name,))
            c_row = cur.fetchone()
            if c_row:
                customer_id = c_row['customer_id']
            else:
                cur.execute('INSERT INTO customers (customer_name) VALUES (%s)', (customer_name,))
                customer_id = cur.lastrowid

            cur.execute('''
                UPDATE sales SET
                    sale_date = %s,
                    customer_id = %s,
                    product_id = %s,
                    quantity = %s,
                    unit_price = %s,
                    amount_paid = %s,
                    payment_method = %s,
                    notes = %s
                WHERE sale_id = %s
            ''', (sale_date, customer_id, product_id, quantity, unit_price, amount_paid, payment_method, notes, sale_id))
            db.commit()

        flash(f"Record {sale['formatted_id']} updated successfully!", 'success')
        return redirect(url_for('sales.records'))

    return render_template(
        'edit_sale.html',
        user=user,
        active_tab='records',
        sale=sale,
        products=products
    )

@sales_bp.route('/sales/delete/<int:sale_id>', methods=['POST'])
@login_required
def delete(sale_id):
    user = get_current_user()
    delete_reason = request.form.get('delete_reason', 'Cashier Punch Errors').strip()
    
    sale = query_db('SELECT * FROM sales WHERE sale_id = %s', (sale_id,), one=True)
    if not sale:
        flash('Record not found.', 'danger')
        return redirect(url_for('sales.records'))

    db = get_db()
    with db.cursor() as cur:
        # Move to deleted_sales archive
        cur.execute('''
            INSERT INTO deleted_sales (
                sale_id, sale_date, customer_id, product_id, quantity,
                amount_paid, recorded_by, deleted_by, delete_reason, deleted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            sale['sale_id'],
            sale['sale_date'],
            sale['customer_id'],
            sale['product_id'],
            sale['quantity'],
            sale['amount_paid'],
            sale['recorded_by'],
            user['user_id'],
            delete_reason,
            datetime.now()
        ))

        # Delete from active ledger
        cur.execute('DELETE FROM sales WHERE sale_id = %s', (sale_id,))
        db.commit()

    flash(f"Record REC-{sale_id:04d} moved to Deleted Records archive.", 'warning')
    return redirect(url_for('sales.records'))

@sales_bp.route('/sales/export/csv')
@login_required
def export_csv():
    """Generates CSV download matching Figma export feature."""
    sales_rows = query_db('''
        SELECT 
            s.sale_id,
            s.sale_date,
            c.customer_name,
            p.display_name AS flavor,
            s.quantity,
            s.unit_price,
            s.amount_paid,
            s.payment_method,
            u.full_name AS cashier,
            s.created_at
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN products p ON s.product_id = p.product_id
        JOIN users u ON s.recorded_by = u.user_id
        ORDER BY s.sale_date DESC, s.sale_id DESC
    ''')

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Record ID', 'Transaction Date', 'Customer Name', 'Flavor', 'Quantity (Packs)', 'Unit Price', 'Amount Paid', 'Payment Method', 'Recorded By', 'Timestamp'])
    
    for r in sales_rows:
        writer.writerow([
            f"REC-{r['sale_id']:04d}",
            r['sale_date'],
            r['customer_name'],
            r['flavor'],
            r['quantity'],
            f"PHP {r['unit_price']:.2f}",
            f"PHP {r['amount_paid']:.2f}",
            r['payment_method'],
            r['cashier'],
            r['created_at']
        ])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)

    filename = f"Banaging_Chips_Sales_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
