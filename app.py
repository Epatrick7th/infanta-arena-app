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

# --- Session cookie hardening ---
# SameSite=Lax stops the browser attaching this cookie to cross-site POSTs,
# which is what actually prevents CSRF here. 'Lax' (not 'Strict') so that
# arriving via an ordinary link keeps the user logged in.
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    # enable in production, where the app is served over HTTPS
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# --- Role model -----------------------------------------------------------
# boss      oversight only. Sees every figure, changes nothing.
# assistant does the operational work, including processing approvals.
# admin     account management.
#
# The boss restriction is enforced by denying every state-changing request
# from a boss session, rather than by guarding routes one at a time. A route
# added tomorrow is therefore closed to the boss by default, which is the
# only way this stays true as the app grows.
READ_ONLY_ROLES = {"boss", "viewer"}

# the only state-changing endpoints a read-only user may reach
READ_ONLY_POST_ALLOWED = {"login", "logout"}


@app.before_request
def enforce_read_only_roles():
    """Refuse any mutation attempted by a read-only role.

    Covers direct URL and API calls, not just hidden buttons: a boss session
    cannot change data even with a crafted request.
    """
    if request.method in SAFE_METHODS:
        return None
    if request.endpoint in READ_ONLY_POST_ALLOWED:
        return None

    role = session.get("user_role")
    if role in READ_ONLY_ROLES:
        message = ("Your account has view-only access. "
                   "Ask an assistant to make this change.")
        if request.path.startswith("/api/"):
            return jsonify({"error": message, "role": role}), 403
        flash(message, "error")
        # send them back where they came from rather than a dead end
        return redirect(request.referrer or url_for("dashboard"))
    return None




@app.before_request
def block_cross_site_writes():
    """Reject state-changing requests that a *different* site initiated.

    Backs up SameSite for browsers that ignore it, and covers the JSON API.
    A missing Origin/Referer is allowed: curl, the test client and mobile
    apps send neither, while browsers always send Origin on a cross-site
    POST, so the forgery path is still closed.
    """
    if request.method in SAFE_METHODS:
        return None

    origin = request.headers.get("Origin")
    if not origin:
        referer = request.headers.get("Referer")
        if not referer:
            return None  # non-browser client
        origin = referer

    from urllib.parse import urlparse
    incoming = urlparse(origin).netloc
    expected = urlparse(request.host_url).netloc
    if incoming and incoming != expected:
        return jsonify({"error": "Cross-site request rejected"}), 403
    return None


ROLE_LABELS = db.ROLE_LABELS

# --- JSON payload coercion ---------------------------------------------
# request.get_json() returns a plain dict, so Werkzeug's `type=` kwarg is
# not available here. These mirror it: coerce when possible, return the
# default when the key is missing or the value will not convert.

def _as_int(data, key, default=None):
    try:
        return int(data.get(key))
    except (TypeError, ValueError):
        return default


def _as_float(data, key, default=None):
    try:
        return float(data.get(key))
    except (TypeError, ValueError):
        return default


def _as_text(data, key, default=None):
    """Trimmed string, or `default` when missing/blank. JSON may send non-strings."""
    v = data.get(key)
    if v is None:
        return default
    v = str(v).strip()
    return v or default

def current_boss_id():
    """The boss whose books the logged-in user may see.

    boss      -> their own id
    assistant -> the boss who owns the same arena
    admin     -> None, meaning "no filter" (unchanged behaviour)

    Returning None for admins keeps the analytics and approval paths working
    exactly as before; every other caller gets a hard filter.
    """
    role = session.get('user_role')
    uid = session.get('user_id')
    if role in ('admin', 'super_admin'):
        return None
    if role == 'boss':
        return uid
    # assistants and staff inherit their arena's boss
    conn = db.get_connection()
    row = conn.execute("SELECT arena_name FROM users WHERE id = ?", (uid,)).fetchone()
    boss = None
    if row and row['arena_name']:
        boss = conn.execute(
            "SELECT id FROM users WHERE role = 'boss' AND arena_name = ?",
            (row['arena_name'],)).fetchone()
    conn.close()
    return boss['id'] if boss else uid


def owns(record):
    """True when the logged-in user may touch this record. Admins may touch all."""
    if record is None:
        return False
    role = session.get('user_role')
    if role in ('admin', 'super_admin'):
        return True
    return record.get('boss_id') == current_boss_id()


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
        events_result = db.list_events(date_from=str(date(2026, 1, 1)), limit=10,
                                       boss_id=current_boss_id())
        recent_events = events_result['rows'] if isinstance(events_result, dict) else events_result
        
        # Get summary for display
        dashboard_data = boss_db.get_boss_dashboard_summary(boss_id, today)
        
        return render_template('assistant_dashboard.html',
            today=today,
            arena_name=arena_name,
            recent_events=recent_events,
            **dashboard_data)
    
    # STAFF: Show operational dashboard (fallback)
    events_result = db.list_events(date_from=str(date(2026, 1, 1)), limit=5,
                                   boss_id=current_boss_id())
    recent_events = events_result['rows'] if isinstance(events_result, dict) else events_result
    total_expenses_result = db.list_expenses(boss_id=current_boss_id())
    total_expenses_list = total_expenses_result['rows'] if isinstance(total_expenses_result, dict) else total_expenses_result
    total_expenses = sum(e['amount'] for e in total_expenses_list) if total_expenses_list else 0
    
    return render_template('dashboard.html', 
        recent_events=recent_events,
        total_expenses=total_expenses,
        today=today)

@app.route('/events')
@require_login
def events_page():
    result = db.list_events(limit=60, boss_id=current_boss_id())
    rows = result['rows'] if isinstance(result, dict) else result
    # the card shows fights and revenue per event, so enrich each row.
    # get_event_summary returns fight_count/total_revenue; the template
    # reads total_fights, so map it rather than silently showing 0.
    events = []
    for e in rows:
        summary = db.get_event_summary(e['id']) or {}
        events.append({**e,
                       'event_date': e.get('date'),
                       'total_fights': summary.get('fight_count', 0),
                       'total_revenue': summary.get('total_revenue', 0)})
    return render_template('events.html', recent_events=events)

@app.route('/api/events')
@require_login
def api_events():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    result = db.list_events(date_from, date_to, limit, offset,
                            boss_id=current_boss_id())
    return jsonify(result)

@app.route('/events/new', methods=['GET', 'POST'])
@require_login
def new_event():
    if request.method == 'POST':
        # the form posts event_date/notes; accept both spellings so an
        # older client or a direct POST keeps working
        date_str = request.form.get('date') or request.form.get('event_date')
        name = request.form.get('name', '').strip()
        event_type = request.form.get('event_type') or 'derby'
        note = ((request.form.get('note') or request.form.get('notes') or '')
                .strip() or None)
        location = (request.form.get('location') or '').strip() or None
        
        if not all([date_str, name, event_type]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_event'))
        
        try:
            event_id = db.insert_event(date_str, name, event_type, note, g.username,
                            boss_id=current_boss_id(), location=location)
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
    
    if not owns(event):
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
    if not owns(event):
        return jsonify({"error": "Access denied"}), 403
    
    data = request.get_json() or {}
    fight_number = _as_int(data, 'fight_number')
    meron = _as_text(data, 'meron', '')
    wala = _as_text(data, 'wala', '')
    winner = data.get('winner')
    plasada = _as_float(data, 'plasada')
    pit_fee = _as_float(data, 'pit_fee')
    notes = _as_text(data, 'notes')
    
    if not all([fight_number, meron, wala]):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        fight_id = db.insert_fight(event_id, fight_number, event['date'], meron, wala, winner,
                                   plasada, pit_fee, notes, g.username,
                                   boss_id=event.get('boss_id') or current_boss_id())
        return jsonify({"id": fight_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/events/<int:event_id>/revenue', methods=['POST'])
@require_login
def api_add_revenue(event_id):
    event = db.get_event(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    if not owns(event):
        return jsonify({"error": "Access denied"}), 403
    
    data = request.get_json() or {}
    source = data.get('source')
    amount = _as_float(data, 'amount')
    description = _as_text(data, 'description')
    
    if not source or amount is None or amount < 0:
        return jsonify({"error": "Missing/invalid fields"}), 400
    
    try:
        revenue_id = db.insert_event_revenue(event_id, event['date'], source, amount, description,
                                       g.username,
                                       boss_id=event.get('boss_id') or current_boss_id())
        return jsonify({"id": revenue_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/fights/<int:fight_id>', methods=['PUT', 'DELETE'])
@require_login
def api_fight(fight_id):
    fight = db.get_fight(fight_id)
    if not fight:
        return jsonify({"error": "Fight not found"}), 404
    if not owns(fight):
        return jsonify({"error": "Access denied"}), 403
    
    if request.method == 'PUT':
        data = request.get_json() or {}
        winner = data.get('winner')
        plasada = _as_float(data, 'plasada')
        pit_fee = _as_float(data, 'pit_fee')
        notes = _as_text(data, 'notes')
        
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
    result = db.list_expenses(limit=60, boss_id=current_boss_id())
    rows = result['rows'] if isinstance(result, dict) else result
    return render_template('expenses.html', expenses=rows)

@app.route('/api/expenses')
@require_login
def api_expenses():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category')
    
    result = db.list_expenses(date_from, date_to, category, limit, offset,
                              boss_id=current_boss_id())
    return jsonify(result)

@app.route('/expenses/new', methods=['GET', 'POST'])
@require_login
def new_expense():
    if request.method == 'POST':
        date_str = request.form.get('date')
        amount = request.form.get('amount', type=float)
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        note = ((request.form.get('note') or request.form.get('notes') or '')
                .strip() or None)
        
        if not all([date_str, amount]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_expense'))
        
        try:
            db.insert_expense(date_str, amount, description, category, note, g.username,
                              boss_id=current_boss_id())
            flash("Expense recorded.", "success")
            return redirect(url_for('expenses_page'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template('new_expense.html')

# --- Remittances ---

@app.route('/remittances')
@require_login
def remittances_page():
    result = db.list_cash_remittances(limit=60, boss_id=current_boss_id())
    rows = result['rows'] if isinstance(result, dict) else result
    return render_template('remittances.html', remittances=rows)

@app.route('/api/remittances')
@require_login
def api_remittances():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    result = db.list_cash_remittances(date_from, date_to, limit, offset,
                                      boss_id=current_boss_id())
    return jsonify(result)

@app.route('/remittances/new', methods=['GET', 'POST'])
@require_login
def new_remittance():
    if request.method == 'POST':
        date_str = request.form.get('date')
        amount = request.form.get('amount', type=float)
        note = ((request.form.get('note') or request.form.get('notes') or '')
                .strip() or None)
        recipient = (request.form.get('recipient') or '').strip()
        if recipient:
            note = f"To {recipient}" + (f" - {note}" if note else "")
        
        if not all([date_str, amount]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_remittance'))
        
        try:
            db.insert_cash_remittance(date_str, amount, note, g.username,
                                      boss_id=current_boss_id())
            flash("Remittance recorded.", "success")
            return redirect(url_for('remittances_page'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template('new_remittance.html')

# --- Personnel ---

@app.route('/personnel')
@require_login
def personnel_page():
    result = db.list_personnel(limit=100, boss_id=current_boss_id())
    rows = result['rows'] if isinstance(result, dict) else result
    return render_template('personnel.html', personnel=rows)

@app.route('/api/personnel')
@require_login
def api_personnel():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    status = request.args.get('status')
    position = request.args.get('position')
    
    result = db.list_personnel(status, position, limit, offset,
                               boss_id=current_boss_id())
    return jsonify(result)

@app.route('/personnel/new', methods=['GET', 'POST'])
@require_login
def new_personnel():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        position = request.form.get('position')
        contact = request.form.get('contact', '').strip() or None
        date_hired = request.form.get('date_hired') or None
        # the form field is named daily_rate
        rate = request.form.get('rate', type=float)
        if rate is None:
            rate = request.form.get('daily_rate', type=float)

        # The table only permits Admin/Handler/Security/Staff. Older markup
        # offered job titles that do not exist there, so every submission
        # failed the CHECK constraint; map them rather than rebuild the table.
        POSITION_MAP = {
            'pit_manager': 'Admin', 'referee': 'Handler', 'cashier': 'Staff',
            'security': 'Security', 'cleaner': 'Staff', 'other': 'Staff',
        }
        position = POSITION_MAP.get((position or '').lower(), position)
        if position not in ('Admin', 'Handler', 'Security', 'Staff'):
            position = 'Staff'

        # the column expects Active/Inactive, the select sends lower case
        status = (request.form.get('status') or 'Active').capitalize()
        if status not in ('Active', 'Inactive'):
            status = 'Active'
        
        if not all([name, position]):
            flash("Missing required fields.", "error")
            return redirect(url_for('new_personnel'))
        
        try:
            db.insert_personnel(name, position, contact, date_hired, status, rate,
                                g.username, boss_id=current_boss_id())
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
    roster = db.get_shift_roster(roster_date, boss_id=current_boss_id())
    shift_types = db.list_shift_types()
    personnel = db.list_personnel(status='Active', boss_id=current_boss_id())
    
    return render_template('shift_roster.html', 
        roster_date=roster_date, roster=roster, 
        shift_types=shift_types, personnel=personnel)

@app.route('/api/shift-roster', methods=['POST'])
@require_login
def api_add_roster():
    data = request.get_json() or {}
    date_str = data.get('date')
    shift_type_id = _as_int(data, 'shift_type_id')
    personnel_id = _as_int(data, 'personnel_id')
    status = data.get('status', 'Present')
    
    if not all([date_str, shift_type_id, personnel_id]):
        return jsonify({"error": "Missing fields"}), 400
    
    try:
        roster_id = db.add_shift_roster_entry(date_str, shift_type_id, personnel_id, status,
                                              g.username, boss_id=current_boss_id())
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
        SELECT id, date AS transaction_date, amount, source AS sales_type, approval_status AS status, created_at
        FROM event_revenue
        WHERE boss_id = ? AND date = ? AND deleted_at IS NULL
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
        SELECT id, date AS transaction_date, amount, source AS sales_type, approval_status AS status, created_at
        FROM event_revenue
        WHERE boss_id = ? AND date = ? AND deleted_at IS NULL
        ORDER BY created_at DESC
    """, (boss_id, today)).fetchall()
    conn.close()
    
    # Get expenses
    conn = boss_db.get_connection()
    expenses = conn.execute("""
        SELECT id, date AS transaction_date, amount, category, description, created_at
        FROM expenses
        WHERE boss_id = ? AND date = ? AND deleted_at IS NULL
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
        SELECT id, date AS transaction_date, amount, source AS sales_type, approval_status AS status, created_at
        FROM event_revenue
        WHERE boss_id = ? AND date = ? AND LOWER(source) = ? AND deleted_at IS NULL
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
        SELECT id, date AS transaction_date, amount, category, description, created_at
        FROM expenses
        WHERE boss_id = ? AND date = ? AND LOWER(category) = ? AND deleted_at IS NULL
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
@require_role('boss', 'assistant', 'admin', 'super_admin')
def boss_approvals():
    """Boss views pending approvals."""
    user_id = session.get('user_id')
    conn = db.get_connection()
    user = conn.execute("SELECT id, arena_name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    arena_name = user['arena_name'] or 'My Arena'

    # Pending records belong to the arena's boss. An assistant's own user id
    # matches nothing, which left the approvals queue permanently empty for
    # the very role that is supposed to action it.
    boss_id = current_boss_id()

    pending = boss_approval.get_pending_approvals(boss_id)
    
    return render_template('boss_approvals.html',
        arena_name=arena_name,
        **pending)

@app.route('/approve/event/<int:event_id>', methods=['POST'])
@require_role('assistant', 'admin', 'super_admin')
def approve_event(event_id):
    """Boss approves an event."""
    username = session.get('username')
    # Records belong to the arena's boss, not to the assistant acting on them,
    # so scope by the arena. Using the actor's own id silently matched no rows.
    owner_id = current_boss_id()

    if boss_approval.approve_event(event_id, owner_id, username):
        flash("Event approved by {}.".format(username), "success")
    else:
        flash("Nothing was changed. It may already have been actioned.", "error")
    
    return redirect(url_for('boss_approvals'))

@app.route('/approve/revenue/<int:revenue_id>', methods=['POST'])
@require_role('assistant', 'admin', 'super_admin')
def approve_revenue(revenue_id):
    """Boss approves revenue."""
    username = session.get('username')
    # Records belong to the arena's boss, not to the assistant acting on them,
    # so scope by the arena. Using the actor's own id silently matched no rows.
    owner_id = current_boss_id()

    if boss_approval.approve_revenue(revenue_id, owner_id, username):
        flash("Revenue approved by {}.".format(username), "success")
    else:
        flash("Nothing was changed. It may already have been actioned.", "error")
    
    return redirect(url_for('boss_approvals'))

@app.route('/approve/expense/<int:expense_id>', methods=['POST'])
@require_role('assistant', 'admin', 'super_admin')
def approve_expense(expense_id):
    """Boss approves expense."""
    username = session.get('username')
    # Records belong to the arena's boss, not to the assistant acting on them,
    # so scope by the arena. Using the actor's own id silently matched no rows.
    owner_id = current_boss_id()

    if boss_approval.approve_expense(expense_id, owner_id, username):
        flash("Expense approved by {}.".format(username), "success")
    else:
        flash("Nothing was changed. It may already have been actioned.", "error")
    
    return redirect(url_for('boss_approvals'))

@app.route('/approve/remittance/<int:remittance_id>', methods=['POST'])
@require_role('assistant', 'admin', 'super_admin')
def approve_remittance(remittance_id):
    """Boss approves remittance."""
    username = session.get('username')
    # Records belong to the arena's boss, not to the assistant acting on them,
    # so scope by the arena. Using the actor's own id silently matched no rows.
    owner_id = current_boss_id()

    if boss_approval.approve_remittance(remittance_id, owner_id, username):
        flash("Remittance approved by {}.".format(username), "success")
    else:
        flash("Nothing was changed. It may already have been actioned.", "error")
    
    return redirect(url_for('boss_approvals'))

@app.route('/reject/event/<int:event_id>', methods=['POST'])
@require_role('assistant', 'admin', 'super_admin')
def reject_event(event_id):
    """Boss rejects an event."""
    username = session.get('username')
    # Records belong to the arena's boss, not to the assistant acting on them,
    # so scope by the arena. Using the actor's own id silently matched no rows.
    owner_id = current_boss_id()

    if boss_approval.reject_event(event_id, owner_id, username):
        flash("Event rejected by {}.".format(username), "info")
    else:
        flash("Nothing was changed. It may already have been actioned.", "error")
    
    return redirect(url_for('boss_approvals'))

if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, port=5001)
