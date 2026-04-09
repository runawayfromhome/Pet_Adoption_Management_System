import os
import re
import csv
from io import StringIO
from flask import Response
from datetime import datetime, timedelta
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import select
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv 
import psycopg2
from supabase import create_client

load_dotenv() 
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(CURRENT_DIR, 'templates')
static_dir = os.path.join(CURRENT_DIR, 'static')

app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=static_dir
)
app.secret_key = os.environ.get("SECRET_KEY", "petadopt_secret_2026_key")


def upload_url(stored_path):
    if not stored_path:
        return ""
    value = str(stored_path).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return url_for('static', filename='uploads/' + value)


supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase_bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "pet-assets")
supabase = None
if supabase_url and supabase_key:
    try:
        supabase = create_client(supabase_url, supabase_key)
    except Exception as exc:
        print(f"Supabase disabled: {exc}")
        supabase = None


remote_db = (
    os.environ.get('DATABASE_URL')
    or os.environ.get('POSTGRES_URL')
    or os.environ.get('POSTGRES_PRISMA_URL')
    or os.environ.get('POSTGRES_URL_NON_POOLING')
)
if not remote_db:
    raise RuntimeError(
        "Database URL is missing. Set DATABASE_URL or POSTGRES_URL in environment variables."
    )

if remote_db.startswith("postgres://"):
    remote_db = remote_db.replace("postgres://", "postgresql://", 1)

if not remote_db.startswith("postgresql://"):
    raise RuntimeError("DATABASE_URL must be a PostgreSQL connection string.")

print("PostgreSQL configuration detected.")

app.config['SQLALCHEMY_DATABASE_URI'] = remote_db

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.jinja_env.globals['upload_url'] = upload_url


def local_upload_path(stored_path):
    if not stored_path:
        return None
    value = str(stored_path).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return None
    return os.path.join(app.config['UPLOAD_FOLDER'], value)

# 3. Now the functions can use the 'supabase' variable safely
def save_upload(file):
    if not supabase:
        return None, "Supabase client not initialized."




oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
)

upload_dir = os.path.join(app.static_folder, 'uploads')
os.makedirs(upload_dir, exist_ok=True)
app.config['UPLOAD_FOLDER'] = upload_dir
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'office@petadopt.ph')
mail = Mail(app)
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    phone_number = db.Column(db.String(20)) # Notice the name
    home_address = db.Column(db.String(200))
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    applications = db.relationship('AdoptionApplication', backref='adopter', lazy=True)


class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    breed = db.Column(db.String(50))
    photo = db.Column(db.String(200))
    age_category = db.Column(db.String(20))    
    gender = db.Column(db.String(10))          
    size = db.Column(db.String(10))            
    energy_level = db.Column(db.String(20))    
    spayed_neutered = db.Column(db.String(5))  
    vac_status = db.Column(db.String(30))      
    vac_date = db.Column(db.String(20))        
    special_needs = db.Column(db.Text, default="N/A")
    other_description = db.Column(db.Text)
    status = db.Column(db.String(20), default="Available")
    adopter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    applications = db.relationship('ApplicationItem', backref='pet_record', cascade="all, delete", lazy=True)
    adoption_date = db.Column(db.DateTime, nullable=True)
    current_adopter = db.relationship('User', backref='adopted_pets')




class AdoptionApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    adopter_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    id_proof = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="Pending") 

    phone = db.Column(db.String(20), nullable=True)
    occupation = db.Column(db.String(100), nullable=True)

    q_home_type = db.Column(db.String(255), nullable=True)
    q_yard_access = db.Column(db.String(255), nullable=True)
    household_size = db.Column(db.String(100), nullable=True)
    
    q_hours_alone = db.Column(db.String(100), nullable=True)
    other_pets = db.Column(db.String(255), nullable=True)
    q_pet_experience = db.Column(db.Text, nullable=True)
    financial_readiness = db.Column(db.String(50), nullable=True)
    
    home_picture = db.Column(db.String(200), nullable=True) 
    
    application_date = db.Column(db.DateTime, default=datetime.utcnow) 
    approval_date = db.Column(db.DateTime, nullable=True)
    pickup_date = db.Column(db.DateTime, nullable=True)
    claim_date = db.Column(db.DateTime, nullable=True)                  
    
    items = db.relationship('ApplicationItem', backref='application', cascade="all, delete", lazy=True)
    admin_remarks = db.Column(db.Text, nullable=True)

class ApplicationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('adoption_application.id'), nullable=False)
    pet_id = db.Column(db.Integer, db.ForeignKey('pet.id'), nullable=False)
    pet = db.relationship('Pet', overlaps="applications,pet_record")

class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    force_password_change = db.Column(db.Boolean, default=False)
    is_default = db.Column(db.Boolean, default=False)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(255), nullable=False) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

def get_current_admin():
    admin_id = session.get('admin_id')
    if admin_id:
        return db.session.get(AdminUser, admin_id)
    return None

def log_action(action_text):
    curr = get_current_admin()
    if curr:
        log = AuditLog(admin_username=curr.username, action=action_text)
        db.session.add(log)
        db.session.commit()

def save_upload(file):
    if not file or file.filename == "": return None, "No file selected."
    filename = secure_filename(file.filename)
    unique_name = f"{uuid4().hex}_{filename}"
    file_content = None

    # Prefer Supabase when configured; if upload fails, fall back to local storage.
    if supabase:
        try:
            file_content = file.read()
            supabase.storage.from_(supabase_bucket).upload(unique_name, file_content)
            public_url = supabase.storage.from_(supabase_bucket).get_public_url(unique_name)
            return public_url, None
        except Exception as exc:
            print(f"Supabase upload failed ({exc}). Using local upload fallback.")

    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        if file_content is not None:
            with open(file_path, 'wb') as out:
                out.write(file_content)
        else:
            file.save(file_path)
        return unique_name, None
    except Exception as exc:
        return None, f"Failed to save upload locally: {exc}"

def is_authentic_email(email):
    return re.fullmatch(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email or "")

def is_valid_name(name, max_len=100):
    return name and len(name) <= max_len and re.fullmatch(r"[A-Za-z][A-Za-z\s'\-\.]{1,}", name)

def is_valid_username(u, max_len=50):
    return u and len(u) <= max_len and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-\.]{2,}", u)

def is_strong_password(p, min_len=8):
    return p and len(p) >= min_len

with app.app_context():
    db.create_all() 
    admin_exists = db.session.execute(select(AdminUser).filter_by(username="admin")).scalar()
    if not admin_exists:
        db.session.add(AdminUser(
            username="admin", 
            password_hash=generate_password_hash("password123"), 
            force_password_change=True, 
            is_default=True
        ))
        db.session.commit()

@app.route('/')
def index():
    return render_template('public/index.html', pets=Pet.query.filter_by(status="Available").all())

@app.route('/adopt/<int:pet_id>', methods=['GET', 'POST'])
def adopt(pet_id):
    if not session.get('user_id'):
        flash("Please log in to apply.", "info")
        return redirect(url_for('adopter_login', next=url_for('adopt', pet_id=pet_id)))

    pet = Pet.query.get_or_404(pet_id)
    
    if request.method == 'POST':
        file_id = request.files.get('id_proof')
        filename_id, err_id = save_upload(file_id)
        if err_id: 
            flash(err_id, "danger")
            return redirect(request.url)

        file_home = request.files.get('home_picture')
        filename_home, err_home = save_upload(file_home)
        if err_home:
            flash(err_home, "danger")
            return redirect(request.url)

        def get_answer(field_name, trigger_val='Other'):
            val = request.form.get(field_name)
            if val == trigger_val:
                return request.form.get(f"{field_name}_other")
            elif field_name == 'surrendered_pet' and val == 'Yes':
                explanation = request.form.get(f"{field_name}_other")
                return f"Yes: {explanation}"
            return val

        adopter_name = request.form.get('name')
        adopter_email = request.form.get('email')

        new_app = AdoptionApplication(
            user_id=session.get('user_id'),
            adopter_name=adopter_name,
            email=adopter_email,
            id_proof=filename_id,
            home_picture=filename_home,
            status="Pending",
            phone=request.form.get('phone'),
            occupation=request.form.get('occupation'),
            q_home_type=get_answer('q_home_type'),
            q_yard_access=get_answer('q_yard_access'),
            household_size=get_answer('household_size'),
            q_hours_alone=request.form.get('q_hours_alone'),
            other_pets=get_answer('other_pets'),
            financial_readiness=get_answer('financial_readiness'),
            q_pet_experience=request.form.get('q_pet_experience')
        )
        
        db.session.add(new_app)
        db.session.flush()

        item = ApplicationItem(application_id=new_app.id, pet_id=pet.id)
        db.session.add(item)
        db.session.commit()

        if request.form.get('send_email_copy') == 'on':
            try:
                msg = Message("Copy of Your PetAdopt Application", recipients=[adopter_email])
                msg.html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; background-color: #fdfdfb;">
                    <h2 style="color: #1a2a3a; border-bottom: 2px solid #c5a059; padding-bottom: 10px;">Application Received!</h2>
                    <p>Hi <strong>{adopter_name}</strong>,</p>
                    <p>Thank you for submitting your application to adopt <strong>{pet.name}</strong>. Here is a copy of your submitted questionnaire:</p>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;">
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Home Type:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.q_home_type} ({new_app.q_yard_access})</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Household Size:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.household_size}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Other Pets:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.other_pets}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Hours Alone:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.q_hours_alone}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Experience:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.q_pet_experience}</td></tr>
                    </table>
                    <p style="margin-top: 30px; font-size: 14px; color: #666;">You can view your full responses anytime on your Adopter Dashboard.</p>
                </div>
                """
                mail.send(msg)
            except Exception as e:
                print(f"Failed to send application receipt email: {e}")

        flash(f"Application for {pet.name} submitted!", "success")
        return redirect(url_for('adopter_dashboard'))

    return render_template('public/adopt.html', pet=pet)

@app.route('/dashboard')
def adopter_dashboard():
    uid = session.get('user_id')
    if not uid: 
        flash("Unauthorized access. Please login as an adopter first.", "danger")
        return redirect(url_for('adopter_login'))
    
    user = db.session.get(User, uid)
    # Just fetch the applications and send them to the template
    reqs = AdoptionApplication.query.filter_by(user_id=uid).all()
    
    return render_template('adopter/adopter_dashboard.html', user=user, requests=reqs)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        admin = AdminUser.query.filter_by(username=u).first()
        if admin and check_password_hash(admin.password_hash, p):
            session['admin_id'] = admin.id
            return redirect(url_for('admin_dashboard'))
        flash("Invalid username or password.", "danger")
        return redirect(request.url) 
    return render_template('admin/admin.html', login_mode=True)
    

@app.route('/admin/dashboard')
def admin_dashboard():
    curr_admin = get_current_admin()
    if not curr_admin: 
        flash("Please log in first.", "warning")
        return redirect(url_for('admin_login'))

    pending = AdoptionApplication.query.filter_by(status="Pending").all()
    from sqlalchemy import or_, and_
    
    active_tasks = AdoptionApplication.query.filter(
        and_(
        or_(
            AdoptionApplication.pickup_date != None),
        AdoptionApplication.status.notin_(["Declined", "Claimed"])
        )
    ).order_by(AdoptionApplication.pickup_date.asc()).all()
    scheduled = AdoptionApplication.query.filter(
        or_(
            AdoptionApplication.pickup_date != None)
    ).order_by(AdoptionApplication.pickup_date.asc()).all()

    approved_apps = AdoptionApplication.query.filter(AdoptionApplication.approval_date != None).all()
    total_seconds = 0
    count = 0
    
    for app in approved_apps:
        diff = app.approval_date - app.application_date
        total_seconds += diff.total_seconds()
        count += 1
    
    avg_hours = (total_seconds / count) / 3600 if count > 0 else 0

    total_capacity = 50
    current_occupancy = Pet.query.filter_by(status="Available").count()
    available_spots = total_capacity - current_occupancy
    occupancy_percent = (current_occupancy / total_capacity) * 100
    
    reserved_count = Pet.query.filter_by(status="Approved").count()

    history = AdoptionApplication.query.filter(
        AdoptionApplication.status.in_(["Returned", "Claimed", "Declined"])
    ).order_by(AdoptionApplication.application_date.desc()).all()
    total_finalized_adoptions = AdoptionApplication.query.filter_by(status="Claimed").count()
    return render_template('admin/admin_dashboard.html', 
                       pets=Pet.query.all(), 
                       pending_applications=pending, 
                       scheduled_apps=active_tasks,     
                       current_occupancy=current_occupancy,
                        available_spots=total_capacity - current_occupancy,
                        occupancy_percent=(current_occupancy / total_capacity) * 100,
                       logs=AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(50).all(),
                       history_apps=history, total_adoptions=total_finalized_adoptions,avg_processing_time=round(avg_hours, 2), reserved_pets=reserved_count,
                       login_mode=False)

@app.route('/admin/add_pet', methods=['POST'])
def add_pet():
    if not get_current_admin(): return redirect(url_for('admin_login'))
    file = request.files.get('photo')
    filename, error = save_upload(file)
    if error:
        flash(error, "danger")
        return redirect(url_for('admin_dashboard'))
    
    new_pet = Pet(
        name=request.form.get('name'), breed=request.form.get('breed'),
        age_category=request.form.get('age_category'), gender=request.form.get('gender'),
        size=request.form.get('size'), energy_level=request.form.get('energy_level'),
        spayed_neutered=request.form.get('spayed_neutered'), vac_status=request.form.get('vac_status'),
        vac_date=request.form.get('vac_date'), special_needs=request.form.get('special_needs') or "N/A",
        other_description=request.form.get('other_description'), photo=filename
    )
    db.session.add(new_pet)
    db.session.commit()
    log_action(f"Registered new pet: {new_pet.name}")
    flash("Pet added!", "success")
    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/edit_pet/<int:pet_id>', methods=['GET', 'POST'])
def edit_pet(pet_id):
    if not get_current_admin(): return redirect(url_for('admin_login'))
    pet = Pet.query.get_or_404(pet_id)
    if request.method == 'POST':
        pet.name = request.form.get('name')
        pet.breed = request.form.get('breed')
        pet.age_category = request.form.get('age_category')
        pet.gender = request.form.get('gender')
        pet.size = request.form.get('size')
        pet.energy_level = request.form.get('energy_level')
        pet.spayed_neutered = request.form.get('spayed_neutered')
        pet.vac_status = request.form.get('vac_status')
        pet.vac_date = request.form.get('vac_date')
        pet.special_needs = request.form.get('special_needs')
        pet.other_description = request.form.get('other_description')
        file = request.files.get('photo')
        if file and file.filename != '':
            new_img, err = save_upload(file)
            if not err:
                if pet.photo: 
                    try:
                        old_path = local_upload_path(pet.photo)
                        if old_path and os.path.exists(old_path):
                            os.remove(old_path)
                    except: pass
                pet.photo = new_img
        db.session.commit()
        log_action(f"Updated profile for: {pet.name}")
        flash("Pet profile updated successfully!", "success")
        return redirect(url_for('admin_inventory'))
    
    return render_template('admin/edit_pet.html', pet=pet)

@app.route('/admin/delete_pet/<int:pet_id>')
def delete_pet(pet_id):
    if not get_current_admin(): return redirect(url_for('admin_login'))
    pet = Pet.query.get_or_404(pet_id)
    pet_name = pet.name
    if pet.photo:
        try:
            old_path = local_upload_path(pet.photo)
            if old_path and os.path.exists(old_path):
                os.remove(old_path)
        except: pass
    db.session.delete(pet)
    db.session.commit()
    log_action(f"Permanently removed pet: {pet_name}")
    flash("Pet removed.", "info")
    return redirect(request.referrer or url_for('admin_dashboard')) 

@app.route('/schedule_pickup/<int:app_id>', methods=['POST'])
def schedule_pickup(app_id):
    application = AdoptionApplication.query.get_or_404(app_id)
    date_str = request.form.get('pickup_date')
    
    if date_str:
        selected_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        
        if selected_date < datetime.now():
            flash("You cannot schedule a pickup in the past.", "danger")
            return redirect(request.referrer)
            
        if selected_date.weekday() == 6: 
            flash("The sanctuary is closed on Sundays.", "danger")
            return redirect(request.referrer)

        application.pickup_date = selected_date
        db.session.commit()
        flash("Pickup appointment confirmed!", "success")
        
    return redirect(request.referrer)

@app.route('/admin/delete_admin/<int:admin_id>', methods=['POST'])
def delete_admin(admin_id):
    curr_admin = get_current_admin()
    if not curr_admin: return redirect(url_for('admin_login'))
    
    if curr_admin.id == admin_id:
        flash("You cannot revoke your own access.", "danger")
        return redirect(url_for('manage_staff'))
        
    entered_password = request.form.get('auth_password')
    if not check_password_hash(curr_admin.password_hash, entered_password):
        flash("Security Authorization Failed: Incorrect password.", "danger")
        return redirect(url_for('manage_staff'))

    target_admin = db.session.get(AdminUser, admin_id)
    if target_admin:
        if target_admin.is_default:
            flash("System Security: Cannot delete the default root admin.", "danger")
            return redirect(url_for('manage_staff'))
            
        target_name = target_admin.username
        db.session.delete(target_admin)
        db.session.commit()
        log_action(f"Revoked access for staff member: {target_name}")
        flash(f"Access permanently revoked for {target_name}.", "success")
        
    return redirect(url_for('manage_staff'))

@app.route('/admin/inventory')
def admin_inventory():
    if not get_current_admin(): return redirect(url_for('admin_login'))
    
    search_query = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = Pet.query
    
    if search_query:
        query = query.filter(
            (Pet.name.like(f'%{search_query}%')) | 
            (Pet.breed.like(f'%{search_query}%'))
        )
        
    if status_filter:
        query = query.filter(Pet.status == status_filter)
    
    pets = query.all()
    
    return render_template('admin/admin_inventory.html', pets=pets)

@app.route('/admin/schedule')
def admin_schedule():
    if not get_current_admin(): return redirect(url_for('admin_login'))
    pending = AdoptionApplication.query.filter_by(status="Pending").all()
    from sqlalchemy import or_, and_
    tasks = AdoptionApplication.query.filter(and_(
        or_(
            AdoptionApplication.pickup_date != None
        ),
        AdoptionApplication.status.notin_(["Claimed", "Declined"])
    )).all()
    
    return render_template('admin/admin_schedule.html', pending_applications=pending, scheduled_apps=tasks)

@app.route('/admin/archive')
def admin_archive():
    if not get_current_admin(): return redirect(url_for('admin_login'))
    history = AdoptionApplication.query.filter(AdoptionApplication.status.in_(["Returned", "Claimed"])).all()
    return render_template('admin/admin_archive.html', history_apps=history, logs=AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(50).all())

@app.route('/admin/adopter/<int:user_id>')
def admin_view_adopter(user_id):
    if not get_current_admin(): return redirect(url_for('admin_login'))
    
    target_user = db.session.get(User, user_id)
    if not target_user:
        flash("Adopter profile not found.", "danger")
        return redirect(request.referrer or url_for('admin_dashboard'))
    
    user_apps = AdoptionApplication.query.filter_by(user_id=user_id).order_by(AdoptionApplication.application_date.desc()).all()
    
    return render_template('admin/admin_adopter_profile.html', adopter=target_user, applications=user_apps)

@app.route('/admin/pet_profile/<int:pet_id>')
def admin_view_pet(pet_id):
    if not get_current_admin(): return redirect(url_for('admin_login'))
    
    pet = db.session.get(Pet, pet_id)
    if not pet:
        flash("Pet profile not found.", "danger")
        return redirect(request.referrer or url_for('admin_dashboard'))
        
    return render_template('admin/admin_pet_profile.html', pet=pet)

@app.route('/admin/adopters')
def admin_adopters():
    if not get_current_admin(): return redirect(url_for('admin_login'))
    
    search_query = request.args.get('search', '')
    
    query = User.query
    
    if search_query:
        query = query.filter(
            (User.full_name.like(f'%{search_query}%')) | 
            (User.email.like(f'%{search_query}%'))
        )
        
    all_users = query.all()
    
    return render_template('admin/admin_adopters.html', adopters=all_users)

@app.route('/admin/approve_application/<int:app_id>')
def approve_application(app_id):
    if not get_current_admin(): 
        return redirect(url_for('admin_login'))
    
    application = db.session.get(AdoptionApplication, app_id)

    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    if application.status != "Approved":
        application.status = "Approved"
        application.approval_date = datetime.now() 

        pet_names_list = []
        for item in application.items:
            item.pet.status = "Approved"
            pet_names_list.append(item.pet.name)
            
        pet_names_string = ", ".join(pet_names_list)
        
        try:
            msg = Message(f"Official Approval: Application for {pet_names_string}",
                          recipients=[application.email])

            msg.body = f"""Dear {application.adopter_name},

Congratulations! We are pleased to inform you that your formal application to adopt {pet_names_string} has been APPROVED.

Next Steps:

1. SCHEDULE FOR PICKUP
Please log in to your PetAdopt Dashboard to select a specific date and time for pickup. Our sanctuary is open Mon-Sat (9AM-4PM).

2. DOCUMENTS
Remember to bring the physical Government ID you used for your digital application.

We look forward to seeing you at our San Mateo Rizal Animal Welfare Office!

Best regards,
Patch & The PetAdopt Team
"""
            mail.send(msg)
            flash(f"Approval email sent for {pet_names_string} to {application.adopter_name}!", "success") 
        except Exception as e:
            flash(f"Approved, but email failed: {str(e)}", "warning")

        db.session.commit()
        log_action(f"Approved multi-pet adoption for: {pet_names_string}")
        
    return redirect(url_for('admin_schedule'))

@app.route('/register', methods=['GET', 'POST'])
def adopter_register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email').lower()
        pwd = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(request.url)
        else:
            token = uuid4().hex
            
            new_user = User(
                full_name=name, 
                email=email, 
                password_hash=generate_password_hash(pwd),
                is_verified=False,
                verification_token=token
            )
            db.session.add(new_user)
            db.session.commit()
            
            try:
                verify_url = url_for('verify_email', token=token, _external=True)
                
                msg = Message("Verify Your PetAdopt Account", recipients=[email])
                msg.body = f"Hi {name},\n\nPlease verify your email by clicking this link: {verify_url}"
                msg.html = f"""
                <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 30px; border: 1px solid #e0e0e0; border-radius: 8px; text-align: center; background-color: #fdfdfb;">
                    <h2 style="color: #1a2a3a; margin-bottom: 20px;">Welcome to PetAdopt!</h2>
                    <p style="color: #555; font-size: 16px; line-height: 1.6;">Hi <strong>{name}</strong>,</p>
                    <p style="color: #555; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                        Thank you for joining our sanctuary portal. To ensure the security of our platform and begin your adoption journey, please verify your email address.
                    </p>
                    <a href="{verify_url}" style="display: inline-block; padding: 14px 30px; background-color: #c5a059; color: #ffffff; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; text-transform: uppercase; border-radius: 4px;">
                        Verify My Account
                    </a>
                    <p style="color: #999; font-size: 12px; margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px;">
                        If the button above doesn't work, copy and paste this link into your browser:<br>
                        <a href="{verify_url}" style="color: #c5a059; word-break: break-all;">{verify_url}</a>
                    </p>
                    <p style="color: #999; font-size: 12px;">If you did not create this account, please ignore this email.</p>
                </div>
                """
                mail.send(msg)
                flash("Account created! Please check your email to verify your account before logging in.", "info")
            except Exception as e:
                flash(f"Account created, but failed to send verification email: {str(e)}", "warning")
                
            return redirect(url_for('adopter_login'))
            
    return render_template('adopter/adopter_auth.html', mode='register')

@app.route('/login', methods=['GET', 'POST'])
def adopter_login():
    next_page = request.args.get('next')

    if request.method == 'POST':
        email = request.form.get('email').lower()
        pwd = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, pwd):
            if not user.is_verified:
                flash("Please verify your email address before logging in. Check your inbox.", "warning")
                return redirect(request.url)
                
            session['user_id'] = user.id
            if next_page: 
                return redirect(next_page)
            return redirect(url_for('adopter_dashboard'))
            
        flash("Invalid credentials.", "danger")
        return redirect(request.url)

    return render_template('adopter/adopter_auth.html', mode='login')

@app.route('/login/google')
def google_login():
    return google.authorize_redirect(url_for('google_authorize', _external=True))

@app.route('/login/google/authorize')
def google_authorize():
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.gjson()
    email = user_info['email']
    name = user_info['name']

    user = User.query.filter_by(email=email).first()
    if not user:
        # We set is_verified=True here because Google already verified them!
        user = User(
            full_name=name, 
            email=email, 
            password_hash=generate_password_hash(uuid4().hex),
            is_verified=True  # <--- ADD THIS LINE
        )
        db.session.add(user)
        db.session.commit()
    else:
        # Optional: If an existing email user logs in via Google for the first time,
        # we can also verify them now since Google confirms ownership.
        if not user.is_verified:
            user.is_verified = True
            db.session.commit()

    session['user_id'] = user.id
    flash(f"Welcome, {name}!", "success")
    return redirect(url_for('adopter_dashboard'))

@app.route('/add_to_cart/<int:pet_id>')
def add_to_cart(pet_id):
    if 'cart' not in session:
        session['cart'] = []
    
    if pet_id not in session['cart']:
        session['cart'].append(pet_id)
        session.modified = True 
        flash("Pet added to your application list!", "success")
    else:
        flash("This pet is already in your selection.", "info")
    return redirect(request.referrer or url_for('index'))

@app.route('/remove_from_cart/<int:pet_id>')
def remove_from_cart(pet_id):
    if 'cart' in session:
        if pet_id in session['cart']:
            session['cart'].remove(pet_id)
            session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/cart')
def view_cart():
    if not session.get('user_id'):
        flash("Please log in to view your selection and proceed with adoption.", "info")
        return redirect(url_for('adopter_login', next=url_for('view_cart')))
    
    if 'cart' not in session or not session['cart']:
        flash("Your selection is empty. Please browse our gallery first.", "info")
        return redirect(url_for('index'))
    
    selected_pets = Pet.query.filter(Pet.id.in_(session['cart'])).all()
    return render_template('public/cart.html', pets=selected_pets)

@app.route('/profile', methods=['GET', 'POST'])
def adopter_profile():
    uid = session.get('user_id')
    if not uid:
        flash("Please log in to view your profile.", "danger")
        return redirect(url_for('adopter_login'))
        
    user = db.session.get(User, uid)
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        new_email = request.form.get('email').lower()
        
       
        if new_email != user.email:
            if User.query.filter_by(email=new_email).first():
                flash("That email is already registered to another account.", "danger")
                return redirect(url_for('adopter_profile'))
                
            
            user.email = new_email
            user.is_verified = False
            token = uuid4().hex
            user.verification_token = token
            
            try:
                verify_url = url_for('verify_email', token=token, _external=True)
                msg = Message("Verify Your PetAdopt Account", recipients=[new_email])
                
                msg.body = f"Hi {new_name},\n\nPlease verify your email by clicking this link: {verify_url}"
                
                msg.html = f"""
                <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 30px; border: 1px solid #e0e0e0; border-radius: 8px; text-align: center; background-color: #fdfdfb;">
                    <h2 style="color: #1a2a3a; margin-bottom: 20px;">Welcome to PetAdopt!</h2>
                    <p style="color: #555; font-size: 16px; line-height: 1.6;">Hi <strong>{new_name}</strong>,</p>
                    <p style="color: #555; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                        Thank you for joining our sanctuary portal. To ensure the security of our platform and begin your adoption journey, please verify your email address.
                    </p>
                    <a href="{verify_url}" style="display: inline-block; padding: 14px 30px; background-color: #c5a059; color: #ffffff; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; text-transform: uppercase; border-radius: 4px;">
                        Verify My Account
                    </a>
                    <p style="color: #999; font-size: 12px; margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px;">
                        If the button above doesn't work, copy and paste this link into your browser:<br>
                        <a href="{verify_url}" style="color: #c5a059; word-break: break-all;">{verify_url}</a>
                    </p>
                    <p style="color: #999; font-size: 12px;">If you did not create this account, please ignore this email.</p>
                </div>
                """
                
                mail.send(msg)
                
                db.session.commit()
                session.clear() # Log them out until they verify
                flash("Email updated! Please check your new inbox to verify and log back in.", "info")
                return redirect(url_for('adopter_login'))
            except Exception as e:
                flash("Failed to send verification email. Please try again.", "danger")
                return redirect(url_for('adopter_profile'))
        
        user.full_name = new_name
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for('adopter_profile'))
        
    return render_template('adopter/adopter_profile.html', user=user)

@app.route('/profile/password', methods=['POST'])
def adopter_password():
    uid = session.get('user_id')
    user = db.session.get(User, uid)
    
    curr_pass = request.form.get('current_password')
    new_pass = request.form.get('new_password')
    confirm_pass = request.form.get('confirm_password')

    # Logic: Only check current password if a real one was previously set
    # (Checking if the hash is a standard Werkzeug hash)
    is_traditional_user = user.password_hash.startswith('pbkdf2:sha256')

    if is_traditional_user:
        if not curr_pass or not check_password_hash(user.password_hash, curr_pass):
            flash("Incorrect current security key.", "danger")
            return redirect(url_for('adopter_profile'))

    if new_pass != confirm_pass:
        flash("New passwords do not match.", "warning")
    elif is_traditional_user and check_password_hash(user.password_hash, new_pass):
        flash("New password cannot be the same as your current one.", "warning")
    elif not is_strong_password(new_pass):
        flash("Security key must be at least 8 characters long.", "warning")
    else:
        user.password_hash = generate_password_hash(new_pass)
        db.session.commit()
        flash("Security key successfully updated.", "success")
        
    return redirect(url_for('adopter_profile'))

@app.route('/profile/delete', methods=['POST'])
def delete_account():
    uid = session.get('user_id')
    if not uid: return redirect(url_for('adopter_login'))
    user = db.session.get(User, uid)
    
    for app in user.applications:
        app.user_id = None
        
    db.session.delete(user)
    db.session.commit()
    
    session.clear()
    flash("Your account has been permanently deleted. We are sad to see you go!", "info")
    return redirect(url_for('index'))

@app.route('/admin/export_history')
def export_history():
    if not get_current_admin(): 
        return redirect(url_for('admin_login'))
        
    history = AdoptionApplication.query.filter(
        AdoptionApplication.status.in_(["Declined", "Claimed"])
    ).all()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['App ID', 'Adopter', 'Submission', 'Approval', 'Appointment', 'Finalized', 'Outcome', 'Admin Remarks'])
    
    for app in history:
        finalized_date = app.claim_date if app.status == 'Claimed' else app.application_date

        cw.writerow([
            f"APP-{app.id}",
            app.adopter_name,
            app.application_date.strftime('%Y-%m-%d %H:%M') if app.application_date else "N/A",
            app.approval_date.strftime('%Y-%m-%d %H:%M') if app.approval_date else "N/A",
            app.pickup_date.strftime('%Y-%m-%d %H:%M') if app.pickup_date else "N/A",
            finalized_date.strftime('%Y-%m-%d %H:%M') if finalized_date else "N/A",
            app.status.upper(),
            app.admin_remarks if app.admin_remarks else "N/A"
        ])
    
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=adoption_history_report.csv"}
    )


@app.route('/admin/manage_staff')
def manage_staff():
    if not get_current_admin(): 
        return redirect(url_for('admin_login'))
    
    all_admins = AdminUser.query.all()
    return render_template('admin/admin_list.html', all_admins=all_admins)

@app.route('/admin/add_admin', methods=['POST'])
def add_admin():
    if not get_current_admin(): 
        return redirect(url_for('admin_login'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    confirm = request.form.get('confirm_password')

    if password != confirm:
        flash("Passwords do not match!", "danger")
        return redirect(url_for('manage_staff'))
        
    if not is_strong_password(password):
        flash("Password must be at least 8 characters long.", "danger")
        return redirect(url_for('manage_staff'))

    if not is_valid_username(username):
        flash("Invalid username format.", "danger")
        return redirect(url_for('manage_staff'))
    
    existing = AdminUser.query.filter_by(username=username).first()
    if existing:
        flash("Username already exists!", "danger")
    else:
        hashed_pw = generate_password_hash(password)
        new_admin = AdminUser(username=username, password_hash=hashed_pw)
        db.session.add(new_admin)
        db.session.commit()
        log_action(f"Registered new staff member: {username}")
        flash(f"Staff account for {username} created successfully.", "success")
        
    return redirect(url_for('manage_staff'))


@app.route('/admin/update_password/<int:admin_id>', methods=['POST'])
def update_admin_password(admin_id):
    current_admin = get_current_admin()
    if not current_admin:
        return redirect(url_for('admin_login'))
    
    curr_pass = request.form.get('current_password')
    new_pass = request.form.get('new_password')
    confirm_pass = request.form.get('confirm_password')

    target_admin = db.session.get(AdminUser, admin_id)
    
    if not target_admin:
        flash("Admin record not found.", "danger")
        return redirect(url_for('manage_staff'))

    if not check_password_hash(current_admin.password_hash, curr_pass):
        flash("Authentication failed: Current password is incorrect.", "danger")
        return redirect(url_for('manage_staff'))

    if new_pass != confirm_pass:
        flash("Validation failed: New passwords do not match.", "warning")
        return redirect(url_for('manage_staff'))

    if not is_strong_password(new_pass):
        flash("Security error: New password is too weak.", "warning")
        return redirect(url_for('manage_staff'))

    target_admin.password_hash = generate_password_hash(new_pass)
    db.session.commit()
    
    log_action(f"Password updated for staff account: {target_admin.username}")
    flash(f"Success! Password for {target_admin.username} has been changed.", "success")
    
    return redirect(url_for('manage_staff'))

@app.route('/submit_application', methods=['POST'])
def submit_application():
    if not session.get('user_id'): return redirect(url_for('adopter_login'))
    
    cart = session.get('cart', [])
    if not cart:
        flash("No pets selected for adoption.", "warning")
        return redirect(url_for('index'))

    file_id = request.files.get('id_proof')
    filename_id, err_id = save_upload(file_id)
    if err_id:
        flash(f"ID Upload Error: {err_id}", "danger")
        return redirect(url_for('view_cart'))

    file_home = request.files.get('home_picture')
    filename_home, err_home = save_upload(file_home)
    if err_home:
        flash(f"Home Picture Error: {err_home}", "danger")
        return redirect(url_for('view_cart'))

    def get_answer(field_name, trigger_val='Other'):
        val = request.form.get(field_name)
        if val == trigger_val:
            return request.form.get(f"{field_name}_other")
        return val

    adopter_name = request.form.get('name')
    adopter_email = request.form.get('email')
    
    new_app = AdoptionApplication(
        user_id=session['user_id'],
        adopter_name=adopter_name,
        email=adopter_email,
        id_proof=filename_id,       
        home_picture=filename_home, 
        status="Pending",
        phone=request.form.get('phone'),
        occupation=request.form.get('occupation'),
        
        q_home_type=get_answer('q_home_type'),
        q_yard_access=get_answer('q_yard_access'),
        household_size=get_answer('household_size'),
        q_hours_alone=request.form.get('q_hours_alone'), 
        other_pets=get_answer('other_pets'),
        financial_readiness=get_answer('financial_readiness'),
        q_pet_experience=request.form.get('q_pet_experience')
    )
    
    db.session.add(new_app)
    db.session.flush()

    pet_names_list = []
    for pet_id in cart:
        item = ApplicationItem(application_id=new_app.id, pet_id=pet_id)
        db.session.add(item)
        pet = db.session.get(Pet, pet_id)
        if pet: pet_names_list.append(pet.name)
        
    db.session.commit()
    
    if request.form.get('send_email_copy') == 'on':
        try:
            pet_names_str = ", ".join(pet_names_list)
            msg = Message("Copy of Your PetAdopt Application", recipients=[adopter_email])
            msg.html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; background-color: #fdfdfb;">
                <h2 style="color: #1a2a3a; border-bottom: 2px solid #c5a059; padding-bottom: 10px;">Application Received!</h2>
                <p>Hi <strong>{adopter_name}</strong>,</p>
                <p>Thank you for submitting your application to adopt <strong>{pet_names_str}</strong>. Here is a copy of your submitted questionnaire:</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;">
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Home Type:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.q_home_type} ({new_app.q_yard_access})</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Household Size:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.household_size}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Other Pets:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.other_pets}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Hours Alone:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.q_hours_alone}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Experience:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{new_app.q_pet_experience}</td></tr>
                </table>
                <p style="margin-top: 30px; font-size: 14px; color: #666;">You can view your full responses anytime on your Adopter Dashboard.</p>
            </div>
            """
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send application receipt email: {e}")
    
    session.pop('cart', None)
    flash("Application submitted! You can review your responses below.", "success")
    return redirect(url_for('adopter_dashboard'))

# Quick fix to link existing adoptions
@app.route('/admin/sync_adopters')
def sync_adopters():
    # Find all applications that are 'Claimed' or 'Adopted'
    apps = AdoptionApplication.query.filter(AdoptionApplication.status.in_(['Claimed', 'Adopted'])).all()
    for app in apps:
        for item in app.items:
            # Set the pet's adopter_id to the person who applied
            item.pet.adopter_id = app.user_id
    db.session.commit()
    return "Adopters Synced!"

@app.route('/verify_email/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    
    if user:
        user.is_verified = True
        user.verification_token = None 
        db.session.commit()
        flash("Your email has been verified! You can now log in.", "success")
    else:
        flash("Invalid or expired verification link.", "danger")
        
    return redirect(url_for('adopter_login'))

@app.route('/admin/decline_application/<int:app_id>', methods=['POST']) # Added POST method
def decline_application(app_id):
    if not get_current_admin(): 
        return redirect(url_for('admin_login'))
    
    req = db.session.get(AdoptionApplication, app_id)
    if req:
        # GET THE REASON FROM THE MODAL FORM
        reason = request.form.get('admin_remarks')
        
        adopter_name = req.adopter_name
        recipient_email = req.email
        pet_names = ", ".join([item.pet_record.name for item in req.items])
        pet_name = pet_names if pet_names else "the pets"

        try:
            msg = Message(f"Update regarding your application for {pet_name}",
                          recipients=[recipient_email])
            
            # INCLUDE THE REASON IN THE EMAIL
            msg.body = f"""Dear {adopter_name},

Thank you for your interest in adopting from PetAdopt.

After a careful review, we have decided not to move forward with your request at this time.
Reason for Decision: {reason}

Our selection process is designed to ensure the most compatible match for the specific needs of each animal. We appreciate your heart for animal welfare.

Best regards,
The PetAdopt Team
"""
            mail.send(msg)
            flash(f"Decline notice sent to {recipient_email}.", "info")
        except Exception as e:
            flash(f"Request removed, but email failed: {str(e)}", "warning")

        # SAVE THE REASON TO THE DATABASE
        req.status = "Declined"
        req.admin_remarks = reason 
        log_action(f"Declined adoption request from {adopter_name}. Reason: {reason}")
        db.session.commit()
        
    return redirect(url_for('admin_schedule'))

@app.route('/admin/mark_claimed/<int:app_id>')
def mark_claimed(app_id):
    if not get_current_admin(): 
        return redirect(url_for('admin_login'))
    
    application = db.session.get(AdoptionApplication, app_id)
    if application:
        application.status = "Claimed"
        application.claim_date = datetime.now()  
        
        for item in application.items:
            item.pet.status = "Adopted"
            item.pet.adoption_date = datetime.utcnow()
            
        db.session.commit()
        log_action(f"Officially finalized adoption for Application #{app_id}")
        flash(f"Application #{app_id} marked as Claimed.", "success")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reports/monthly')
def monthly_report():
    if not get_current_admin(): 
        return redirect(url_for('admin_login'))

    today = datetime.utcnow()
    month = int(request.args.get('month', today.month))
    year = int(request.args.get('year', today.year))

    import calendar
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)

    finalized_apps = AdoptionApplication.query.filter(
        AdoptionApplication.status == "Claimed",
        AdoptionApplication.claim_date >= first_day,
        AdoptionApplication.claim_date <= last_day
    ).all()

    report_date_label = first_day.strftime('%B %Y')

    return render_template('admin/admin_report.html', 
                           applications=finalized_apps, 
                           report_date=report_date_label,
                           selected_month=month,
                           selected_year=year,
                           datetime=datetime)

@app.route('/logout')
def adopter_logout():
    session.clear()  
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

@app.route('/admin/logout')
def logout():
    session.clear() 
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email').lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = uuid4().hex
            user.verification_token = token
            db.session.commit()
            r_url = url_for('reset_password', token=token, _external=True)
            msg = Message("Reset Your PetAdopt Security Key", recipients=[email])
            msg.html = f"Click here to reset your key: <a href='{r_url}'>Reset Key</a>"
            mail.send(msg)
        flash("If registered, a reset link has been sent via Gmail.", "info")
        return redirect(url_for('adopter_login'))
    # This explicitly tells the template to show the 'forgot' recovery UI
    return render_template('adopter/adopter_auth.html', mode='forgot')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('adopter_login'))
    
    if request.method == 'POST':
        new_pass = request.form.get('password')
        user.password_hash = generate_password_hash(new_pass)
        user.verification_token = None
        db.session.commit()
        flash("Password reset successful! You can now log in.", "success")
        return redirect(url_for('adopter_login'))
        
    return render_template('adopter/adopter_auth.html', mode='reset', token=token)

if __name__ == '__main__':  
    app.run(debug=True)