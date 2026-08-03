import os
import secrets
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

ROLE_LABELS = db.ROLE_LABELS

# --- Auth & Access Control ---

def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Login required.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_role(*roles):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                flash("Login required.", "error")
                return redirect(url_for('login'))
            user_role = session.get('user_role')
            if user_role not in roles:
                flash("Access denied.", "error")
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.before_request
def inject_user():
    if 'user_id' in session:
        g.user_id = session['user_id']
        g.username = session['username']
        g.user_role = session['user_role']
        app.jinja_env.globals['current_role'] = g.user_role
        app.jinja_env.globals['role_labels'] = ROLE_LABELS
    else:
        g.user_id = None
        g.username = None
        g.user_role = None

from flask import g

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = db.verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_role'] = user['role']
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid username or password.", "error")
    
    # First-time: if no users exist, create one
    users = db.list_users()
    if not users and request.method == 'GET':
        flash("No users yet. Create the first super admin account.", "info")
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if db.list_users():
        flash("Registration closed.", "error")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or len(username) < 3:
            flash("Username must be 3+ chars.", "error")
        elif not password or len(password) < 6:
            flash("Password must be 6+ chars.", "error")
        else:
            try:
                db.create_user(username, password, 'super_admin')
                flash(f"Account created. Log in.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                flash(f"Error: {str(e)}", "error")
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('login'))

# --- Pages ---

@app.route('/')
@require_login
def home():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@require_login
def dashboard():
    today = date.today().isoformat()
    # Summary stats
    recent_events = db.list_events(date_from=str(date(2026, 1, 1)), limit=5)
    total_expenses_row = db.list_expenses()
    total_expenses = sum(e['amount'] for e in total_expenses_row)
    
    return render_template('dashboard.html', 
        recent_events=recent_events,
        total_expenses=total_expenses,
        today=today)

@app.route('/events')
@require_login
def events_page():
    return render_template('events.html')

@app.route('/api/events')
@require_login
def api_events():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    result = db.list_events(date_from, date_to, limit, offset)
    return jsonify(result)

@app.route('/events/new', methods=['GET', 'POST'])
@require_login
def new_event():
    if request.method == 'POST':
        date_str = request.form.get('date')
        name = request.form.get('name', '').strip()
        event_type = request.form.get('event_type')
        note = request.form.get('note', '').strip() or None
        
        if not all([date_str, name, event_type]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_event'))
        
        try:
            event_id = db.insert_event(date_str, name, event_type, note, g.username)
            flash(f"Event created.", "success")
            return redirect(url_for('event_detail', event_id=event_id))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template('new_event.html')

@app.route('/events/<int:event_id>')
@require_login
def event_detail(event_id):
    event = db.get_event(event_id)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for('events_page'))
    
    fights = db.list_fights_for_event(event_id)
    revenue = db.list_event_revenue(event_id)
    summary = db.get_event_summary(event_id)
    
    return render_template('event_detail.html', 
        event=event, fights=fights, revenue=revenue, summary=summary)

@app.route('/api/events/<int:event_id>/fights', methods=['POST'])
@require_login
def api_add_fight(event_id):
    event = db.get_event(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    
    data = request.get_json() or {}
    fight_number = data.get('fight_number', type=int)
    meron = data.get('meron', '').strip()
    wala = data.get('wala', '').strip()
    winner = data.get('winner')
    plasada = data.get('plasada', type=float)
    pit_fee = data.get('pit_fee', type=float)
    notes = data.get('notes', '').strip() or None
    
    if not all([fight_number, meron, wala]):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        fight_id = db.insert_fight(event_id, fight_number, event['date'], meron, wala, winner, plasada, pit_fee, notes, g.username)
        return jsonify({"id": fight_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/events/<int:event_id>/revenue', methods=['POST'])
@require_login
def api_add_revenue(event_id):
    event = db.get_event(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    
    data = request.get_json() or {}
    source = data.get('source')
    amount = data.get('amount', type=float)
    description = data.get('description', '').strip() or None
    
    if not source or amount is None or amount < 0:
        return jsonify({"error": "Missing/invalid fields"}), 400
    
    try:
        revenue_id = db.insert_event_revenue(event_id, event['date'], source, amount, description, g.username)
        return jsonify({"id": revenue_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/fights/<int:fight_id>', methods=['PUT', 'DELETE'])
@require_login
def api_fight(fight_id):
    fight = db.get_fight(fight_id)
    if not fight:
        return jsonify({"error": "Fight not found"}), 404
    
    if request.method == 'PUT':
        data = request.get_json() or {}
        winner = data.get('winner')
        plasada = data.get('plasada', type=float)
        pit_fee = data.get('pit_fee', type=float)
        notes = data.get('notes', '').strip() or None
        
        try:
            db.update_fight(fight_id, winner, plasada, pit_fee, notes)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            db.delete_fight(fight_id)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

# --- Expenses ---

@app.route('/expenses')
@require_login
def expenses_page():
    return render_template('expenses.html')

@app.route('/api/expenses')
@require_login
def api_expenses():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category')
    
    result = db.list_expenses(date_from, date_to, category, limit, offset)
    return jsonify(result)

@app.route('/expenses/new', methods=['GET', 'POST'])
@require_login
def new_expense():
    if request.method == 'POST':
        date_str = request.form.get('date')
        amount = request.form.get('amount', type=float)
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        note = request.form.get('note', '').strip() or None
        
        if not all([date_str, amount]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_expense'))
        
        try:
            db.insert_expense(date_str, amount, description, category, note, g.username)
            flash("Expense recorded.", "success")
            return redirect(url_for('expenses_page'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template('new_expense.html')

# --- Remittances ---

@app.route('/remittances')
@require_login
def remittances_page():
    return render_template('remittances.html')

@app.route('/api/remittances')
@require_login
def api_remittances():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    result = db.list_cash_remittances(date_from, date_to, limit, offset)
    return jsonify(result)

@app.route('/remittances/new', methods=['GET', 'POST'])
@require_login
def new_remittance():
    if request.method == 'POST':
        date_str = request.form.get('date')
        amount = request.form.get('amount', type=float)
        note = request.form.get('note', '').strip() or None
        
        if not all([date_str, amount]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_remittance'))
        
        try:
            db.insert_cash_remittance(date_str, amount, note, g.username)
            flash("Remittance recorded.", "success")
            return redirect(url_for('remittances_page'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template('new_remittance.html')

# --- Personnel ---

@app.route('/personnel')
@require_login
def personnel_page():
    return render_template('personnel.html')

@app.route('/api/personnel')
@require_login
def api_personnel():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    status = request.args.get('status')
    position = request.args.get('position')
    
    result = db.list_personnel(status, position, limit, offset)
    return jsonify(result)

@app.route('/personnel/new', methods=['GET', 'POST'])
@require_login
def new_personnel():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        position = request.form.get('position')
        contact = request.form.get('contact', '').strip() or None
        date_hired = request.form.get('date_hired')
        rate = request.form.get('rate', type=float)
        
        if not all([name, position]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_personnel'))
        
        try:
            db.insert_personnel(name, position, contact, date_hired, 'Active', rate, g.username)
            flash("Personnel added.", "success")
            return redirect(url_for('personnel_page'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template('new_personnel.html')

# --- Shift Roster ---

@app.route('/shift-roster')
@require_login
def shift_roster_page():
    roster_date = request.args.get('date', date.today().isoformat())
    roster = db.get_shift_roster(roster_date)
    shift_types = db.list_shift_types()
    personnel = db.list_personnel(status='Active')
    
    return render_template('shift_roster.html', 
        roster_date=roster_date, roster=roster, 
        shift_types=shift_types, personnel=personnel)

@app.route('/api/shift-roster', methods=['POST'])
@require_login
def api_add_roster():
    data = request.get_json() or {}
    date_str = data.get('date')
    shift_type_id = data.get('shift_type_id', type=int)
    personnel_id = data.get('personnel_id', type=int)
    status = data.get('status', 'Present')
    
    if not all([date_str, shift_type_id, personnel_id]):
        return jsonify({"error": "Missing fields"}), 400
    
    try:
        roster_id = db.add_shift_roster_entry(date_str, shift_type_id, personnel_id, status, g.username)
        return jsonify({"id": roster_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/shift-roster/<int:roster_id>', methods=['PUT', 'DELETE'])
@require_login
def api_roster_action(roster_id):
    if request.method == 'PUT':
        data = request.get_json() or {}
        status = data.get('status', 'Present')
        try:
            db.update_shift_roster_status(roster_id, status, g.username)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            db.remove_shift_roster_entry(roster_id)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

# --- Users (Admin) ---

@app.route('/users')
@require_role('super_admin', 'admin')
def users_page():
    users = db.list_users()
    return render_template('users.html', users=users)

@app.route('/users/new', methods=['GET', 'POST'])
@require_role('super_admin', 'admin')
def new_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        role = request.form.get('role', 'staff')
        
        if len(username) < 3 or len(password) < 6:
            flash("Username (3+) and password (6+) required.", "error")
            return redirect(url_for('new_user'))
        
        try:
            db.create_user(username, password, role)
            flash(f"User {username} created.", "success")
            return redirect(url_for('users_page'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template('new_user.html', roles=db.ROLES, role_labels=ROLE_LABELS)

@app.route('/api/users/<username>', methods=['DELETE'])
@require_role('super_admin', 'admin')
def api_delete_user(username):
    try:
        if db.delete_user(username):
            return jsonify({"ok": True})
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, port=5001)
