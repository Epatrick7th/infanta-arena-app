import os
import secrets
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, make_response, g
import db
import boss_db
import boss_approval
import analytics
import live_fight

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
    user_role = session.get('user_role')
    user_id = session.get('user_id')
    today = date.today().isoformat()
    
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    arena_name = user['arena_name'] or 'My Arena'
    boss_id = user['id']
    
    # BOSS: Executive dashboard - View/Approve only
    if user_role == 'boss':
        dashboard_data = boss_db.get_boss_dashboard_summary(boss_id, today)
        financial = boss_db.get_financial_summary(boss_id, 'day', today)
        
        return render_template('boss_dashboard.html',
            today=today,
            arena_name=arena_name,
            **dashboard_data,
            **financial)
    
    # ASSISTANT: Data entry dashboard - Input all numbers
    if user_role == 'assistant':
        # Get recent events for this arena (for the assistant to edit)
        events_result = db.list_events(date_from=str(date(2026, 1, 1)), limit=10)
        recent_events = events_result['rows'] if isinstance(events_result, dict) else events_result
        
        # Get summary for display
        dashboard_data = boss_db.get_boss_dashboard_summary(boss_id, today)
        
        return render_template('assistant_dashboard.html',
            today=today,
            arena_name=arena_name,
            recent_events=recent_events,
            **dashboard_data)
    
    # STAFF: Show operational dashboard (fallback)
    events_result = db.list_events(date_from=str(date(2026, 1, 1)), limit=5)
    recent_events = events_result['rows'] if isinstance(events_result, dict) else events_result
    total_expenses_result = db.list_expenses()
    total_expenses_list = total_expenses_result['rows'] if isinstance(total_expenses_result, dict) else total_expenses_result
    total_expenses = sum(e['amount'] for e in total_expenses_list) if total_expenses_list else 0
    
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

# ===== LIVE ARENA FIGHT DASHBOARD =====

@app.route('/live-arena')
@require_role('boss', 'admin')
def live_arena():
    """Live arena fight dashboard - real-time fight and betting view."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    # Get current/live event for today
    conn = db.get_connection()
    event = conn.execute(
        f"SELECT id, name, event_type FROM events WHERE boss_id = ? AND date = ? AND {db.NOT_DELETED} ORDER BY created_at DESC LIMIT 1",
        (boss_id, today)
    ).fetchone()
    conn.close()
    
    event_id = event['id'] if event else None
    event_name = event['name'] if event else 'No Event Today'
    
    # Get live or next fight
    live_fight_data = live_fight.get_live_fight(boss_id, event_id)
    
    if not live_fight_data:
        flash("No fights scheduled. Create a fight to begin.", "info")
        return render_template('live_arena.html',
            arena_name=arena_name,
            event_name=event_name,
            fight=None,
            bets_summary=None)
    
    # Get recent bets (last 10)
    recent_bets = live_fight.get_fight_bets(live_fight_data['id'])[:10]
    
    response = make_response(render_template('live_arena.html',
        arena_name=arena_name,
        event_name=event_name,
        fight=live_fight_data,
        bets_summary=live_fight_data if live_fight_data else None,
        recent_bets=recent_bets))
    
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/api/live-fight/<int:fight_id>')
@require_role('boss', 'admin')
def api_live_fight(fight_id):
    """API endpoint for live fight data (for polling/WebSocket)."""
    conn = db.get_connection()
    fight = conn.execute("SELECT * FROM fights WHERE id = ?", (fight_id,)).fetchone()
    conn.close()
    
    if not fight:
        return jsonify({'error': 'Fight not found'}), 404
    
    # Verify access
    user_id = session.get('user_id')
    if fight['boss_id'] != user_id and session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    fight_dict = dict(fight)
    bets = live_fight.get_fight_bets_summary(fight_id)
    
    return jsonify({
        **fight_dict,
        **bets
    })

@app.route('/api/live-fight/<int:fight_id>/bets')
@require_role('boss', 'admin')
def api_fight_bets(fight_id):
    """Get recent bets for a fight."""
    conn = db.get_connection()
    fight = conn.execute("SELECT boss_id FROM fights WHERE id = ?", (fight_id,)).fetchone()
    conn.close()
    
    if not fight:
        return jsonify({'error': 'Fight not found'}), 404
    
    # Verify access
    user_id = session.get('user_id')
    if fight['boss_id'] != user_id and session.get('user_role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    bets = live_fight.get_fight_bets(fight_id)
    return jsonify({'bets': bets, 'count': len(bets)})

@app.route('/api/live-fight/<int:fight_id>/start', methods=['POST'])
@require_role('boss', 'admin')
def api_start_fight(fight_id):
    """Start a fight (change status to live)."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    fight = conn.execute("SELECT boss_id FROM fights WHERE id = ?", (fight_id,)).fetchone()
    conn.close()
    
    if not fight or fight['boss_id'] != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    if live_fight.start_fight(fight_id):
        return jsonify({'status': 'ok', 'message': 'Fight started'})
    return jsonify({'error': 'Failed to start fight'}), 500

@app.route('/api/live-fight/<int:fight_id>/finish', methods=['POST'])
@require_role('boss', 'admin')
def api_finish_fight(fight_id):
    """Finish a fight with a winner."""
    user_id = session.get('user_id')
    data = request.get_json()
    winner = data.get('winner')  # 'Meron', 'Wala', or 'Draw'
    
    if not winner or winner not in ['Meron', 'Wala', 'Draw']:
        return jsonify({'error': 'Invalid winner'}), 400
    
    conn = db.get_connection()
    fight = conn.execute("SELECT boss_id FROM fights WHERE id = ?", (fight_id,)).fetchone()
    conn.close()
    
    if not fight or fight['boss_id'] != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    if live_fight.finish_fight(fight_id, winner):
        return jsonify({'status': 'ok', 'message': f'Fight finished - {winner} wins'})
    return jsonify({'error': 'Failed to finish fight'}), 500

@app.route('/api/live-fight/<int:fight_id>/bet', methods=['POST'])
@require_role('boss', 'admin')
def api_add_bet(fight_id):
    """Add a bet to a live fight."""
    user_id = session.get('user_id')
    data = request.get_json()
    
    side = data.get('side')  # 'Meron' or 'Wala'
    amount = data.get('amount', 0)
    bettor_name = data.get('bettor_name', 'Anonymous')
    
    if not side or side not in ['Meron', 'Wala'] or amount <= 0:
        return jsonify({'error': 'Invalid bet'}), 400
    
    conn = db.get_connection()
    fight = conn.execute("SELECT boss_id FROM fights WHERE id = ?", (fight_id,)).fetchone()
    conn.close()
    
    if not fight or fight['boss_id'] != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    if live_fight.add_bet(fight_id, user_id, side, amount, bettor_name, session.get('username')):
        bets_summary = live_fight.get_fight_bets_summary(fight_id)
        return jsonify({'status': 'ok', 'bet_added': True, **bets_summary})
    return jsonify({'error': 'Failed to add bet'}), 500

# ===== ANALYTICS DETAIL ROUTES (Drilldowns) =====

@app.route('/analytics/sales-today')
@require_role('boss')
def analytics_sales_today():
    """View all sales transactions for today."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    # Get all sales for today
    conn = boss_db.get_connection()
    sales = conn.execute("""
        SELECT id, transaction_date, amount, sales_type, status, created_at
        FROM sales
        WHERE user_id = ? AND DATE(transaction_date) = ?
        ORDER BY created_at DESC
    """, (boss_id, today)).fetchall()
    conn.close()
    
    total_revenue = sum(s['amount'] for s in sales) if sales else 0
    
    return render_template('analytics_sales_today.html',
        arena_name=arena_name,
        sales=sales,
        total_revenue=total_revenue,
        today=today)

@app.route('/analytics/revenue-vs-expenses-today')
@require_role('boss')
def analytics_revenue_vs_expenses():
    """View revenue vs expenses comparison for today."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    # Get sales (revenue)
    conn = boss_db.get_connection()
    sales = conn.execute("""
        SELECT id, transaction_date, amount, sales_type, status, created_at
        FROM sales
        WHERE user_id = ? AND DATE(transaction_date) = ?
        ORDER BY created_at DESC
    """, (boss_id, today)).fetchall()
    conn.close()
    
    # Get expenses
    conn = boss_db.get_connection()
    expenses = conn.execute("""
        SELECT id, transaction_date, amount, category, description, created_at
        FROM expenses
        WHERE user_id = ? AND DATE(transaction_date) = ?
        ORDER BY created_at DESC
    """, (boss_id, today)).fetchall()
    conn.close()
    
    total_revenue = sum(s['amount'] for s in sales) if sales else 0
    total_expenses = sum(e['amount'] for e in expenses) if expenses else 0
    net_profit = total_revenue - total_expenses
    
    return render_template('analytics_revenue_vs_expenses.html',
        arena_name=arena_name,
        sales=sales,
        expenses=expenses,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_profit=net_profit,
        today=today)

@app.route('/analytics/sales-by-type/<sales_type>')
@require_role('boss')
def analytics_sales_by_type(sales_type):
    """View sales filtered by type (gate, concession, plasada)."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    # Normalize sales_type
    valid_types = {'gate', 'concession', 'plasada'}
    if sales_type.lower() not in valid_types:
        flash("Invalid sales type.", "error")
        return redirect(url_for('analytics_daily'))
    
    # Get sales for this type today
    conn = boss_db.get_connection()
    sales = conn.execute("""
        SELECT id, transaction_date, amount, sales_type, status, created_at
        FROM sales
        WHERE user_id = ? AND DATE(transaction_date) = ? AND LOWER(sales_type) = ?
        ORDER BY created_at DESC
    """, (boss_id, today, sales_type.lower())).fetchall()
    conn.close()
    
    total_revenue = sum(s['amount'] for s in sales) if sales else 0
    
    return render_template('analytics_sales_by_type.html',
        arena_name=arena_name,
        sales=sales,
        sales_type=sales_type.title(),
        total_revenue=total_revenue,
        today=today)

@app.route('/analytics/expenses-by-category/<category>')
@require_role('boss')
def analytics_expenses_by_category(category):
    """View expenses filtered by category."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    # Normalize category (convert hyphens to spaces and title case)
    category_display = category.replace('-', ' ').title()
    
    # Get expenses for this category today
    conn = boss_db.get_connection()
    expenses = conn.execute("""
        SELECT id, transaction_date, amount, category, description, created_at
        FROM expenses
        WHERE user_id = ? AND DATE(transaction_date) = ? AND LOWER(category) = ?
        ORDER BY created_at DESC
    """, (boss_id, today, category_display.lower())).fetchall()
    conn.close()
    
    total_expenses = sum(e['amount'] for e in expenses) if expenses else 0
    
    return render_template('analytics_expenses_by_category.html',
        arena_name=arena_name,
        category=category_display,
        expenses=expenses,
        total_expenses=total_expenses,
        today=today)

# ===== ANALYTICS ROUTES =====

@app.route('/analytics')
@require_role('boss')
def analytics_dashboard():
    """Boss views financial analytics - daily view."""
    return redirect(url_for('analytics_daily'))

@app.route('/analytics/daily')
@require_role('boss')
def analytics_daily():
    """Boss views daily P&L."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    daily_pl = analytics.get_daily_pl(boss_id, today)
    daily_trend = analytics.get_daily_trend(boss_id, 7, today)
    revenue_breakdown = analytics.get_revenue_breakdown(boss_id, today)
    expense_breakdown = analytics.get_expense_breakdown(boss_id, today)
    
    response = make_response(render_template('analytics_daily.html',
        arena_name=arena_name,
        daily_pl=daily_pl,
        daily_trend=daily_trend,
        revenue_breakdown=revenue_breakdown,
        expense_breakdown=expense_breakdown,
        current_view='daily'))
    
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/analytics/weekly')
@require_role('boss')
def analytics_weekly():
    """Boss views weekly P&L."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    weekly_pl = analytics.get_weekly_pl(boss_id, today)
    daily_trend = analytics.get_daily_trend(boss_id, 7, today)
    revenue_breakdown = analytics.get_revenue_breakdown(boss_id, today)
    expense_breakdown = analytics.get_expense_breakdown(boss_id, today)
    
    response = make_response(render_template('analytics_weekly.html',
        arena_name=arena_name,
        weekly_pl=weekly_pl,
        daily_trend=daily_trend,
        revenue_breakdown=revenue_breakdown,
        expense_breakdown=expense_breakdown,
        current_view='weekly'))
    
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/analytics/monthly')
@require_role('boss')
def analytics_monthly():
    """Boss views monthly P&L."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    monthly_pl = analytics.get_monthly_pl(boss_id, today)
    daily_trend = analytics.get_daily_trend(boss_id, 7, today)
    revenue_breakdown = analytics.get_revenue_breakdown(boss_id, today)
    expense_breakdown = analytics.get_expense_breakdown(boss_id, today)
    
    response = make_response(render_template('analytics_monthly.html',
        arena_name=arena_name,
        monthly_pl=monthly_pl,
        daily_trend=daily_trend,
        revenue_breakdown=revenue_breakdown,
        expense_breakdown=expense_breakdown,
        current_view='monthly'))
    
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/analytics/trends')
@require_role('boss')
def analytics_trends():
    """Boss views 7-day trends."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    today = date.today().isoformat()
    
    daily_trend = analytics.get_daily_trend(boss_id, 7, today)
    
    response = make_response(render_template('analytics_trends.html',
        arena_name=arena_name,
        daily_trend=daily_trend,
        current_view='trends'))
    
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/api/users/<username>', methods=['DELETE'])
@require_role('super_admin', 'admin')
def api_delete_user(username):
    try:
        if db.delete_user(username):
            return jsonify({"ok": True})
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ===== BOSS APPROVAL ROUTES =====

@app.route('/boss/approvals')
@require_role('boss')
def boss_approvals():
    """Boss views pending approvals."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    boss_id = user['id']
    arena_name = user['arena_name'] or 'My Arena'
    
    pending = boss_approval.get_pending_approvals(boss_id)
    
    return render_template('boss_approvals.html',
        arena_name=arena_name,
        **pending)

@app.route('/approve/event/<int:event_id>', methods=['POST'])
@require_role('boss')
def approve_event(event_id):
    """Boss approves an event."""
    user_id = session.get('user_id')
    username = session.get('username')
    conn = db.get_connection()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if user:
        boss_approval.approve_event(event_id, user['id'], username)
        flash("Event approved!", "success")
    
    return redirect(url_for('boss_approvals'))

@app.route('/approve/revenue/<int:revenue_id>', methods=['POST'])
@require_role('boss')
def approve_revenue(revenue_id):
    """Boss approves revenue."""
    user_id = session.get('user_id')
    username = session.get('username')
    conn = db.get_connection()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if user:
        boss_approval.approve_revenue(revenue_id, user['id'], username)
        flash("Revenue approved!", "success")
    
    return redirect(url_for('boss_approvals'))

@app.route('/approve/expense/<int:expense_id>', methods=['POST'])
@require_role('boss')
def approve_expense(expense_id):
    """Boss approves expense."""
    user_id = session.get('user_id')
    username = session.get('username')
    conn = db.get_connection()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if user:
        boss_approval.approve_expense(expense_id, user['id'], username)
        flash("Expense approved!", "success")
    
    return redirect(url_for('boss_approvals'))

@app.route('/approve/remittance/<int:remittance_id>', methods=['POST'])
@require_role('boss')
def approve_remittance(remittance_id):
    """Boss approves remittance."""
    user_id = session.get('user_id')
    username = session.get('username')
    conn = db.get_connection()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if user:
        boss_approval.approve_remittance(remittance_id, user['id'], username)
        flash("Remittance approved!", "success")
    
    return redirect(url_for('boss_approvals'))

@app.route('/reject/event/<int:event_id>', methods=['POST'])
@require_role('boss')
def reject_event(event_id):
    """Boss rejects an event."""
    user_id = session.get('user_id')
    username = session.get('username')
    conn = db.get_connection()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if user:
        boss_approval.reject_event(event_id, user['id'], username)
        flash("Event rejected!", "info")
    
    return redirect(url_for('boss_approvals'))

if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, port=5001)
