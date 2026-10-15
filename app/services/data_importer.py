import csv
import io
import openpyxl
from datetime import datetime, date
from app.database import get_db, query_db

def match_flavor(flavor_input, db_flavors):
    """Fuzzy / normalized matcher for flavors in Banaging Chips catalog."""
    if not flavor_input:
        return None
    raw = str(flavor_input).strip().lower()
    for f in db_flavors:
        f_name = f['flavor_name'].lower()
        d_name = f['display_name'].lower()
        if raw == f_name or raw == d_name:
            return f
        if 'original' in raw and 'original' in f_name:
            return f
        if 'cheese' in raw and 'cheese' in f_name:
            return f
        if 'sour' in raw or 'cream' in raw or 'chive' in raw:
            if 'sour cream' in f_name:
                return f
        if 'bbq' in raw or 'barbecue' in raw or 'barbeque' in raw:
            if 'bbq' in f_name:
                return f
    return None

def parse_date(date_val):
    if not date_val:
        return None
    if isinstance(date_val, (date, datetime)):
        return date_val.strftime('%Y-%m-%d')
    s = str(date_val).strip()
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y', '%m-%d-%Y']
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None

def parse_and_validate_file(file_storage, filename):
    """
    Parses CSV or Excel file and returns:
    {
        'total_rows': int,
        'valid_rows': list of dicts,
        'invalid_rows': list of dicts,
        'headers': list
    }
    """
    # Fetch active flavors from DB
    db_flavors = query_db('SELECT product_id, flavor_name, display_name, unit_price FROM products WHERE is_active = 1')
    
    rows_data = []
    
    if filename.lower().endswith('.csv'):
        content = file_storage.read().decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(content))
        for r in reader:
            rows_data.append(r)
    elif filename.lower().endswith(('.xlsx', '.xls')):
        wb = openpyxl.load_workbook(file_storage, data_only=True)
        sheet = wb.active
        headers = []
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(c).strip() if c is not None else f'Col_{idx}' for idx, c in enumerate(row)]
            else:
                if any(c is not None for c in row):
                    row_dict = {}
                    for h, val in zip(headers, row):
                        row_dict[h] = val
                    rows_data.append(row_dict)

    valid_rows = []
    invalid_rows = []

    for idx, raw in enumerate(rows_data, start=2): # 1-based indexing + header
        # Normalize key names
        normalized = {k.strip().lower(): v for k, v in raw.items() if k is not None}
        
        # Extract fields with fallback headers
        raw_date = normalized.get('date') or normalized.get('sale_date') or normalized.get('transaction_date') or normalized.get('tx date')
        raw_customer = normalized.get('customer') or normalized.get('customer_name') or normalized.get('buyer') or normalized.get('client')
        raw_flavor = normalized.get('flavor') or normalized.get('flavor_name') or normalized.get('product') or normalized.get('variant')
        raw_qty = normalized.get('quantity') or normalized.get('qty') or normalized.get('packs') or normalized.get('count')
        raw_price = normalized.get('unit_price') or normalized.get('price') or normalized.get('unit price')
        raw_payment = normalized.get('payment_method') or normalized.get('payment') or 'Cash on Hand'
        raw_notes = normalized.get('notes') or normalized.get('remarks') or ''

        errors = []

        # Validate Date
        parsed_date = parse_date(raw_date)
        if not parsed_date:
            errors.append(f"Invalid or missing date: '{raw_date}'")

        # Validate Customer
        customer_name = str(raw_customer).strip() if raw_customer is not None else ""
        if not customer_name:
            errors.append("Customer name is required")

        # Validate Flavor
        matched_f = match_flavor(raw_flavor, db_flavors)
        if not matched_f:
            errors.append(f"Unrecognized flavor: '{raw_flavor}'. Allowed: Original, Cheese, Sour Cream, BBQ")

        # Validate Quantity
        try:
            qty = int(float(str(raw_qty).replace(',', '')))
            if qty <= 0:
                errors.append(f"Quantity must be greater than 0 (got {qty})")
        except (ValueError, TypeError):
            errors.append(f"Invalid quantity: '{raw_qty}'")
            qty = 0

        # Validate Unit Price
        unit_price = float(matched_f['unit_price']) if matched_f else 50.00
        if raw_price:
            try:
                unit_price = float(str(raw_price).replace(',', '').replace('₱', ''))
            except (ValueError, TypeError):
                pass
        
        amount_paid = round(qty * unit_price, 2)
        
        # Payment Method
        payment_method = 'GCash Transfer' if 'gcash' in str(raw_payment).lower() else 'Cash on Hand'

        row_item = {
            'row_number': idx,
            'sale_date': parsed_date or str(raw_date or ''),
            'customer_name': customer_name,
            'flavor_name': matched_f['display_name'] if matched_f else str(raw_flavor or ''),
            'product_id': matched_f['product_id'] if matched_f else None,
            'quantity': qty,
            'unit_price': unit_price,
            'amount_paid': amount_paid,
            'payment_method': payment_method,
            'notes': str(raw_notes or ''),
            'errors': errors
        }

        if errors:
            invalid_rows.append(row_item)
        else:
            valid_rows.append(row_item)

    return {
        'total_rows': len(rows_data),
        'valid_rows': valid_rows,
        'invalid_rows': invalid_rows
    }

def commit_import_batch(filename, file_type, valid_rows, invalid_rows, user_id):
    """Commits validated rows to the database and logs batch history."""
    db = get_db()
    with db.cursor() as cur:
        # Create Batch Record
        cur.execute('''
            INSERT INTO import_batches (filename, file_type, total_rows, imported_rows, failed_rows, imported_by, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            filename,
            file_type,
            len(valid_rows) + len(invalid_rows),
            len(valid_rows),
            len(invalid_rows),
            user_id,
            'COMPLETED' if not invalid_rows else ('PARTIAL' if valid_rows else 'FAILED')
        ))
        batch_id = cur.lastrowid

        # Insert Valid Sales Records
        for row in valid_rows:
            # 1. Get or create customer
            cur.execute('SELECT customer_id FROM customers WHERE customer_name = %s', (row['customer_name'],))
            cust = cur.fetchone()
            if cust:
                customer_id = cust['customer_id']
            else:
                cur.execute('INSERT INTO customers (customer_name) VALUES (%s)', (row['customer_name'],))
                customer_id = cur.lastrowid

            # 2. Insert sales record
            cur.execute('''
                INSERT INTO sales (
                    sale_date, customer_id, product_id, quantity, unit_price, 
                    amount_paid, payment_method, notes, batch_reference, recorded_by, import_batch_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                row['sale_date'],
                customer_id,
                row['product_id'],
                row['quantity'],
                row['unit_price'],
                row['amount_paid'],
                row['payment_method'],
                row['notes'],
                f"BATCH-IMPORT-{batch_id}",
                user_id,
                batch_id
            ))

        # Insert Invalid Rows into import_errors
        for row in invalid_rows:
            error_msg = '; '.join(row['errors'])
            cur.execute('''
                INSERT INTO import_errors (batch_id, row_number, raw_data, error_message)
                VALUES (%s, %s, %s, %s)
            ''', (
                batch_id,
                row['row_number'],
                f"Customer: {row['customer_name']}, Date: {row['sale_date']}, Flavor: {row['flavor_name']}, Qty: {row['quantity']}",
                error_msg
            ))

        db.commit()
        return batch_id
