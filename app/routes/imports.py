from flask import Blueprint, request, jsonify, session, Response
from app.routes.auth import login_required, get_current_user
from app.services.data_importer import parse_and_validate_file, commit_import_batch
from werkzeug.utils import secure_filename
import io
import csv

imports_bp = Blueprint('imports', __name__)

@imports_bp.route('/import/validate', methods=['POST'])
@login_required
def validate_import():
    """Receives file and returns validation preview for the modal."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected.'}), 400
        
    filename = secure_filename(file.filename)
    if not (filename.lower().endswith('.csv') or filename.lower().endswith(('.xlsx', '.xls'))):
        return jsonify({'success': False, 'error': 'Only CSV and Excel (.xlsx, .xls) files are supported.'}), 400

    try:
        result = parse_and_validate_file(file, filename)
        # Store in session for confirmation
        session['pending_import'] = {
            'filename': filename,
            'file_type': 'EXCEL' if filename.lower().endswith(('.xlsx', '.xls')) else 'CSV',
            'valid_rows': result['valid_rows'],
            'invalid_rows': result['invalid_rows']
        }
        return jsonify({
            'success': True,
            'filename': filename,
            'total_rows': result['total_rows'],
            'valid_count': len(result['valid_rows']),
            'invalid_count': len(result['invalid_rows']),
            'valid_rows': result['valid_rows'][:10], # sample preview
            'invalid_rows': result['invalid_rows']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to process file: {str(e)}'}), 500

@imports_bp.route('/import/commit', methods=['POST'])
@login_required
def commit_import():
    """Commits validated rows stored in session to MySQL."""
    user = get_current_user()
    pending = session.get('pending_import')
    if not pending or not pending.get('valid_rows'):
        return jsonify({'success': False, 'error': 'No valid records ready to commit.'}), 400

    try:
        batch_id = commit_import_batch(
            filename=pending['filename'],
            file_type=pending['file_type'],
            valid_rows=pending['valid_rows'],
            invalid_rows=pending['invalid_rows'],
            user_id=user['user_id']
        )
        session.pop('pending_import', None)
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'imported_count': len(pending['valid_rows']),
            'error_count': len(pending['invalid_rows'])
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500

@imports_bp.route('/import/template/csv')
@login_required
def download_template_csv():
    """Provides a sample CSV template for users to populate."""
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Date', 'Customer Name', 'Flavor', 'Quantity', 'Unit Price', 'Payment Method', 'Notes'])
    writer.writerow(['2025-05-18', 'Juan Dela Cruz', 'Cheese Delight', '10', '50.00', 'Cash on Hand', 'Walk-in bulk purchase'])
    writer.writerow(['2025-05-18', 'Angelica Reyes', 'Original Sweet', '5', '50.00', 'Cash on Hand', 'Regular pack'])
    writer.writerow(['2025-05-18', 'Roberto Tan', 'Smoked BBQ', '12', '50.00', 'GCash Transfer', 'Pasalubong order'])
    writer.writerow(['2025-05-17', 'Marites Gonzales', 'Sour Cream & Chives', '8', '50.00', 'Cash on Hand', 'Extra bags'])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=Banaging_Chips_Sample_Import.csv"}
    )
