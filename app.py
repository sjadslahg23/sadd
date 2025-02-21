import os
from datetime import datetime, date
import logging

from flask import Flask, render_template_string, request, redirect, url_for, flash, session, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from jinja2 import DictLoader

# لمحاولة تصدير التقارير إلى PDF (تأكد من تثبيت pdfkit و wkhtmltopdf)
import pdfkit

# إنشاء التطبيق وتكوينه مع تحديد مجلد الصور كـ static folder
app = Flask(__name__, static_folder='images')
app.config['SECRET_KEY'] = 'secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# تهيئة الإضافات
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# إعداد تسجيل الأحداث
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

###############################################
# إعداد قالب الأساس باستخدام DictLoader
###############################################
base_template = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
  <title>نظام إدارة المدرسة</title>
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    body { padding-top: 70px; }
    /* العلامة المائية */
    body::after {
      content: "";
      background: url("{{ url_for('static', filename='watermark.png') }}") no-repeat center center;
      opacity: 0.1;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: -1;
    }
    {% if session.get('theme', 'light') == 'dark' %}
    body { background-color: #343a40; color: white; }
    .card { background-color: #495057; }
    {% endif %}
  </style>
</head>
<body>
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
    <a class="navbar-brand" href="{{ url_for('index') }}">SchoolMS</a>
    <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarNav">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarNav">
      <ul class="navbar-nav">
        {% if current_user.is_authenticated %}
          {% if current_user.role in ['admin', 'responsible'] %}
            <li class="nav-item"><a class="nav-link" href="{{ url_for('admin_dashboard') }}">لوحة التحكم</a></li>
          {% elif current_user.role == 'teacher' %}
            <li class="nav-item"><a class="nav-link" href="{{ url_for('teacher.teacher_dashboard') }}">لوحة التحكم</a></li>
          {% elif current_user.role == 'student' %}
            <li class="nav-item"><a class="nav-link" href="{{ url_for('student.student_dashboard') }}">الإحصائيات</a></li>
          {% endif %}
          <li class="nav-item"><a class="nav-link" href="{{ url_for('attendance.weekly_attendance') }}">الغيابات الأسبوعية</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('attendance.list') }}">سجلات الحضور</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('attendance.charts') }}">مخططات الغياب</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('report.write_report') }}">كتابة تقرير</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('toggle_theme') }}">تبديل الوضع</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('logout') }}">تسجيل الخروج</a></li>
        {% else %}
          <li class="nav-item"><a class="nav-link" href="{{ url_for('login') }}">تسجيل الدخول</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('register') }}">إنشاء حساب</a></li>
        {% endif %}
      </ul>
    </div>
  </nav>
  <div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </div>
  <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.5.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
templates = {"base.html": base_template}
app.jinja_loader = DictLoader(templates)

###############################################
# نماذج البيانات (Data Models)
###############################################
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # student, admin, teacher, responsible

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    stage = db.Column(db.String(50), nullable=False)      # first, second, third
    section = db.Column(db.String(10), nullable=False)      # A, B, C, D
    guardian_info = db.Column(db.String(250))
    academic_record = db.Column(db.Text)
    medical_reports = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    attendance_records = db.relationship('Attendance', backref='student', lazy=True)
    fees = db.relationship('Fee', backref='student', lazy=True)

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(150))
    qualifications = db.Column(db.Text)
    experience_years = db.Column(db.Integer)
    evaluation = db.Column(db.Text)
    teaching_level = db.Column(db.String(50))  # المرحلة التي يدرس فيها (first, second, third)
    attendance_records = db.relationship('Attendance', backref='teacher', lazy=True)
    schedule = db.relationship('Schedule', backref='teacher', lazy=True)
    exams = db.relationship('Exam', backref='teacher', lazy=True)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    period = db.Column(db.String(50))
    reason = db.Column(db.String(100))
    status = db.Column(db.String(10), nullable=False)  # present / absent
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_date = db.Column(db.Date, nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    details = db.Column(db.Text)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20))
    period = db.Column(db.String(50))
    subject = db.Column(db.String(150))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))

class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50))   # paid, unpaid
    invoice_details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(150))
    isbn = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=1)

###############################################
# إعداد تسجيل الدخول باستخدام Flask-Login
###############################################
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

###############################################
# Blueprints – تقسيم النظام إلى وحدات
###############################################

# (1) وحدة إدارة الطلاب
student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_student():
    if current_user.role != 'admin':
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            full_name = request.form['full_name']
            birth_date = datetime.strptime(request.form['birth_date'], '%Y-%m-%d').date()
            stage = request.form['stage']
            section = request.form['section']
            guardian_info = request.form.get('guardian_info', '')
            academic_record = request.form.get('academic_record', '')
            medical_reports = request.form.get('medical_reports', '')
            notes = request.form.get('notes', '')
            new_student = Student(
                full_name=full_name,
                birth_date=birth_date,
                stage=stage,
                section=section,
                guardian_info=guardian_info,
                academic_record=academic_record,
                medical_reports=medical_reports,
                notes=notes
            )
            db.session.add(new_student)
            db.session.commit()
            flash("تم إضافة الطالب بنجاح", "success")
            logger.info(f"تم إضافة الطالب: {full_name}")
            return redirect(url_for('student.list_students'))
        except Exception as e:
            logger.error("خطأ في إضافة الطالب: " + str(e))
            flash("حدث خطأ أثناء إضافة الطالب", "danger")
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إضافة طالب</h2>
    <form method="post">
      <div class="form-group">
        <label>الاسم الكامل</label>
        <input type="text" name="full_name" class="form-control" required>
      </div>
      <div class="form-group">
        <label>تاريخ الميلاد</label>
        <input type="date" name="birth_date" class="form-control" required>
      </div>
      <div class="form-group">
        <label>المرحلة</label>
        <select name="stage" class="form-control" required>
          <option value="first">المرحلة الأولى</option>
          <option value="second">المرحلة الثانية</option>
          <option value="third">المرحلة الثالثة</option>
        </select>
      </div>
      <div class="form-group">
        <label>الشعبة</label>
        <select name="section" class="form-control" required>
          <option value="A">أ</option>
          <option value="B">ب</option>
          <option value="C">ج</option>
          <option value="D">د</option>
        </select>
      </div>
      <div class="form-group">
        <label>معلومات ولي الأمر</label>
        <input type="text" name="guardian_info" class="form-control">
      </div>
      <div class="form-group">
        <label>السجل الأكاديمي</label>
        <textarea name="academic_record" class="form-control"></textarea>
      </div>
      <div class="form-group">
        <label>التقارير الطبية</label>
        <textarea name="medical_reports" class="form-control"></textarea>
      </div>
      <div class="form-group">
        <label>ملاحظات خاصة</label>
        <textarea name="notes" class="form-control"></textarea>
      </div>
      <button type="submit" class="btn btn-primary">إضافة الطالب</button>
    </form>
    {% endblock %}
    """)

@student_bp.route('/list')
@login_required
def list_students():
    students = Student.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>قائمة الطلاب</h2>
    <table class="table">
      <thead>
        <tr>
          <th>الاسم الكامل</th>
          <th>تاريخ الميلاد</th>
          <th>المرحلة</th>
          <th>الشعبة</th>
        </tr>
      </thead>
      <tbody>
        {% for student in students %}
        <tr>
          <td>{{ student.full_name }}</td>
          <td>{{ student.birth_date }}</td>
          <td>{{ student.stage }}</td>
          <td>{{ student.section }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endblock %}
    """, students=students)

@student_bp.route('/dashboard')
@login_required
def student_dashboard():
    # الربط الافتراضي بين حساب المستخدم وسجل الطالب بناءً على الاسم (يمكن التعديل)
    student_record = Student.query.filter_by(full_name=current_user.username).first()
    if not student_record:
        return render_template_string("""
        {% extends "base.html" %}
        {% block content %}
          <h2>لا يوجد سجل طالب مرتبط بحسابك.</h2>
        {% endblock %}
        """)
    total = len(student_record.attendance_records)
    absences = len([r for r in student_record.attendance_records if r.status == 'absent'])
    absence_percentage = (absences / total * 100) if total > 0 else 0
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>لوحة تحكم الطالب</h2>
    <p>أهلاً {{ student.full_name }}</p>
    <p>نسبة الغياب: {{ absence_percentage }}%</p>
    {% endblock %}
    """, student=student_record, absence_percentage=absence_percentage)

# (2) وحدة إدارة المدرسين
teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

@teacher_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_teacher():
    if current_user.role != 'admin':
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            full_name = request.form['full_name']
            specialization = request.form.get('specialization', '')
            qualifications = request.form.get('qualifications', '')
            experience_years = int(request.form.get('experience_years', 0))
            evaluation = request.form.get('evaluation', '')
            teaching_level = request.form.get('teaching_level', '')
            new_teacher = Teacher(
                full_name=full_name,
                specialization=specialization,
                qualifications=qualifications,
                experience_years=experience_years,
                evaluation=evaluation,
                teaching_level=teaching_level
            )
            db.session.add(new_teacher)
            db.session.commit()
            flash("تم إضافة المدرس بنجاح", "success")
            logger.info(f"تم إضافة المدرس: {full_name}")
            return redirect(url_for('teacher.list_teachers'))
        except Exception as e:
            logger.error("خطأ في إضافة المدرس: " + str(e))
            flash("حدث خطأ أثناء إضافة المدرس", "danger")
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إضافة مدرس</h2>
    <form method="post">
      <div class="form-group">
        <label>الاسم الكامل</label>
        <input type="text" name="full_name" class="form-control" required>
      </div>
      <div class="form-group">
        <label>التخصص</label>
        <input type="text" name="specialization" class="form-control">
      </div>
      <div class="form-group">
        <label>المؤهلات</label>
        <textarea name="qualifications" class="form-control"></textarea>
      </div>
      <div class="form-group">
        <label>سنوات الخبرة</label>
        <input type="number" name="experience_years" class="form-control" required>
      </div>
      <div class="form-group">
        <label>التقييم</label>
        <textarea name="evaluation" class="form-control"></textarea>
      </div>
      <div class="form-group">
        <label>المرحلة التي يدرس فيها</label>
        <select name="teaching_level" class="form-control" required>
          <option value="first">المرحلة الأولى</option>
          <option value="second">المرحلة الثانية</option>
          <option value="third">المرحلة الثالثة</option>
        </select>
      </div>
      <button type="submit" class="btn btn-primary">إضافة المدرس</button>
    </form>
    {% endblock %}
    """)

@teacher_bp.route('/list')
@login_required
def list_teachers():
    teachers = Teacher.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>قائمة المدرسين</h2>
    <table class="table">
      <thead>
        <tr>
          <th>الاسم الكامل</th>
          <th>التخصص</th>
          <th>سنوات الخبرة</th>
          <th>المرحلة التي يدرس فيها</th>
        </tr>
      </thead>
      <tbody>
        {% for teacher in teachers %}
        <tr>
          <td>{{ teacher.full_name }}</td>
          <td>{{ teacher.specialization }}</td>
          <td>{{ teacher.experience_years }}</td>
          <td>{{ teacher.teaching_level }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endblock %}
    """, teachers=teachers)

@teacher_bp.route('/dashboard')
@login_required
def teacher_dashboard():
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>لوحة تحكم المدرس</h2>
    <p>أهلاً {{ current_user.username }}</p>
    <p>يمكنك إدارة جداولك وحضور طلابك.</p>
    {% endblock %}
    """)

# (3) وحدة إدارة الحضور والغياب
attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@attendance_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_attendance():
    if current_user.role not in ['admin', 'teacher']:
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            record_type = request.form['record_type']
            date_str = request.form.get('date', date.today().strftime('%Y-%m-%d'))
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            period = request.form.get('period', '')
            reason = request.form.get('reason', '')
            status = request.form['status']
            if record_type == 'student':
                student_id = int(request.form['student_id'])
                new_record = Attendance(
                    date=attendance_date,
                    period=period,
                    reason=reason,
                    status=status,
                    student_id=student_id
                )
            else:
                teacher_id = int(request.form['teacher_id'])
                new_record = Attendance(
                    date=attendance_date,
                    period=period,
                    reason=reason,
                    status=status,
                    teacher_id=teacher_id
                )
            db.session.add(new_record)
            db.session.commit()
            flash("تم إضافة سجل الحضور/الغياب بنجاح", "success")
            logger.info("تم إضافة سجل حضور/غياب")
            return redirect(url_for('attendance.list'))
        except Exception as e:
            logger.error("خطأ في إضافة سجل الحضور: " + str(e))
            flash("حدث خطأ أثناء إضافة سجل الحضور/الغياب", "danger")
    students = Student.query.all()
    teachers = Teacher.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إضافة سجل حضور/غياب</h2>
    <form method="post">
      <div class="form-group">
        <label>نوع السجل</label>
        <select name="record_type" class="form-control" required>
          <option value="student">طالب</option>
          <option value="teacher">مدرس</option>
        </select>
      </div>
      <div class="form-group">
        <label>التاريخ</label>
        <input type="date" name="date" class="form-control" value="{{ request.args.get('current_date', date.today().strftime('%Y-%m-%d')) }}">
      </div>
      <div class="form-group">
        <label>الحصة</label>
        <input type="text" name="period" class="form-control">
      </div>
      <div class="form-group">
        <label>سبب الغياب (إن وجد)</label>
        <input type="text" name="reason" class="form-control">
      </div>
      <div class="form-group">
        <label>الحالة</label>
        <select name="status" class="form-control" required>
          <option value="present">حاضر</option>
          <option value="absent">غائب</option>
        </select>
      </div>
      <div class="form-group" id="student_select">
        <label>الطالب</label>
        <select name="student_id" class="form-control">
          {% for student in students %}
          <option value="{{ student.id }}">{{ student.full_name }} - {{ student.stage }} - {{ student.section }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-group" id="teacher_select" style="display:none;">
        <label>المدرس</label>
        <select name="teacher_id" class="form-control">
          {% for teacher in teachers %}
          <option value="{{ teacher.id }}">{{ teacher.full_name }}</option>
          {% endfor %}
        </select>
      </div>
      <button type="submit" class="btn btn-primary">إضافة السجل</button>
    </form>
    <script>
      document.querySelector('select[name="record_type"]').addEventListener('change', function() {
        if(this.value === 'student'){
          document.getElementById('student_select').style.display = 'block';
          document.getElementById('teacher_select').style.display = 'none';
        } else {
          document.getElementById('student_select').style.display = 'none';
          document.getElementById('teacher_select').style.display = 'block';
        }
      });
    </script>
    {% endblock %}
    """, students=students, teachers=teachers, date=date)

@attendance_bp.route('/list')
@login_required
def list():
    records = Attendance.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>سجلات الحضور والغياب</h2>
    <table class="table">
      <thead>
        <tr>
          <th>التاريخ</th>
          <th>الحصة</th>
          <th>السبب</th>
          <th>الحالة</th>
          <th>الطالب/المدرس</th>
        </tr>
      </thead>
      <tbody>
        {% for record in records %}
        <tr>
          <td>{{ record.date }}</td>
          <td>{{ record.period }}</td>
          <td>{{ record.reason }}</td>
          <td>{{ record.status }}</td>
          <td>
            {% if record.student %}
              {{ record.student.full_name }}
            {% elif record.teacher %}
              {{ record.teacher.full_name }}
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endblock %}
    """, records=records)

# إضافة تسجيل الغيابات الأسبوعية لكل مرحلة وشعبة
@attendance_bp.route('/weekly', methods=['GET', 'POST'])
@login_required
def weekly_attendance():
    if current_user.role not in ['admin', 'teacher']:
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        stage = request.form.get('stage')
        section = request.form.get('section')
        week_date_str = request.form.get('week_date')
        absence_ids = request.form.getlist('absent')
        week_date = datetime.strptime(week_date_str, '%Y-%m-%d').date()
        for sid in absence_ids:
            att = Attendance(date=week_date, period="أسبوعي", reason="", status="absent", student_id=int(sid))
            db.session.add(att)
        db.session.commit()
        flash("تم تسجيل الغيابات الأسبوعية", "success")
        return redirect(url_for('attendance.list'))
    else:
        stage = request.args.get('stage')
        section = request.args.get('section')
        week_date = request.args.get('week_date')
        students = []
        if stage and section and week_date:
            students = Student.query.filter_by(stage=stage, section=section).all()
        return render_template_string("""
        {% extends "base.html" %}
        {% block content %}
        <h2>تسجيل الغيابات الأسبوعية</h2>
        <form method="get" action="{{ url_for('attendance.weekly_attendance') }}">
          <div class="form-group">
            <label>المرحلة</label>
            <select name="stage" class="form-control" required>
              <option value="first" {% if request.args.get('stage')=='first' %}selected{% endif %}>المرحلة الأولى</option>
              <option value="second" {% if request.args.get('stage')=='second' %}selected{% endif %}>المرحلة الثانية</option>
              <option value="third" {% if request.args.get('stage')=='third' %}selected{% endif %}>المرحلة الثالثة</option>
            </select>
          </div>
          <div class="form-group">
            <label>الشعبة</label>
            <select name="section" class="form-control" required>
              <option value="A" {% if request.args.get('section')=='A' %}selected{% endif %}>أ</option>
              <option value="B" {% if request.args.get('section')=='B' %}selected{% endif %}>ب</option>
              <option value="C" {% if request.args.get('section')=='C' %}selected{% endif %}>ج</option>
              <option value="D" {% if request.args.get('section')=='D' %}selected{% endif %}>د</option>
            </select>
          </div>
          <div class="form-group">
            <label>تاريخ الأسبوع (بداية الأسبوع)</label>
            <input type="date" name="week_date" class="form-control" value="{{ request.args.get('week_date','') }}" required>
          </div>
          <button type="submit" class="btn btn-info">عرض الطلاب</button>
        </form>
        {% if students %}
        <hr>
        <form method="post" action="{{ url_for('attendance.weekly_attendance') }}">
          <input type="hidden" name="stage" value="{{ request.args.get('stage') }}">
          <input type="hidden" name="section" value="{{ request.args.get('section') }}">
          <input type="hidden" name="week_date" value="{{ request.args.get('week_date') }}">
          <table class="table">
            <thead>
              <tr>
                <th>اختر الغياب</th>
                <th>اسم الطالب</th>
              </tr>
            </thead>
            <tbody>
              {% for student in students %}
              <tr>
                <td><input type="checkbox" name="absent" value="{{ student.id }}"></td>
                <td>{{ student.full_name }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
          <button type="submit" class="btn btn-primary">تسجيل الغيابات</button>
        </form>
        {% endif %}
        {% endblock %}
        """, students=students)

# عرض المخططات البيانية لنسبة الغياب لكل مرحلة وشعبة
@attendance_bp.route('/charts')
@login_required
def charts():
    data = []
    stages = ['first', 'second', 'third']
    sections = ['A', 'B', 'C', 'D']
    for st in stages:
        for sec in sections:
            students = Student.query.filter_by(stage=st, section=sec).all()
            total = len(students)
            total_absences = 0
            for student in students:
                abs_count = Attendance.query.filter_by(student_id=student.id, status="absent").count()
                total_absences += abs_count
            percentage = (total_absences / total * 100) if total > 0 else 0
            data.append({"stage": st, "section": sec, "total": total, "absences": total_absences, "percentage": percentage})
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>مخططات نسبة الغياب لكل مرحلة وشعبة</h2>
    <canvas id="absenceChart" width="800" height="400"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
      var ctx = document.getElementById('absenceChart').getContext('2d');
      var chartData = {
        labels: [{% for item in data %}"{{ item.stage }}-{{ item.section }}",{% endfor %}],
        datasets: [{
          label: 'نسبة الغياب (%)',
          data: [{% for item in data %}{{ item.percentage }},{% endfor %}],
          backgroundColor: 'rgba(255, 99, 132, 0.7)',
          borderColor: 'rgba(255, 99, 132, 1)',
          borderWidth: 1
        }]
      };
      var absenceChart = new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: {
          scales: {
            y: { beginAtZero: true, max: 100 }
          }
        }
      });
    </script>
    {% endblock %}
    """, data=data)

# (4) وحدة إدارة الجداول الزمنية والامتحانات (تبقى كما في الكود السابق)
schedule_bp = Blueprint('schedule', __name__, url_prefix='/schedule')

@schedule_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_schedule():
    if current_user.role != 'admin':
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            day = request.form['day']
            period = request.form['period']
            subject = request.form['subject']
            teacher_id = int(request.form['teacher_id'])
            new_schedule = Schedule(day=day, period=period, subject=subject, teacher_id=teacher_id)
            db.session.add(new_schedule)
            db.session.commit()
            flash("تم إضافة الجدول بنجاح", "success")
            logger.info("تم إضافة جدول زمني")
            return redirect(url_for('schedule.list_schedule'))
        except Exception as e:
            logger.error("خطأ في إضافة الجدول: " + str(e))
            flash("حدث خطأ أثناء إضافة الجدول", "danger")
    teachers = Teacher.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إضافة جدول زمني</h2>
    <form method="post">
      <div class="form-group">
        <label>اليوم</label>
        <input type="text" name="day" class="form-control" required>
      </div>
      <div class="form-group">
        <label>الحصة</label>
        <input type="text" name="period" class="form-control" required>
      </div>
      <div class="form-group">
        <label>المادة</label>
        <input type="text" name="subject" class="form-control" required>
      </div>
      <div class="form-group">
        <label>المدرس</label>
        <select name="teacher_id" class="form-control" required>
          {% for teacher in teachers %}
          <option value="{{ teacher.id }}">{{ teacher.full_name }}</option>
          {% endfor %}
        </select>
      </div>
      <button type="submit" class="btn btn-primary">إضافة الجدول</button>
    </form>
    {% endblock %}
    """, teachers=teachers)

@schedule_bp.route('/list')
@login_required
def list_schedule():
    schedules = Schedule.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>قائمة الجداول الزمنية</h2>
    <table class="table">
      <thead>
        <tr>
          <th>اليوم</th>
          <th>الحصة</th>
          <th>المادة</th>
          <th>المدرس</th>
        </tr>
      </thead>
      <tbody>
        {% for sched in schedules %}
        <tr>
          <td>{{ sched.day }}</td>
          <td>{{ sched.period }}</td>
          <td>{{ sched.subject }}</td>
          <td>{{ sched.teacher.full_name }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endblock %}
    """, schedules=schedules)

@schedule_bp.route('/exam/add', methods=['GET', 'POST'])
@login_required
def add_exam():
    if current_user.role != 'admin':
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            exam_date = datetime.strptime(request.form['exam_date'], '%Y-%m-%d').date()
            subject = request.form['subject']
            teacher_id = int(request.form['teacher_id'])
            details = request.form.get('details', '')
            new_exam = Exam(exam_date=exam_date, subject=subject, teacher_id=teacher_id, details=details)
            db.session.add(new_exam)
            db.session.commit()
            flash("تم إضافة الامتحان بنجاح", "success")
            logger.info("تم إضافة امتحان")
            return redirect(url_for('schedule.list_exams'))
        except Exception as e:
            logger.error("خطأ في إضافة الامتحان: " + str(e))
            flash("حدث خطأ أثناء إضافة الامتحان", "danger")
    teachers = Teacher.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إضافة امتحان</h2>
    <form method="post">
      <div class="form-group">
        <label>تاريخ الامتحان</label>
        <input type="date" name="exam_date" class="form-control" required>
      </div>
      <div class="form-group">
        <label>المادة</label>
        <input type="text" name="subject" class="form-control" required>
      </div>
      <div class="form-group">
        <label>المدرس</label>
        <select name="teacher_id" class="form-control" required>
          {% for teacher in teachers %}
          <option value="{{ teacher.id }}">{{ teacher.full_name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-group">
        <label>تفاصيل</label>
        <textarea name="details" class="form-control"></textarea>
      </div>
      <button type="submit" class="btn btn-primary">إضافة الامتحان</button>
    </form>
    {% endblock %}
    """, teachers=teachers)

@schedule_bp.route('/exam/list')
@login_required
def list_exams():
    exams = Exam.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>قائمة الامتحانات</h2>
    <table class="table">
      <thead>
        <tr>
          <th>تاريخ الامتحان</th>
          <th>المادة</th>
          <th>المدرس</th>
          <th>تفاصيل</th>
        </tr>
      </thead>
      <tbody>
        {% for exam in exams %}
        <tr>
          <td>{{ exam.exam_date }}</td>
          <td>{{ exam.subject }}</td>
          <td>{{ exam.teacher.full_name }}</td>
          <td>{{ exam.details }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endblock %}
    """, exams=exams)

# (5) وحدة التواصل والإشعارات
communication_bp = Blueprint('communication', __name__, url_prefix='/communication')

@communication_bp.route('/notifications')
@login_required
def notifications():
    notes = Notification.query.filter_by(user_id=current_user.id).all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>الإشعارات</h2>
    <ul class="list-group">
      {% for note in notes %}
      <li class="list-group-item">
        <strong>{{ note.title }}</strong> - {{ note.message }} <em>{{ note.created_at }}</em>
      </li>
      {% endfor %}
    </ul>
    {% endblock %}
    """, notes=notes)

@communication_bp.route('/message/send', methods=['GET', 'POST'])
@login_required
def send_message():
    if request.method == 'POST':
        try:
            receiver_id = int(request.form['receiver_id'])
            content = request.form['content']
            new_message = Message(sender_id=current_user.id, receiver_id=receiver_id, content=content)
            db.session.add(new_message)
            db.session.commit()
            flash("تم إرسال الرسالة بنجاح", "success")
            logger.info("تم إرسال رسالة")
            return redirect(url_for('communication.inbox'))
        except Exception as e:
            logger.error("خطأ في إرسال الرسالة: " + str(e))
            flash("حدث خطأ أثناء إرسال الرسالة", "danger")
    users = User.query.filter(User.id != current_user.id).all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إرسال رسالة</h2>
    <form method="post">
      <div class="form-group">
        <label>المستقبل</label>
        <select name="receiver_id" class="form-control">
          {% for user in users %}
          <option value="{{ user.id }}">{{ user.username }} ({{ user.role }})</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-group">
        <label>نص الرسالة</label>
        <textarea name="content" class="form-control"></textarea>
      </div>
      <button type="submit" class="btn btn-primary">إرسال الرسالة</button>
    </form>
    {% endblock %}
    """, users=users)

@communication_bp.route('/inbox')
@login_required
def inbox():
    msgs = Message.query.filter_by(receiver_id=current_user.id).all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>صندوق الوارد</h2>
    <ul class="list-group">
      {% for msg in msgs %}
      <li class="list-group-item">
        <strong>من: {{ msg.sender_id }}</strong> - {{ msg.content }} <em>{{ msg.timestamp }}</em>
      </li>
      {% endfor %}
    </ul>
    {% endblock %}
    """, msgs=msgs)

# (6) وحدة إدارة المكتبة (اختياري)
library_bp = Blueprint('library', __name__, url_prefix='/library')

@library_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_book():
    if current_user.role != 'admin':
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            title = request.form['title']
            author = request.form.get('author', '')
            isbn = request.form.get('isbn', '')
            quantity = int(request.form.get('quantity', 1))
            new_book = Book(title=title, author=author, isbn=isbn, quantity=quantity)
            db.session.add(new_book)
            db.session.commit()
            flash("تم إضافة الكتاب بنجاح", "success")
            logger.info("تم إضافة كتاب للمكتبة")
            return redirect(url_for('library.list_books'))
        except Exception as e:
            logger.error("خطأ في إضافة الكتاب: " + str(e))
            flash("حدث خطأ أثناء إضافة الكتاب", "danger")
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إضافة كتاب</h2>
    <form method="post">
      <div class="form-group">
        <label>العنوان</label>
        <input type="text" name="title" class="form-control" required>
      </div>
      <div class="form-group">
        <label>المؤلف</label>
        <input type="text" name="author" class="form-control">
      </div>
      <div class="form-group">
        <label>الرقم الدولي (ISBN)</label>
        <input type="text" name="isbn" class="form-control">
      </div>
      <div class="form-group">
        <label>الكمية</label>
        <input type="number" name="quantity" class="form-control" value="1">
      </div>
      <button type="submit" class="btn btn-primary">إضافة الكتاب</button>
    </form>
    {% endblock %}
    """)

@library_bp.route('/list')
@login_required
def list_books():
    books = Book.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>كتب المكتبة</h2>
    <table class="table">
      <thead>
        <tr>
          <th>العنوان</th>
          <th>المؤلف</th>
          <th>الرقم الدولي</th>
          <th>الكمية</th>
        </tr>
      </thead>
      <tbody>
        {% for book in books %}
        <tr>
          <td>{{ book.title }}</td>
          <td>{{ book.author }}</td>
          <td>{{ book.isbn }}</td>
          <td>{{ book.quantity }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endblock %}
    """, books=books)

# (7) وحدة إدارة الرسوم والمحاسبة
finance_bp = Blueprint('finance', __name__, url_prefix='/finance')

@finance_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_fee():
    if current_user.role != 'admin':
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            student_id = int(request.form['student_id'])
            amount = float(request.form['amount'])
            status = request.form['status']
            invoice_details = request.form.get('invoice_details', '')
            new_fee = Fee(student_id=student_id, amount=amount, status=status, invoice_details=invoice_details)
            db.session.add(new_fee)
            db.session.commit()
            flash("تم إضافة سجل الرسوم بنجاح", "success")
            logger.info("تم إضافة سجل رسوم")
            return redirect(url_for('finance.list_fees'))
        except Exception as e:
            logger.error("خطأ في إضافة سجل الرسوم: " + str(e))
            flash("حدث خطأ أثناء إضافة سجل الرسوم", "danger")
    students = Student.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>إضافة سجل رسوم</h2>
    <form method="post">
      <div class="form-group">
        <label>الطالب</label>
        <select name="student_id" class="form-control">
          {% for student in students %}
          <option value="{{ student.id }}">{{ student.full_name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-group">
        <label>المبلغ</label>
        <input type="number" step="0.01" name="amount" class="form-control" required>
      </div>
      <div class="form-group">
        <label>الحالة</label>
        <select name="status" class="form-control" required>
          <option value="paid">مدفوع</option>
          <option value="unpaid">غير مدفوع</option>
        </select>
      </div>
      <div class="form-group">
        <label>تفاصيل الفاتورة</label>
        <textarea name="invoice_details" class="form-control"></textarea>
      </div>
      <button type="submit" class="btn btn-primary">إضافة سجل الرسوم</button>
    </form>
    {% endblock %}
    """, students=students)

@finance_bp.route('/list')
@login_required
def list_fees():
    fees = Fee.query.all()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>سجلات الرسوم</h2>
    <table class="table">
      <thead>
        <tr>
          <th>الطالب</th>
          <th>المبلغ</th>
          <th>الحالة</th>
          <th>تفاصيل الفاتورة</th>
        </tr>
      </thead>
      <tbody>
        {% for fee in fees %}
        <tr>
          <td>{{ fee.student.full_name }}</td>
          <td>{{ fee.amount }}</td>
          <td>{{ fee.status }}</td>
          <td>{{ fee.invoice_details }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endblock %}
    """, fees=fees)

###############################################
# وحدة كتابة التقارير (Report)
###############################################
report_bp = Blueprint('report', __name__, url_prefix='/report')

@report_bp.route('/write', methods=['GET', 'POST'])
@login_required
def write_report():
    if request.method == 'POST':
        report_content = request.form.get('report_content')
        # تحويل المحتوى إلى PDF باستخدام pdfkit (تأكد من إعداد wkhtmltopdf)
        pdf = pdfkit.from_string(report_content, False)
        response = app.response_class(pdf, mimetype='application/pdf')
        response.headers['Content-Disposition'] = 'attachment; filename=report.pdf'
        return response
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>كتابة تقرير</h2>
    <form method="post">
      <textarea id="report_editor" name="report_content" style="width:100%; height:400px;"></textarea>
      <br>
      <button type="submit" class="btn btn-success">تصدير التقرير إلى PDF</button>
      <button type="button" class="btn btn-primary" onclick="window.print();">طباعة التقرير</button>
    </form>
    <script src="https://cdn.tiny.cloud/1/no-api-key/tinymce/5/tinymce.min.js" referrerpolicy="origin"></script>
    <script>
      tinymce.init({
        selector: '#report_editor',
        language: 'ar'
      });
    </script>
    {% endblock %}
    """)

###############################################
# الصفحة الرئيسية مع حركة أنيميشن لجعلها ديناميكية
###############################################
@app.route('/')
def index():
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <div class="animated-banner" style="text-align:center; margin-bottom:20px;">
      <h2 style="animation: slide 5s infinite;">مرحباً بكم في نظام إدارة المدرسة الاحترافي</h2>
    </div>
    <style>
      @keyframes slide {
        0% { transform: translateX(-100%); opacity: 0; }
        50% { transform: translateX(0); opacity: 1; }
        100% { transform: translateX(100%); opacity: 0; }
      }
    </style>
    <h3>هذه هي الصفحة الرئيسية.</h3>
    {% endblock %}
    """)

###############################################
# مسارات تسجيل الدخول والتسجيل والخروج
###############################################
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.student_dashboard'))
        elif current_user.role in ['admin', 'responsible']:
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher.teacher_dashboard'))
        else:
            return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("تم تسجيل الدخول بنجاح", "success")
            if user.role == 'student':
                return redirect(url_for('student.student_dashboard'))
            elif user.role in ['admin', 'responsible']:
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher.teacher_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <!-- الشعار في الزاوية اليسرى -->
    <div class="row">
      <div class="col-12 text-left">
        <div style="display: flex; align-items: center;">
          <img src="{{ url_for('static', filename='gov_logo.png') }}" alt="Gov Logo" style="height: 50px; margin-right: 10px;">
          <div>
            <small>جمهورية العراق وزارة التربية المديرية العامة للتعليم المهني // المثنى</small>
          </div>
        </div>
      </div>
    </div>
    <!-- اسم المدرسة المتحرك وصورة المدرسة -->
    <div class="text-center my-4">
      <h1 id="school-name" style="font-family: 'Cursive', sans-serif;">أعدادية الحسين للحاسوب وتقنية المعلومات</h1>
      <img src="{{ url_for('static', filename='school.jpg') }}" alt="School Image" class="img-fluid" style="max-height: 200px;">
    </div>
    <!-- نموذج تسجيل الدخول -->
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card">
          <div class="card-body">
            <h3 class="card-title text-center">تسجيل الدخول</h3>
            <form method="post">
              <div class="form-group">
                <label>اسم المستخدم</label>
                <input type="text" name="username" class="form-control" required>
              </div>
              <div class="form-group">
                <label>كلمة المرور</label>
                <input type="password" name="password" class="form-control" required>
              </div>
              <button type="submit" class="btn btn-primary btn-block">دخول</button>
            </form>
            <div class="text-center mt-3">
              <a href="{{ url_for('register') }}">إنشاء حساب جديد</a>
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- تذييل الصفحة مع أسماء المطورين وأيقونة إنستقرام -->
    <footer class="mt-4 text-center">
      <p>تمت البرمجة والتطوير بواسطة 
        <a href="https://www.instagram.com/your_instagram_handle1" target="_blank">
          سجاد قيصر الوائلي o9cc0 <img src="{{ url_for('static', filename='instagram.png') }}" alt="Instagram" style="height:20px;">
        </a>
        و
        <a href="https://www.instagram.com/your_instagram_handle2" target="_blank">
          علي المرتضى صافي f.2kv <img src="{{ url_for('static', filename='instagram.png') }}" alt="Instagram" style="height:20px;">
        </a>
      </p>
    </footer>
    <script>
      const schoolName = document.getElementById('school-name');
      schoolName.style.animation = "colorChange 5s infinite";
    </script>
    <style>
      @keyframes colorChange {
        0% { color: red; }
        25% { color: blue; }
        50% { color: green; }
        75% { color: orange; }
        100% { color: purple; }
      }
    </style>
    {% endblock %}
    """)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash("أنت مسجل بالفعل", "info")
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        if password != confirm_password:
            flash("كلمة المرور غير متطابقة", "danger")
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash("اسم المستخدم موجود بالفعل", "danger")
            return redirect(url_for('register'))
        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("تم إنشاء الحساب بنجاح. يرجى تسجيل الدخول.", "success")
        return redirect(url_for('login'))
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <!-- الشعار في الزاوية اليسرى -->
    <div class="row">
      <div class="col-12 text-left">
        <div style="display: flex; align-items: center;">
          <img src="{{ url_for('static', filename='gov_logo.png') }}" alt="Gov Logo" style="height: 50px; margin-right: 10px;">
          <div>
            <small>جمهورية العراق وزارة التربية المديرية العامة للتعليم المهني // المثنى</small>
          </div>
        </div>
      </div>
    </div>
    <!-- اسم المدرسة المتحرك وصورة المدرسة -->
    <div class="text-center my-4">
      <h1 id="school-name" style="font-family: 'Cursive', sans-serif;">أعدادية الحسين للحاسوب وتقنية المعلومات</h1>
      <img src="{{ url_for('static', filename='school.jpg') }}" alt="School Image" class="img-fluid" style="max-height: 200px;">
    </div>
    <!-- نموذج التسجيل -->
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card">
          <div class="card-body">
            <h3 class="card-title text-center">إنشاء حساب جديد</h3>
            <form method="post">
              <div class="form-group">
                <label>اسم المستخدم</label>
                <input type="text" name="username" class="form-control" required>
              </div>
              <div class="form-group">
                <label>كلمة المرور</label>
                <input type="password" name="password" class="form-control" required>
              </div>
              <div class="form-group">
                <label>تأكيد كلمة المرور</label>
                <input type="password" name="confirm_password" class="form-control" required>
              </div>
              <div class="form-group">
                <label>الدور</label>
                <select name="role" class="form-control" required>
                  <option value="student">طالب</option>
                  <option value="admin">مدير/مسؤول</option>
                  <option value="teacher">مدرس</option>
                  <option value="responsible">مسؤول</option>
                </select>
              </div>
              <button type="submit" class="btn btn-success btn-block">إنشاء الحساب</button>
            </form>
            <div class="text-center mt-3">
              <a href="{{ url_for('login') }}">العودة إلى تسجيل الدخول</a>
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- تذييل الصفحة -->
    <footer class="mt-4 text-center">
      <p>تمت البرمجة والتطوير بواسطة 
        <a href="https://www.instagram.com/your_instagram_handle1" target="_blank">
          سجاد قيصر الوائلي o9cc0 <img src="{{ url_for('static', filename='instagram.png') }}" alt="Instagram" style="height:20px;">
        </a>
        و
        <a href="https://www.instagram.com/your_instagram_handle2" target="_blank">
          علي المرتضى صافي o9cc0 <img src="{{ url_for('static', filename='instagram.png') }}" alt="Instagram" style="height:20px;">
        </a>
      </p>
    </footer>
    <script>
      const schoolName = document.getElementById('school-name');
      schoolName.style.animation = "colorChange 5s infinite";
    </script>
    <style>
      @keyframes colorChange {
        0% { color: red; }
        25% { color: blue; }
        50% { color: green; }
        75% { color: orange; }
        100% { color: purple; }
      }
    </style>
    {% endblock %}
    """)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("تم تسجيل الخروج", "success")
    return redirect(url_for('login'))

@app.route('/toggle-theme')
def toggle_theme():
    current_theme = session.get('theme', 'light')
    session['theme'] = 'dark' if current_theme == 'light' else 'light'
    return redirect(request.referrer or url_for('index'))

###############################################
# تسجيل Blueprints
###############################################
app.register_blueprint(student_bp)
app.register_blueprint(teacher_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(communication_bp)
app.register_blueprint(library_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(report_bp)

###############################################
# لوحة تحكم الإدارة (Dashboard)
###############################################
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role not in ['admin', 'responsible']:
        flash("غير مسموح بالدخول", "danger")
        return redirect(url_for('index'))
    attendance_count = Attendance.query.count()
    student_count = Student.query.count()
    teacher_count = Teacher.query.count()
    fee_count = Fee.query.count()
    return render_template_string("""
    {% extends "base.html" %}
    {% block content %}
    <h2>لوحة تحكم الإدارة</h2>
    <div class="row">
      <div class="col-md-3">
        <div class="card text-white bg-primary mb-3">
          <div class="card-body">
            <h5 class="card-title">الطلاب</h5>
            <p class="card-text">{{ student_count }}</p>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white bg-success mb-3">
          <div class="card-body">
            <h5 class="card-title">المدرسين</h5>
            <p class="card-text">{{ teacher_count }}</p>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white bg-warning mb-3">
          <div class="card-body">
            <h5 class="card-title">سجلات الحضور</h5>
            <p class="card-text">{{ attendance_count }}</p>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white bg-danger mb-3">
          <div class="card-body">
            <h5 class="card-title">سجلات الرسوم</h5>
            <p class="card-text">{{ fee_count }}</p>
          </div>
        </div>
      </div>
    </div>
    <canvas id="chart" width="400" height="200"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
      var ctx = document.getElementById('chart').getContext('2d');
      var myChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['الطلاب', 'المدرسين', 'الحضور', 'الرسوم'],
          datasets: [{
            label: 'الإحصائيات',
            data: [{{ student_count }}, {{ teacher_count }}, {{ attendance_count }}, {{ fee_count }}],
            backgroundColor: [
              'rgba(54, 162, 235, 0.7)',
              'rgba(75, 192, 192, 0.7)',
              'rgba(255, 206, 86, 0.7)',
              'rgba(255, 99, 132, 0.7)'
            ],
            borderColor: [
              'rgba(54, 162, 235, 1)',
              'rgba(75, 192, 192, 1)',
              'rgba(255, 206, 86, 1)',
              'rgba(255, 99, 132, 1)'
            ],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          scales: { y: { beginAtZero: true } }
        }
      });
    </script>
    {% endblock %}
    """, student_count=student_count, teacher_count=teacher_count, attendance_count=attendance_count, fee_count=fee_count)

###############################################
# اختبار وحدات (Unit Testing) – مثال بسيط
###############################################
@app.cli.command('test')
def test():
    import unittest
    class BasicTests(unittest.TestCase):
        def setUp(self):
            app.config['TESTING'] = True
            self.app = app.test_client()
        def test_home(self):
            response = self.app.get('/')
            self.assertEqual(response.status_code, 200)
    tests = unittest.TestLoader().loadTestsFromTestCase(BasicTests)
    unittest.TextTestRunner(verbosity=2).run(tests)

###############################################
# التشغيل الرئيسي للتطبيق
###############################################
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # إنشاء مستخدم إداري افتراضي إذا لم يكن موجوداً
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Flask App is Running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)