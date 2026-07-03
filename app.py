from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import mysql.connector
import os
import uuid
import threading
import time
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ✅ FIXED: Stable secret key + safe localhost session config
app.secret_key = "elite_secret_key_2026_stable"  # Changed to avoid collision
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Keep False for localhost HTTP
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Upload Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(os.path.join(UPLOAD_FOLDER, 'workers'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'services'), exist_ok=True)

def upload_file(file_obj, folder='workers'):
    if file_obj and file_obj.filename != '':
        ext = os.path.splitext(file_obj.filename)[1].lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file_obj.save(save_path)
        return filename
    return None

def get_db_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="@System123",
            database="homeserve_db",
            autocommit=True,
            charset='utf8mb4'
        )
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# ==================== USER ROUTES ====================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/register', methods=['POST'])
def register():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    area = request.form.get('area', '').strip()
    password = request.form.get('password', '')

    if not all([full_name, email, password, area]):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please fill all required fields'})
        return redirect(url_for('auth'))

    conn = get_db_connection()
    if not conn:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Database error'})
        return redirect(url_for('auth'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Email already registered'})
            return redirect(url_for('auth'))

        cursor.execute("""
            INSERT INTO users (full_name, email, phone, area, password) 
            VALUES (%s, %s, %s, %s, %s)
        """, (full_name, email, phone, area, password))
        conn.commit()
        user_id = cursor.lastrowid

        # ✅ FIXED: Set session + force save
        session['user'] = {
            'id': user_id, 'full_name': full_name, 'email': email,
            'phone': phone, 'area': area
        }
        session['role'] = 'customer'
        session.modified = True  # ✅ Critical: forces Flask to commit session

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Registration successful!', 'redirect': url_for('dashboard')})
        return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"Registration error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Registration failed'})
        return redirect(url_for('auth'))
    finally:
        cursor.close()
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please enter email and password'})
        return redirect(url_for('auth'))

    # ✅ ADMIN CHECK
    if email == 'admin@homeserve.com' and password == 'admin123':
        session['admin_logged_in'] = True
        session['role'] = 'admin'
        session.modified = True
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Admin login successful', 'redirect': url_for('admin_dashboard')})
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    if not conn:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Database error'})
        return redirect(url_for('auth'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and user['password'] == password:
            session['user'] = {
                'id': user['id'], 'full_name': user['full_name'],
                'email': user['email'], 'phone': user.get('phone', ''),
                'area': user.get('area', '')
            }
            session['role'] = 'customer'
            session.modified = True  # ✅ Force save
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Login successful!', 'redirect': url_for('dashboard')})
            return redirect(url_for('dashboard'))
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Invalid email or password'})
            return redirect(url_for('auth'))
    except Exception as e:
        print(f"Login error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Login failed'})
        return redirect(url_for('auth'))
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, description, price, image FROM services ORDER BY id LIMIT 5")
        services = cursor.fetchall()
        for s in services:
            if s['image'] and not s['image'].startswith('services/'):
                s['image'] = f"services/{s['image']}"
        
        cursor.execute("""
            SELECT b.*, s.name as service_name
            FROM bookings b
            LEFT JOIN services s ON b.service_id = s.id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC LIMIT 3
        """, (session['user']['id'],))
        recent_bookings = cursor.fetchall()
    except Exception as e:
        print(f"Dashboard error: {e}")
        services, recent_bookings = [], []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('dashboard.html', user=session['user'], services=services, recent_bookings=recent_bookings)

@app.route('/services')
def services():
    if 'user' not in session:
        return redirect(url_for('auth'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM services")
    services_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('services.html', user=session['user'], services=services_list)

@app.route('/my-bookings')
def my_bookings():
    if 'user' not in session:
        return redirect(url_for('auth'))
    
    status_filter = request.args.get('status', 'all')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT b.id, b.status, b.payment_status, b.rating, b.extra_charges, b.base_price,
                   b.booking_date, b.booking_time, b.area, b.created_at,
                   s.name as service_name, w.name as worker_name, w.phone as worker_phone
            FROM bookings b
            LEFT JOIN services s ON b.service_id = s.id
            LEFT JOIN workers w ON b.assigned_worker_id = w.id
            WHERE b.user_id = %s
        """
        params = [session['user']['id']]
        
        if status_filter != 'all':
            query += " AND b.status = %s"
            params.append(status_filter)
            
        query += " ORDER BY b.created_at DESC"
        cursor.execute(query, tuple(params))
        bookings = cursor.fetchall()
        
        # ✅ ADD THIS: Convert timedelta to string format
        for b in bookings:
            if b.get('booking_time') and hasattr(b['booking_time'], 'seconds'):
                total_seconds = b['booking_time'].seconds
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                b['booking_time'] = f"{hours:02d}:{minutes:02d}"
                
    except Exception as e:
        print(f"Bookings error: {e}")
        bookings = []
    finally:
        cursor.close()
        conn.close()
        
    return render_template('my_bookings.html', bookings=bookings, active_filter=status_filter)

# ==================== BOOKING FLOW ====================

@app.route('/book/<int:service_id>', methods=['GET', 'POST'])
def book(service_id):
    workers = []  #

    if 'user' not in session:
        return redirect(url_for('auth'))
    
    user_data = session['user']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    error_msg = None
    service = None
    JOB_DURATION_HOURS = 2

    try:
        cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
        service = cursor.fetchone()
        if not service:
            return redirect(url_for('services'))

        if request.method == 'GET':
            booking_date = request.args.get('date', '').strip()
            booking_time_24 = request.args.get('time', '').strip()
            user_area = (user_data.get('area', '') or '').strip().lower()
            
            AREA_NEIGHBORS = {
                'kundapura': ['koteshwara', 'byndoor', 'baindur'],
                'koteshwara': ['kundapura','kota', 'byndoor'],
                'byndoor': ['kundapura', 'koteshwara', 'baindur'],
                'baindur': ['kundapura', 'byndoor'],
                'kota': ['koteshwara','kundapura','saligrama','udupi'],
                'udupi': ['saligrama','kota','koteshwara','kundapura']
            }
            allowed_areas = {user_area} | {n.lower() for n in AREA_NEIGHBORS.get(user_area, [])}

            cursor.execute("""
                SELECT w.id, w.name, w.photo, w.area, w.verified_badge,
                       COALESCE(w.jobs_today, 0) as jobs_today, w.last_assigned_at
                FROM workers w
                WHERE w.service_id = %s 
                  AND LOWER(TRIM(w.status)) = 'approved' 
            """, (service_id,))
            all_workers = cursor.fetchall()

            local_workers = [w for w in all_workers if (w.get('area') or '').strip().lower() in allowed_areas]
            if not local_workers:
                return render_template('booking.html', service=service, workers=[], user=user_data, error_msg=None)

            cursor.execute("SELECT worker_id FROM service_history WHERE user_id = %s", (user_data['id'],))
            history_ids = {str(r['worker_id']) for r in cursor.fetchall()}
            
            worker_busy_until = {}
            if booking_date and booking_time_24:
                cursor.execute("""
                    SELECT assigned_worker_id, booking_time FROM bookings 
                    WHERE booking_date = %s AND status IN ('Assigned', 'Arrived', 'In Progress')
                """, (booking_date,))
                try:
                    req_h, req_m = map(int, booking_time_24.split(':'))
                    req_min = req_h * 60 + req_m
                    
                    for row in cursor.fetchall():
                        wid = str(row['assigned_worker_id'])
                        if not wid: continue
                        
                        # ✅ FIXED: Handle both timedelta and string formats
                        booking_time_val = row['booking_time']
                        if hasattr(booking_time_val, 'seconds'):
                            # It's a timedelta object - extract hours and minutes
                            total_seconds = booking_time_val.seconds
                            ex_h = total_seconds // 3600
                            ex_m = (total_seconds % 3600) // 60
                        else:
                            # It's a string - parse it
                            ex_h, ex_m = map(int, str(booking_time_val).split(':')[:2])
                        
                        ex_end_min = (ex_h * 60 + ex_m) + (JOB_DURATION_HOURS * 60)
                        
                        if req_min < ex_end_min:
                            free_h, free_m = divmod(ex_end_min, 60)
                            period = "AM" if free_h < 12 else "PM"
                            display_hour = free_h % 12 or 12  # Convert 0 to 12, 13-23 to 1-11
                            worker_busy_until[wid] = f"{display_hour}:{free_m:02d} {period}"
                except ValueError:
                    pass

            def sort_priority(w):
                w_id = str(w['id'])
                w_area = (w.get('area') or '').strip().lower()
                is_busy = w_id in worker_busy_until
                area_tier = 0 if w_area == user_area else 1
                history_flag = 0 if (w_id in history_ids) else 1
                return (is_busy, area_tier, w['jobs_today'], history_flag, w['last_assigned_at'])

            sorted_workers = sorted(local_workers, key=sort_priority)
            
            for w in sorted_workers:
                w_id = str(w['id'])
                w['worked_before'] = w_id in history_ids
                w['busy_until'] = worker_busy_until.get(w_id)
                w['availability_status'] = f"Busy until {w['busy_until']}" if w['busy_until'] else 'Available'

            workers = sorted_workers[:20]
            print(f"✅ Local Workers: {len(workers)} | area='{user_area}' | busy={len(worker_busy_until)}")
            return render_template('booking.html', service=service, workers=workers, user=user_data, error_msg=None)

        # ==================== POST: CREATE BOOKING ====================
        customer_name = request.form.get('customer_name', '').strip()
        phone = request.form.get('phone', '').strip()
        area = request.form.get('area', user_data.get('area', '')).strip()
        address = request.form.get('address', '').strip()
        booking_date = request.form.get('date')
        booking_time = request.form.get('time')
        selected_workers = request.form.getlist('worker_ids')

        if not all([customer_name, phone, area, address, booking_date, booking_time]):
            error_msg = "Please fill in all required fields."
        elif not selected_workers:
            error_msg = "Please select at least one professional."
        else:
            cursor.execute("SELECT price FROM services WHERE id = %s", (service_id,))
            service_info = cursor.fetchone()
            base_price = service_info['price'] if service_info else 0

            cursor.execute("""
                INSERT INTO bookings (user_id, service_id, customer_name, phone, area, address,
                                      booking_date, booking_time, status, base_price, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pending', %s, 'Pending')
            """, (user_data['id'], service_id, customer_name, phone, area, address,
                  booking_date, booking_time, base_price))
            booking_id = cursor.lastrowid

            for w_id in selected_workers:
                cursor.execute("""
                    INSERT INTO broadcast_queue (booking_id, worker_id, status, sent_at)
                    VALUES (%s, %s, 'pending', NOW())
                """, (booking_id, w_id))

            conn.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'redirect': url_for('track_status', booking_id=booking_id)})
            return redirect(url_for('track_status', booking_id=booking_id))

    except Exception as e:
        print(f"Booking error: {e}")
        conn.rollback()
        error_msg = "Something went wrong. Please try again."
        workers = []
    finally:
        cursor.close()
        conn.close()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': False, 'error': error_msg}), 400
    return render_template('booking.html', service=service or {'id': service_id, 'name': 'Service'},
                          workers=workers, user=user_data, error_msg=error_msg)

@app.route('/track/<int:booking_id>')
def track_status(booking_id):
    if 'user' not in session:
        return redirect(url_for('auth'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, s.name as service_name, w.name as worker_name, w.phone as worker_phone,
                   w.photo as worker_photo, w.verified_badge, w.rating
            FROM bookings b
            LEFT JOIN services s ON b.service_id = s.id
            LEFT JOIN workers w ON b.assigned_worker_id = w.id
            WHERE b.id = %s AND b.user_id = %s
        """, (booking_id, session['user']['id']))
        booking = cursor.fetchone()
        
        # ✅ ADD THIS: Convert timedelta to string format
        if booking and booking.get('booking_time') and hasattr(booking['booking_time'], 'seconds'):
            total_seconds = booking['booking_time'].seconds
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            booking['booking_time'] = f"{hours:02d}:{minutes:02d}"
            
        if not booking:
            return redirect(url_for('my_bookings'))
    except Exception as e:
        print(f"Track status error: {e}")
        booking = None
    finally:
        cursor.close()
        conn.close()
    return render_template('track_status.html', booking=booking)

@app.route('/api/booking_status/<int:booking_id>')
def api_booking_status(booking_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.status, b.payment_status, b.assigned_worker_id,
               w.name as worker_name, w.phone as worker_phone, w.photo as worker_photo
        FROM bookings b
        LEFT JOIN workers w ON b.assigned_worker_id = w.id
        WHERE b.id = %s AND b.user_id = %s
    """, (booking_id, session['user']['id']))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(result or {})

@app.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
def payment(booking_id):
    if 'user' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, s.name as service_name, w.name as worker_name
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            LEFT JOIN workers w ON b.assigned_worker_id = w.id
            WHERE b.id = %s AND b.user_id = %s
        """, (booking_id, session['user']['id']))
        booking = cursor.fetchone()
        
        if not booking or booking.get('payment_status') == 'Paid':
            return redirect(url_for('my_bookings'))
            
        if request.method == 'POST':
            method = request.form.get('payment_method', 'Cash')
            cursor.execute("""
                UPDATE bookings 
                SET payment_status = 'Paid', payment_method = %s, paid_at = NOW()
                WHERE id = %s
            """, (method, booking_id))
            conn.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Payment successful!', 'redirect': url_for('my_bookings')})
            return redirect(url_for('my_bookings'))
            
    except Exception as e:
        conn.rollback()
        print(f"Payment error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Payment failed'}), 500
        return redirect(url_for('payment', booking_id=booking_id))
    finally:
        cursor.close()
        conn.close()
        
    return render_template('payment.html', booking=booking)

@app.route('/feedback/<int:booking_id>')
def feedback(booking_id):
    if 'user' not in session:
        return redirect(url_for('auth'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, s.name as service_name, w.name as worker_name
            FROM bookings b
            LEFT JOIN services s ON b.service_id = s.id
            LEFT JOIN workers w ON b.assigned_worker_id = w.id
            WHERE b.id = %s AND b.user_id = %s
        """, (booking_id, session['user']['id']))
        booking = cursor.fetchone()
        
        if not booking or booking['status'] != 'Completed' or booking.get('payment_status') != 'Paid' or booking.get('rating'):
            return redirect(url_for('my_bookings'))
            
    except Exception as e:
        print(f"Feedback fetch error: {e}")
        booking = None
    finally:
        cursor.close()
        conn.close()
    return render_template('feedback.html', booking=booking)

@app.route('/feedback/<int:booking_id>/submit', methods=['POST'])
def submit_feedback(booking_id):
    if 'user' not in session:
        return redirect(url_for('auth'))
    
    try:
        rating = int(request.form.get('rating', 0))
        if not (1 <= rating <= 5): rating = 5
    except (ValueError, TypeError):
        rating = 0
        
    review = request.form.get('review', '').strip()
    has_complaint = 'complaint_category' in request.form
    
    conn = get_db_connection()
    if not conn:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        return redirect(url_for('feedback', booking_id=booking_id))
        
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO feedback (booking_id, user_id, rating, review, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (booking_id, session['user']['id'], rating, review))
        
        cursor.execute("UPDATE bookings SET rating = %s WHERE id = %s", (rating, booking_id))
        
        cursor.execute("""
            UPDATE workers w 
            SET w.rating = COALESCE((
                SELECT AVG(f.rating) FROM feedback f
                JOIN bookings b ON f.booking_id = b.id
                WHERE b.assigned_worker_id = w.id
            ), 0)
            WHERE w.id = (SELECT assigned_worker_id FROM bookings WHERE id = %s AND assigned_worker_id IS NOT NULL)
        """, (booking_id,))
        
        if has_complaint:
            try:
                cursor.execute("""
                    INSERT INTO complaints (booking_id, user_id, category, description, contact_email, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'open', NOW())
                """, (booking_id, session['user']['id'], 
                      request.form.get('complaint_category', ''),
                      request.form.get('complaint_description', '').strip(),
                      request.form.get('complaint_email', '').strip()))
            except Exception as comp_err:
                print(f"⚠️ Complaint skipped: {comp_err}")
        
        conn.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Thank you for your feedback!', 'redirect': url_for('my_bookings')})
        return redirect(url_for('my_bookings'))
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Feedback error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        return redirect(url_for('feedback', booking_id=booking_id))
    finally:
        cursor.close()
        conn.close()

# ==================== WORKER ROUTES ====================

@app.route('/worker/register', methods=['GET', 'POST'])
def worker_register():
    conn = get_db_connection()
    if not conn:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Database error'})
        return redirect(url_for('worker_register'))
    
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            phone = request.form.get('phone', '').strip()
            aadhar = request.form.get('aadhar', '').strip()
            service_id = request.form.get('service_id')
            gender = request.form.get('gender', '')
            experience = request.form.get('experience', 0)
            address = request.form.get('address', '').strip()
            area = request.form.get('area', '').strip()
            
            if not all([name, email, password, phone, aadhar, service_id, gender, area]):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Please fill all required fields'})
                return redirect(url_for('worker_register'))
            
            photo = upload_file(request.files.get('photo')) or 'default.jpg'
            aadhar_front = upload_file(request.files.get('aadhar_front')) or 'default.jpg'
            aadhar_back = upload_file(request.files.get('aadhar_back')) or 'default.jpg'
            
            cursor.execute("SELECT id FROM workers WHERE email = %s", (email,))
            if cursor.fetchone():
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Email already registered'})
                return redirect(url_for('worker_register'))
            
            cursor.execute("""
                INSERT INTO workers (name, email, password, phone, aadhar, service_id, gender, experience,
                                     address, area, photo, aadhar_front, aadhar_back, status, is_online, is_busy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending', 1, 0)
            """, (name, email, password, phone, aadhar, int(service_id), gender, int(experience),
                  address, area, photo, aadhar_front, aadhar_back))
            conn.commit()
            
            new_worker_id = cursor.lastrowid  # ✅ Capture NEW ID
            
            # ✅ FIXED: Set session for NEW worker ONLY + force save
            session['worker_id'] = new_worker_id
            session['worker_name'] = name
            session['role'] = 'worker'
            session.modified = True  # ✅ Critical
            
            # ✅ Return JSON for AJAX flow (toast → redirect)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True, 
                    'message': 'Registration successful! Welcome to HomeServe.', 
                    'redirect': url_for('worker_dashboard')
                })
            # Fallback (shouldn't happen with AJAX)
            return redirect(url_for('worker_dashboard'))
            
        except mysql.connector.IntegrityError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Email already exists'})
            return redirect(url_for('worker_register'))
        except Exception as e:
            print(f"Registration error: {e}")
            conn.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Registration failed'})
            return redirect(url_for('worker_register'))
        finally:
            cursor.close()
            conn.close()
    
    cursor.execute("SELECT id, name FROM services ORDER BY name")
    services = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('worker_register.html', services=services)

@app.route('/worker/login', methods=['GET', 'POST'])
def worker_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Please enter email and password'})
            return redirect(url_for('worker_login'))
            
        conn = get_db_connection()
        if not conn:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Database error'})
            return redirect(url_for('worker_login'))
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM workers WHERE email = %s", (email,))
            worker = cursor.fetchone()
            if worker and worker['password'] == password:
                # ✅ FIXED: Set session + force save
                session['worker_id'] = worker['id']
                session['worker_name'] = worker['name']
                session['role'] = 'worker'
                session.modified = True
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'message': 'Login successful!', 'redirect': url_for('worker_dashboard')})
                return redirect(url_for('worker_dashboard'))
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Invalid email or password'})
                return redirect(url_for('worker_login'))
        except Exception as e:
            print(f"Login error: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Login failed'})
            return redirect(url_for('worker_login'))
        finally:
            cursor.close()
            conn.close()
    return render_template('worker_login.html')

@app.route('/worker/dashboard')
def worker_dashboard():
    # ✅ Strict session check
    if 'worker_id' not in session or session.get('role') != 'worker':
        return redirect(url_for('worker_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        # Fetch worker profile
        cursor.execute("""
            SELECT w.*, s.name as service_name FROM workers w
            LEFT JOIN services s ON w.service_id = s.id WHERE w.id = %s
        """, (session['worker_id'],))
        worker = cursor.fetchone()
        
        if not worker:
            return redirect(url_for('worker_login'))
        
        # Show pending approval screen if not approved
        if worker['status'] != 'Approved':
            approval_info = {
                'office_address': 'HomeServe HQ, 123 Service Lane, Downtown',
                'verification_hours': 'Mon-Sat, 10:00 AM - 5:00 PM',
                'contact_phone': '+91 98765 43210',
                'contact_email': 'support@homeserve.com',
                'required_docs': 'Original Aadhar Card, PAN Card, Service Certificate',
                'note': 'Please visit our office with the documents listed above.'
            }
            return render_template('worker_dashboard.html', worker=worker, show_pending=True, approval_info=approval_info)
        
        # ✅ FIXED: Fetch pending broadcasts (new requests)
        cursor.execute("""
            SELECT b.id, b.status, b.base_price,
                   b.booking_date, 
                   b.booking_time, 
                   b.address,
                   b.area,
                   s.name as service_name, u.full_name as customer_name, u.phone as customer_phone
            FROM bookings b 
            JOIN services s ON b.service_id = s.id 
            JOIN users u ON b.user_id = u.id
            JOIN broadcast_queue bq ON b.id = bq.booking_id
            WHERE bq.worker_id = %s AND bq.status = 'pending' AND b.status IN ('Pending', 'Broadcast')
            ORDER BY bq.sent_at DESC
        """, (session['worker_id'],))
        broadcasts = cursor.fetchall()  # ✅ THIS WAS MISSING!

        for b in broadcasts:
            if b.get('booking_time') and hasattr(b['booking_time'], 'seconds'):
                total_seconds = b['booking_time'].seconds
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                b['booking_time'] = f"{hours:02d}:{minutes:02d}"
        
        # ✅ FIXED: Fetch ACTIVE job ONLY (EXCLUDE 'Completed')
        cursor.execute("""
            SELECT b.id, b.status,
                   b.booking_date, 
                   b.booking_time, 
                   b.address,
                   b.area,
                   s.name as service_name, u.full_name as customer_name, u.phone as customer_phone
            FROM bookings b 
            JOIN services s ON b.service_id = s.id 
            JOIN users u ON b.user_id = u.id
            WHERE b.assigned_worker_id = %s AND b.status IN ('Assigned', 'Arrived', 'In Progress')
            ORDER BY FIELD(b.status, 'Assigned', 'Arrived', 'In Progress') LIMIT 1
        """, (session['worker_id'],))
        active_job = cursor.fetchone()  # ✅ THIS WAS MISSING!
        

        if active_job and active_job.get('booking_time') and hasattr(active_job['booking_time'], 'seconds'):
            total_seconds = active_job['booking_time'].seconds
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            active_job['booking_time'] = f"{hours:02d}:{minutes:02d}"

        # Fetch recent completed jobs (for history section)
        cursor.execute("""
            SELECT b.*, s.name as service_name, u.full_name as customer_name
            FROM bookings b JOIN services s ON b.service_id = s.id JOIN users u ON b.user_id = u.id
            WHERE b.assigned_worker_id = %s AND b.status = 'Completed'
            ORDER BY b.created_at DESC LIMIT 5
        """, (session['worker_id'],))
        recent_jobs = cursor.fetchall()
        
        # Fetch today's stats
        cursor.execute("""
            SELECT COUNT(CASE WHEN status='Completed' THEN 1 END) as completed_today,
                   COALESCE(SUM(CASE WHEN status='Completed' THEN base_price + COALESCE(extra_charges,0) END), 0) as today_earnings
            FROM bookings WHERE assigned_worker_id = %s AND DATE(created_at) = CURDATE()
        """, (session['worker_id'],))
        today_stats = cursor.fetchone() or {}
        
        # Fetch lifetime stats
        cursor.execute("SELECT COUNT(*) as total FROM bookings WHERE assigned_worker_id = %s AND status='Completed'", (session['worker_id'],))
        overall_total = cursor.fetchone()['total'] if cursor.rowcount > 0 else 0
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        worker = None
        broadcasts, active_job, recent_jobs, today_stats = [], None, [], {}
        overall_total = 0
    finally:
        cursor.close()
        conn.close()
        
    return render_template('worker_dashboard.html', worker=worker, show_pending=False, broadcasts=broadcasts,
                          active_job=active_job, recent_jobs=recent_jobs, today_stats=today_stats,
                          overall_stats={'total_completed': overall_total, 'avg_rating': worker.get('rating', 'N/A') if worker else 'N/A'})


@app.route('/worker/profile', methods=['GET', 'POST'])
def worker_profile():
    if 'worker_id' not in session or session.get('role') != 'worker':
        return redirect(url_for('worker_login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM workers WHERE id = %s", (session['worker_id'],))
        worker = cursor.fetchone()
        if not worker:
            return redirect(url_for('worker_login'))
        cursor.execute("SELECT name FROM services WHERE id = %s", (worker['service_id'],))
        service = cursor.fetchone()
        worker['service_name'] = service['name'] if service else 'Unknown'
        
        if request.method == 'POST':
            phone = request.form.get('phone', worker.get('phone', '')).strip()
            area = request.form.get('area', worker.get('area', '')).strip()
            address = request.form.get('address', worker.get('address', '')).strip()
            experience = request.form.get('experience', worker.get('experience', '')).strip()
            photo_file = request.files.get('photo')
            photo = worker.get('photo')
            
            if photo_file and photo_file.filename != '':
                new_photo = upload_file(photo_file, 'workers')
                if new_photo:
                    photo = new_photo
            
            # ✅ FIXED: Added experience to the tuple (6 values for 6 placeholders)
            cursor.execute("""
                UPDATE workers SET phone = %s, area = %s, address = %s, experience = %s, photo = %s WHERE id = %s
            """, (phone, area, address, experience, photo, session['worker_id']))
            conn.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Profile updated successfully!'})
            
            # ✅ FIXED: Added success parameter to trigger toast
            return redirect(url_for('worker_profile', success='updated'))
            
    except Exception as e:
        print(f"Profile error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Update failed'})
        return redirect(url_for('worker_profile', error='update_failed'))
    finally:
        cursor.close()
        conn.close()
    
    return render_template('worker_profile.html', worker=worker)


@app.route('/worker/schedule', methods=['GET', 'POST'])
def worker_schedule():
    if 'worker_id' not in session or session.get('role') != 'worker':
        return redirect(url_for('worker_login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        booking_id = request.form.get('booking_id')
        new_status = request.form.get('new_status')
        extra_charges = float(request.form.get('extra_charges', 0) or 0)
        extra_note = request.form.get('extra_note', '').strip()
        
        # ✅ SAFETY: Validate inputs
        if not booking_id or not new_status:
            print(f"❌ Missing booking_id or new_status")
            return redirect(url_for('worker_schedule'))
        
        try:
            booking_id = int(booking_id)  # ✅ Convert to int
            print(f"🔍 Worker {session['worker_id']} updating booking #{booking_id} to '{new_status}'")
            
            if new_status == 'Completed':
                cursor.execute("""
                    UPDATE bookings SET status = 'Completed', extra_charges = %s, extra_charges_note = %s
                    WHERE id = %s AND assigned_worker_id = %s
                """, (extra_charges, extra_note, booking_id, session['worker_id']))
            elif new_status == 'Arrived':
                cursor.execute("UPDATE bookings SET status = 'Arrived' WHERE id = %s AND assigned_worker_id = %s",
                               (booking_id, session['worker_id']))
            elif new_status == 'In Progress':
                cursor.execute("UPDATE bookings SET status = 'In Progress' WHERE id = %s AND assigned_worker_id = %s",
                               (booking_id, session['worker_id']))
            
            # ✅ CRITICAL: Verify only ONE row updated
            rows_updated = cursor.rowcount
            print(f"✅ Rows updated: {rows_updated}")
            
            if rows_updated == 0:
                print(f"⚠️ No rows updated - booking #{booking_id} not found")
            elif rows_updated > 1:
                print(f"🚨 ERROR: {rows_updated} rows updated! This is a bug!")
            
            conn.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': f'Status updated to {new_status}'})
            return redirect(url_for('worker_schedule'))
            
        except ValueError:
            print(f"❌ Invalid booking_id: {booking_id}")
            return redirect(url_for('worker_schedule'))
        except Exception as e:
            print(f"❌ Schedule update error: {e}")
            conn.rollback()
            return redirect(url_for('worker_schedule'))
    
    try:
        cursor.execute("""
            SELECT b.id, b.status, b.payment_status, b.customer_name, b.phone, b.address, b.area, 
                b.booking_date, b.booking_time, b.base_price, b.extra_charges, s.name as service_name
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            WHERE b.assigned_worker_id = %s 
            AND b.status IN ('Assigned', 'Arrived', 'In Progress', 'Completed')
            ORDER BY FIELD(b.status, 'Assigned', 'Arrived', 'In Progress', 'Completed'),
                    b.booking_date DESC, b.booking_time ASC
        """, (session['worker_id'],))
        jobs = cursor.fetchall()

        # ✅ ADD THIS: Convert timedelta to string format
        for job in jobs:
            if job.get('booking_time') and hasattr(job['booking_time'], 'seconds'):
                total_seconds = job['booking_time'].seconds
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                job['booking_time'] = f"{hours:02d}:{minutes:02d}"
            
    except Exception as e:
        print(f"Schedule fetch error: {e}")
        jobs = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('worker_schedule.html', jobs=jobs)

@app.route('/worker/respond/<int:booking_id>/<action>')
def worker_respond(booking_id, action):
    if 'worker_id' not in session or session.get('role') != 'worker':
        return redirect(url_for('worker_login'))
    worker_id = session['worker_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM broadcast_queue WHERE booking_id = %s AND worker_id = %s AND status = 'pending'
        """, (booking_id, worker_id))
        if not cursor.fetchone():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Invalid or expired request'})
            return redirect(url_for('worker_dashboard'))
        new_status = 'accepted' if action == 'accept' else 'rejected'
        cursor.execute("""
            UPDATE broadcast_queue SET status = %s, responded_at = NOW()
            WHERE booking_id = %s AND worker_id = %s
        """, (new_status, booking_id, worker_id))
        if action == 'accept':
            cursor.execute("""
                UPDATE bookings SET assigned_worker_id = %s, status = 'Assigned'
                WHERE id = %s AND assigned_worker_id IS NULL
            """, (worker_id, booking_id))
            if cursor.rowcount > 0:
                cursor.execute("UPDATE workers SET is_busy = 1 WHERE id = %s", (worker_id,))
                cursor.execute("""
                    UPDATE broadcast_queue SET status = 'rejected', responded_at = NOW()
                    WHERE booking_id = %s AND worker_id != %s AND status = 'pending'
                """, (booking_id, worker_id))
                conn.commit()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'message': 'Job accepted!', 'redirect': url_for('worker_dashboard')})
                return redirect(url_for('worker_dashboard'))
            else:
                conn.commit()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Job already taken'})
                return redirect(url_for('worker_dashboard'))
        else:
            cursor.execute("""
                SELECT COUNT(*) as pending, SUM(CASE WHEN status='accepted' THEN 1 END) as accepted
                FROM broadcast_queue WHERE booking_id = %s
            """, (booking_id,))
            counts = cursor.fetchone()
            if counts['accepted'] == 0 and counts['pending'] == 0:
                cursor.execute("UPDATE bookings SET status = 'Pending' WHERE id = %s", (booking_id,))
            conn.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Request declined', 'redirect': url_for('worker_dashboard')})
            return redirect(url_for('worker_dashboard'))
    except Exception as e:
        print(f"Respond error: {e}")
        conn.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Action failed'})
        return redirect(url_for('worker_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/worker/api/toggle_online', methods=['POST'])
def toggle_online():
    if 'worker_id' not in session or session.get('role') != 'worker':
        return jsonify({'success': False, 'error': 'Not authenticated'}), 403
    is_online = 1 if request.json.get('is_online') else 0
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE workers SET is_online = %s WHERE id = %s", (is_online, session['worker_id']))
        conn.commit()
        return jsonify({'success': True, 'is_online': bool(is_online)})
    except Exception as e:
        print(f"Toggle error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/worker/logout')
def worker_logout():
    session.clear()
    return redirect(url_for('worker_login'))

@app.route('/worker/history')
def worker_history():
    if 'worker_id' not in session or session.get('role') != 'worker':
        return redirect(url_for('worker_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # ✅ Fetch completed jobs + feedback + complaints in ONE query
        cursor.execute("""
            SELECT 
                b.id, b.booking_date, b.booking_time, b.address, b.area, 
                b.base_price, COALESCE(b.extra_charges, 0) as extra_charges,
                s.name as service_name, u.full_name as customer_name,
                f.rating, f.review as customer_review,
                c.id as complaint_id, c.category as complaint_category, 
                c.description as complaint_description, c.status as complaint_status,
                c.created_at as complaint_date
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN users u ON b.user_id = u.id
            LEFT JOIN feedback f ON b.id = f.booking_id
            LEFT JOIN complaints c ON b.id = c.booking_id
            WHERE b.assigned_worker_id = %s AND b.status = 'Completed'
            ORDER BY b.booking_date DESC, b.booking_time DESC
            LIMIT 50
        """, (session['worker_id'],))
        rows = cursor.fetchall()
        
        # ✅ Convert timedelta to string format
        for row in rows:
            if row.get('booking_time') and hasattr(row['booking_time'], 'seconds'):
                total_seconds = row['booking_time'].seconds
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                row['booking_time'] = f"{hours:02d}:{minutes:02d}"
        
        # ✅ Group complaints per booking (one booking can have multiple complaints)
        history = {}
        for row in rows:
            bid = row['id']
            if bid not in history:
                history[bid] = {
                    **row,
                    'complaints': []
                }
            if row['complaint_id']:
                history[bid]['complaints'].append({
                    'id': row['complaint_id'],
                    'category': row['complaint_category'],
                    'description': row['complaint_description'],
                    'status': row['complaint_status'],
                    'date': row['complaint_date']
                })
        
        history_list = list(history.values())
        
        # ✅ Calculate stats
        total_jobs = len(history_list)
        total_earned = sum(h['base_price'] + h['extra_charges'] for h in history_list)
        ratings = [h['rating'] for h in history_list if h['rating'] is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
    except Exception as e:
        print(f"Worker history error: {e}")
        history_list = []
        total_jobs = 0
        total_earned = 0
        avg_rating = 0
    finally:
        cursor.close()
        conn.close()
        
    return render_template('worker_history.html', history=history_list, 
                           total_jobs=total_jobs, total_earned=total_earned, avg_rating=avg_rating)

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == 'admin' and request.form.get('password') == 'admin123':
            session['admin_logged_in'] = True
            session['role'] = 'admin'
            session.modified = True
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Admin login successful', 'redirect': url_for('admin_dashboard')})
            return redirect(url_for('admin_dashboard'))
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Invalid admin credentials'})
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in') or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count'] or 0
        cursor.execute("SELECT COUNT(*) as count FROM workers")
        total_workers = cursor.fetchone()['count'] or 0
        cursor.execute("SELECT COUNT(*) as count FROM services")
        total_services = cursor.fetchone()['count'] or 0
        cursor.execute("SELECT COUNT(*) as count FROM bookings")
        total_bookings = cursor.fetchone()['count'] or 0
    except Exception as e:
        print(f"Admin dashboard error: {e}")
        total_users = total_workers = total_services = total_bookings = 0
    finally:
        cursor.close()
        conn.close()
    return render_template('admin_dashboard.html', stats={'users': total_users, 'workers': total_workers,
                                                          'services': total_services, 'bookings': total_bookings})

@app.route('/admin/verify-workers', methods=['GET', 'POST'])
def admin_verify_workers():
    if not session.get('admin_logged_in') or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        worker_id = request.form.get('worker_id')
        action = request.form.get('action')
        note = request.form.get('verification_note', '').strip()
        
        print(f"🔍 Admin action: {action} on worker_id={worker_id}")  # Debug log
        
        if not worker_id:
            return jsonify({'success': False, 'message': 'Invalid worker ID'}), 400
        
        try:
            if action == 'approve':
                # ✅ FIXED: Separate queries to ensure both updates work
                cursor.execute("UPDATE workers SET status='Approved' WHERE id=%s", (worker_id,))
                cursor.execute("UPDATE workers SET verified_badge=1 WHERE id=%s", (worker_id,))
                cursor.execute("UPDATE workers SET verification_note='verified' WHERE id=%s", (worker_id,))
                print(f"✅ Worker {worker_id} approved and verified_badge set to 1")
                
            elif action == 'reject':
                cursor.execute("UPDATE workers SET status='Rejected', is_online=0, verification_note=%s WHERE id=%s",
                               (note or 'Documents not verified', worker_id))
                
            conn.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': f'Worker {action}d', 'redirect': url_for('admin_verify_workers')})
            return redirect(url_for('admin_verify_workers'))
            
        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': f'Update failed: {str(e)}'})
            return redirect(url_for('admin_verify_workers'))
        finally:
            cursor.close()
            conn.close()
    
    try:
        cursor.execute("SELECT w.*, s.name as service_name FROM workers w LEFT JOIN services s ON w.service_id = s.id ORDER BY w.created_at DESC")
        workers = cursor.fetchall()
    except:
        workers = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin_verify.html', workers=workers)

@app.route('/admin/manage', methods=['GET', 'POST'])
def manage_services():
    if not session.get('admin_logged_in') or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            img = upload_file(request.files.get('image'), 'services')
            cursor.execute("INSERT INTO services (name, description, price, image) VALUES (%s, %s, %s, %s)",
                           (request.form['name'], request.form['description'], request.form['price'], img))
        elif action == 'update':
            sid = request.form.get('service_id')
            img_file = request.files.get('image')
            if img_file and img_file.filename != '':
                cursor.execute("SELECT image FROM services WHERE id = %s", (sid,))
                old = cursor.fetchone()['image']
                if old:
                    try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], 'services', old))
                    except: pass
                img = upload_file(img_file, 'services')
                cursor.execute("UPDATE services SET name=%s, description=%s, price=%s, image=%s WHERE id=%s",
                               (request.form['name'], request.form['description'], request.form['price'], img, sid))
            else:
                cursor.execute("UPDATE services SET name=%s, description=%s, price=%s WHERE id=%s",
                               (request.form['name'], request.form['description'], request.form['price'], sid))
        elif action == 'delete':
            sid = request.form.get('service_id')
            cursor.execute("SELECT image FROM services WHERE id = %s", (sid,))
            res = cursor.fetchone()
            if res and res['image']:
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], 'services', res['image']))
                except: pass
            cursor.execute("DELETE FROM services WHERE id=%s", (sid,))
        conn.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Service updated', 'redirect': url_for('manage_services')})
        return redirect(url_for('manage_services'))
    cursor.execute("SELECT *, (SELECT COUNT(*) FROM workers WHERE service_id = services.id) as worker_count FROM services")
    services = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_services.html', services=services)

@app.route('/admin/manage-bookings', methods=['GET', 'POST'])
def admin_manage_bookings():
    if not session.get('admin_logged_in') or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            booking_id = request.form.get('booking_id')
            worker_id = request.form.get('worker_id')
            new_status = request.form.get('new_status')
            
            if action == 'assign' and worker_id:
                cursor.execute("UPDATE bookings SET assigned_worker_id=%s, status='Assigned' WHERE id=%s", (worker_id, booking_id))
            elif action == 'complete':
                cursor.execute("UPDATE bookings SET status='Completed' WHERE id=%s", (booking_id,))
            elif action == 'cancel':
                # ✅ FIXED: Auto-syncs payment_status when cancelled
                cursor.execute("UPDATE bookings SET status='Cancelled', payment_status='Cancelled' WHERE id=%s", (booking_id,))
            elif action == 'update_status' and new_status:
                cursor.execute("UPDATE bookings SET status=%s WHERE id=%s", (new_status, booking_id))
            conn.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Booking updated', 'redirect': url_for('admin_manage_bookings')})
            return redirect(url_for('admin_manage_bookings'))
        except Exception as e:
            conn.rollback()
            print(f"❌ Booking update error: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)}), 500
            return redirect(url_for('admin_manage_bookings'))
        finally:
            cursor.close()
            conn.close()
            
    try:
    # 1️⃣ Fetch main booking data
        cursor.execute("""
            SELECT b.id, b.status, b.booking_date, b.booking_time, b.address, b.area,
                b.payment_status, b.base_price, COALESCE(b.extra_charges, 0) as extra_charges,
                b.extra_charges_note,
                u.full_name as customer_name, u.phone as customer_phone,
                w.name as worker_name, w.phone as worker_phone,
                s.name as service_name, b.created_at,
                f.rating as feedback_rating
            FROM bookings b
            LEFT JOIN users u ON b.user_id = u.id
            LEFT JOIN workers w ON b.assigned_worker_id = w.id
            LEFT JOIN services s ON b.service_id = s.id
            LEFT JOIN feedback f ON b.id = f.booking_id
            ORDER BY b.created_at DESC
        """)
        bookings = cursor.fetchall()
        
        # ✅ ADD THIS: Convert timedelta to string format
        for b in bookings:
            if b.get('booking_time') and hasattr(b['booking_time'], 'seconds'):
                total_seconds = b['booking_time'].seconds
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                b['booking_time'] = f"{hours:02d}:{minutes:02d}"
            
            # 2️⃣ Fetch complaints separately (prevents duplicate rows)
            cursor.execute("""
                SELECT booking_id, id, category, description, status, DATE(created_at) as date
                FROM complaints ORDER BY created_at DESC
            """)
        all_complaints = cursor.fetchall()
        
        # 3️⃣ Group complaints by booking_id
        complaints_by_booking = {}
        for c in all_complaints:
            bid = c['booking_id']
            if bid not in complaints_by_booking:
                complaints_by_booking[bid] = []
            complaints_by_booking[bid].append({
                'category': c['category'],
                'description': c['description'],
                'status': c['status'],
                'date': str(c['date'])
            })
            
        # 4️⃣ Attach complaints & count to each booking
        for b in bookings:
            b['complaints'] = complaints_by_booking.get(b['id'], [])
            b['complaint_count'] = len(b['complaints'])
            
        cursor.execute("SELECT id, name FROM workers WHERE LOWER(TRIM(status))='approved' ORDER BY name")
        workers = cursor.fetchall()
        
    except Exception as e:
        print(f"⚠️ Bookings fetch error: {e}")
        bookings, workers = [], []
    finally:
        cursor.close()
        conn.close()
        
    return render_template('admin_manage_bookings.html', bookings=bookings, workers=workers)


@app.route('/admin/manage-users', methods=['GET', 'POST'])
def manage_users():
    if not session.get('admin_logged_in') or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            user_id = request.form.get('user_id')
            
            if action == 'delete':
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            elif action == 'block':
                cursor.execute("UPDATE users SET is_active = 0 WHERE id = %s", (user_id,))
            elif action == 'activate':
                cursor.execute("UPDATE users SET is_active = 1 WHERE id = %s", (user_id,))
                
            conn.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': f'User {action} successful', 'redirect': url_for('manage_users')})
            return redirect(url_for('manage_users'))
        except Exception as e:
            conn.rollback()
            print(f"❌ User action error: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)}), 500
            return redirect(url_for('manage_users'))
        finally:
            cursor.close()
            conn.close()

    try:
        try:
            cursor.execute("""
                SELECT id, full_name, email, phone, area, created_at, 
                       COALESCE(is_active, 1) as is_active 
                FROM users ORDER BY created_at DESC
            """)
            users = cursor.fetchall()
        except:
            cursor.execute("SELECT id, full_name, email, phone, area, created_at FROM users ORDER BY created_at DESC")
            users = cursor.fetchall()
            for u in users: u['is_active'] = True

        for u in users:
            cursor.execute("""
                SELECT COUNT(*) as cnt, MAX(created_at) as last 
                FROM bookings WHERE user_id = %s
            """, (u['id'],))
            stats = cursor.fetchone()
            u['booking_count'] = stats['cnt'] if stats else 0
            u['last_booking'] = stats['last'] if stats else None
            
    except Exception as e:
        print(f"❌ Users fetch error: {e}")
        users = []
    finally:
        cursor.close()
        conn.close()
        
    return render_template('admin_manage_users.html', users=users)

# ==================== API ROUTES ====================

@app.route('/api/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking_api(booking_id):
    if 'user' not in session and not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # ✅ FIXED: Sets payment_status='Cancelled' automatically
        cursor.execute("""
            UPDATE bookings SET status = 'Cancelled', payment_status = 'Cancelled'
            WHERE id = %s AND status = 'Pending'
        """, (booking_id,))
        if cursor.rowcount > 0:
            cursor.execute("""
                UPDATE broadcast_queue SET status = 'rejected', responded_at = NOW()
                WHERE booking_id = %s AND status = 'pending'
            """, (booking_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Booking cancelled'})
        return jsonify({'success': False, 'error': 'Cannot cancel'}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()



@app.route('/get-user')
def get_user():
    if 'user' not in session:
        return jsonify({}), 401
    return jsonify(session['user'])


@app.route('/api/process_booking_expiry')
def process_booking_expiry():
    """Hybrid expiry: rebroadcast at 15min, cancel at 30min"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ============================================
        # PHASE 1: REBROADCAST (15-30 min old bookings)
        # ============================================
        cursor.execute("""
            SELECT b.id, b.service_id, b.area, b.booking_date, b.booking_time
            FROM bookings b
            LEFT JOIN broadcast_queue bq ON b.id = bq.booking_id AND bq.status = 'accepted'
            WHERE b.status IN ('Pending', 'Broadcast')
              AND b.created_at < NOW() - INTERVAL 15 MINUTE
              AND b.created_at >= NOW() - INTERVAL 30 MINUTE
              AND bq.id IS NULL
        """)
        to_rebroadcast = cursor.fetchall()
        
        rebroadcast_count = 0
        for booking in to_rebroadcast:
            # Get workers who already received this booking
            cursor.execute("SELECT worker_id FROM broadcast_queue WHERE booking_id = %s", 
                          (booking['id'],))
            existing_ids = [str(r['worker_id']) for r in cursor.fetchall()]
            
            # Find 3 NEW workers (same service, approved, verified, same area)
            if existing_ids:
                placeholders = ','.join(['%s'] * len(existing_ids))
                query = f"""
                    SELECT id, area FROM workers
                    WHERE service_id = %s 
                      AND LOWER(TRIM(status)) = 'approved'
                      AND COALESCE(verified_badge, 0) = 1
                      AND id NOT IN ({placeholders})
                    ORDER BY 
                      CASE WHEN LOWER(TRIM(area)) = LOWER(TRIM(%s)) THEN 0 ELSE 1 END,
                      is_online DESC,
                      created_at DESC
                    LIMIT 3
                """
                params = [booking['service_id']] + existing_ids + [booking['area']]
            else:
                query = """
                    SELECT id, area FROM workers
                    WHERE service_id = %s 
                      AND LOWER(TRIM(status)) = 'approved'
                      AND COALESCE(verified_badge, 0) = 1
                    ORDER BY 
                      CASE WHEN LOWER(TRIM(area)) = LOWER(TRIM(%s)) THEN 0 ELSE 1 END,
                      is_online DESC,
                      created_at DESC
                    LIMIT 3
                """
                params = [booking['service_id'], booking['area']]
            
            cursor.execute(query, params)
            new_workers = cursor.fetchall()
            
            if new_workers:
                # Mark old pending broadcasts as expired (workers won't see them anymore)
                cursor.execute("""
                    UPDATE broadcast_queue SET status = 'expired', responded_at = NOW()
                    WHERE booking_id = %s AND status = 'pending'
                """, (booking['id'],))
                
                # Add new broadcasts
                for w in new_workers:
                    cursor.execute("""
                        INSERT INTO broadcast_queue (booking_id, worker_id, status, sent_at)
                        VALUES (%s, %s, 'pending', NOW())
                    """, (booking['id'], w['id']))
                
                # Update booking status to indicate rebroadcast
                cursor.execute("UPDATE bookings SET status = 'Broadcast' WHERE id = %s", 
                              (booking['id'],))
                
                rebroadcast_count += 1
                print(f"🔄 REBROADCAST booking #{booking['id']} to {len(new_workers)} new workers")
            else:
                print(f"⚠️ No new workers available for booking #{booking['id']}")
        
        # ============================================
        # PHASE 2: AUTO-CANCEL (30+ min old bookings)
        # ============================================
        cursor.execute("""
            SELECT b.id FROM bookings b
            LEFT JOIN broadcast_queue bq ON b.id = bq.booking_id AND bq.status = 'accepted'
            WHERE b.status IN ('Pending', 'Broadcast')
              AND b.created_at < NOW() - INTERVAL 30 MINUTE
              AND bq.id IS NULL
        """)
        to_cancel = cursor.fetchall()
        
        cancel_count = 0
        for booking in to_cancel:
            cursor.execute("""
                UPDATE bookings SET status = 'Cancelled', payment_status = 'Cancelled'
                WHERE id = %s
            """, (booking['id'],))
            
            cursor.execute("""
                UPDATE broadcast_queue SET status = 'expired', responded_at = NOW()
                WHERE booking_id = %s AND status IN ('pending')
            """, (booking['id'],))
            
            cancel_count += 1
            print(f"❌ AUTO-CANCELLED expired booking #{booking['id']}")
        
        conn.commit()
        
        if rebroadcast_count > 0 or cancel_count > 0:
            print(f"✅ Processed: {rebroadcast_count} rebroadcasts, {cancel_count} cancellations")
        
        return jsonify({
            'success': True, 
            'rebroadcast': rebroadcast_count, 
            'cancelled': cancel_count
        })
        
    except Exception as e:
        print(f"❌ Expiry processing error: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


import threading
import time

def auto_process_expiry():
    """Background task: runs every 60 seconds"""
    # Wait 10 seconds for Flask to fully start
    time.sleep(10)
    while True:
        try:
            import requests as req_lib
            req_lib.get('http://localhost:5000/api/process_booking_expiry', timeout=10)
        except Exception as e:
            pass  # Silent fail - don't spam console
        time.sleep(60)  # Run every 60 seconds

# Start background thread (only when running directly)
if __name__ == '__main__':
    threading.Thread(target=auto_process_expiry, daemon=True).start()
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)