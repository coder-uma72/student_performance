from re import search

from flask import render_template, redirect, request, jsonify, Response, send_file


from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
    create_access_token,
    set_access_cookies
)
from app import app
from extensions import db

from models.course import Course
from models.student import Student
from models.grade import Grade
from models.users import User

from werkzeug.security import check_password_hash

from io import BytesIO
from urllib.parse import parse_qs
from datetime import datetime

import pandas as pd
import numpy as np
print("ROUTES.PY LOADED")
def is_admin():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if user and user.role == "Admin":
        return True

    return False
def check_api_key():
    api_key = request.headers.get("X-API-Key")

    if api_key != app.config["API_KEY"]:
        return False

    return True
def get_current_student():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user:
        return None

    return Student.query.filter_by(email=user.email).first()
class MethodOverrideMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):

        if environ.get("REQUEST_METHOD") == "POST":

            content_length = environ.get("CONTENT_LENGTH")

            if content_length:
                length = int(content_length)

                body = environ["wsgi.input"].read(length)

                form_data = parse_qs(body.decode("utf-8"))

                method = form_data.get("_method", [None])[0]

                if method:
                    environ["REQUEST_METHOD"] = method.upper()

                # Put the body back so Flask can read request.form
                environ["wsgi.input"] = BytesIO(body)

        return self.app(environ, start_response)


# Connect middleware to Flask
app.wsgi_app = MethodOverrideMiddleware(app.wsgi_app)

# Home
@app.route("/")
def home():
    return "Student Performance Analytics System"


# GET /students
@app.route("/students", methods=["GET"])
@jwt_required()
def get_students():
    search = request.args.get("search", "").strip()

    if is_admin():
        query = Student.query

        if search:
            query = query.filter(
                (Student.name.ilike(f"%{search}%")) |
                (Student.email.ilike(f"%{search}%"))
            )

        students = query.all()

    else:
        student = get_current_student()

        if not student:
            return {"message": "Student account not found"}, 404

        if search:
            if search.lower() not in student.name.lower() and \
               search.lower() not in student.email.lower():
                students = []
            else:
                students = [student]
        else:
            students = [student]

        return render_template(
    "students/list.html",
    students=students,
    search=search
)
# GET /students/new
@app.route("/students/new", methods=["GET"])
@jwt_required()
def new_student():
    if not is_admin():
        return {"message": "Only Admin can add students"}, 403

    return render_template("students/new.html")


# POST /students
@app.route("/students", methods=["POST"])
@jwt_required()
def create_student():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()

    if not name:
        return {"message": "Name is required"}, 400

    if not email:
        return {"message": "Email is required"}, 400

    if "@" not in email or "." not in email:
        return {"message": "Invalid email format"}, 400

    existing_student = Student.query.filter_by(email=email).first()

    if existing_student:
        return {"message": "Email already exists"}, 409

    student = Student(name=name, email=email)

    db.session.add(student)
    db.session.commit()

    return redirect("/students")
# GET /students/<id>
@app.route("/students/<int:id>", methods=["GET"])
@jwt_required()
def get_student(id):
    if is_admin():
        student = Student.query.get_or_404(id)
        return render_template("students/details.html", student=student)

    student = get_current_student()

    if not student:
        return {"message": "Student account not found"}, 404

    if student.id != id:
        return {"message": "You can only view your own data"}, 403

    return render_template("students/details.html", student=student)


# GET /students/<id>/edit
@app.route("/students/<int:id>/edit", methods=["GET"])
@jwt_required()
def edit_student(id):
    if not is_admin():
        return {"message": "Only Admin can edit student records"}, 403

    student = Student.query.get_or_404(id)
    return render_template("students/edit.html", student=student)


# PUT /students/<id>
@app.route("/students/<int:id>", methods=["PUT"])
@jwt_required()
def update_student(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403

    student = Student.query.get_or_404(id)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()

    if not name:
        return {"message": "Name is required"}, 400

    if not email:
        return {"message": "Email is required"}, 400

    if "@" not in email or "." not in email:
        return {"message": "Invalid email format"}, 400

    existing_student = Student.query.filter(
        Student.email == email,
        Student.id != id
    ).first()

    if existing_student:
        return {"message": "Email already exists"}, 409

    student.name = name
    student.email = email

    db.session.commit()

    return redirect(f"/students/{id}")
# PATCH /students/<id>
@app.route("/students/<int:id>", methods=["PATCH"])
@jwt_required()
def patch_student(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403

    student = Student.query.get_or_404(id)

    if "name" in request.form:
        name = request.form["name"].strip()

        if not name:
            return {"message": "Name cannot be empty"}, 400

        student.name = name

    if "email" in request.form:
        email = request.form["email"].strip()

        if not email:
            return {"message": "Email cannot be empty"}, 400

        if "@" not in email or "." not in email:
            return {"message": "Invalid email format"}, 400

        existing_student = Student.query.filter(
            Student.email == email,
            Student.id != id
        ).first()

        if existing_student:
            return {"message": "Email already exists"}, 409

        student.email = email

    db.session.commit()

    return redirect(f"/students/{id}")
# DELETE /students/<id>
@app.route("/students/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_student(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403

    student = Student.query.get_or_404(id)

    # Delete grades belonging to this student first
    Grade.query.filter_by(student_id=id).delete()

    # Then delete the student
    db.session.delete(student)

    db.session.commit()

    return redirect("/students/view")
@app.route("/api/students", methods=["GET"])
def api_get_students():
    if not check_api_key():
        return {"message": "Invalid or missing API key"}, 401

    students = Student.query.all()

    return [
        {
            "id": student.id,
            "name": student.name,
            "email": student.email
        }
        for student in students
    ]
@app.route("/api/students", methods=["POST"])
def api_create_student():
    if not check_api_key():
        return {"message": "Invalid or missing API key"}, 401

    data = request.get_json()

    if not data:
        return {"message": "JSON data is required"}, 400

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()

    if not name:
        return {"message": "Name is required"}, 400

    if not email:
        return {"message": "Email is required"}, 400

    if "@" not in email or "." not in email:
        return {"message": "Invalid email format"}, 400

    existing_student = Student.query.filter_by(email=email).first()

    if existing_student:
        return {"message": "Email already exists"}, 409

    student = Student(
        name=name,
        email=email
    )

    db.session.add(student)
    db.session.commit()

    return {
        "message": "Student created successfully",
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email
        }
    }, 201
@app.route("/api/students/<int:id>", methods=["GET"])
def api_get_student(id):
    if not check_api_key():
        return {"message": "Invalid or missing API key"}, 401

    student = Student.query.get_or_404(id)

    return {
        "id": student.id,
        "name": student.name,
        "email": student.email
    }
@app.route("/api/students/<int:id>", methods=["PUT"])
def api_update_student(id):
    if not check_api_key():
        return {"message": "Invalid or missing API key"}, 401

    student = Student.query.get_or_404(id)

    data = request.get_json()

    if not data:
        return {"message": "JSON data is required"}, 400

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()

    if not name:
        return {"message": "Name is required"}, 400

    if not email:
        return {"message": "Email is required"}, 400

    if "@" not in email or "." not in email:
        return {"message": "Invalid email format"}, 400

    existing_student = Student.query.filter(
        Student.email == email,
        Student.id != id
    ).first()

    if existing_student:
        return {"message": "Email already exists"}, 409

    student.name = name
    student.email = email

    db.session.commit()

    return {
        "message": "Student updated successfully",
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email
        }
    }
@app.route("/api/students/<int:id>", methods=["PATCH"])
def api_patch_student(id):
    if not check_api_key():
        return {"message": "Invalid or missing API key"}, 401

    student = Student.query.get_or_404(id)

    data = request.get_json()

    if not data:
        return {"message": "JSON data is required"}, 400

    if "name" in data:
        name = data["name"].strip()

        if not name:
            return {"message": "Name cannot be empty"}, 400

        student.name = name

    if "email" in data:
        email = data["email"].strip()

        if not email:
            return {"message": "Email cannot be empty"}, 400

        if "@" not in email or "." not in email:
            return {"message": "Invalid email format"}, 400

        existing_student = Student.query.filter(
            Student.email == email,
            Student.id != id
        ).first()

        if existing_student:
            return {"message": "Email already exists"}, 409

        student.email = email

    db.session.commit()

    return {
        "message": "Student updated successfully",
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email
        }
    }

@app.route("/api/students/<int:id>", methods=["DELETE"])
def api_delete_student(id):
    if not check_api_key():
        return {"message": "Invalid or missing API key"}, 401

    student = Student.query.get_or_404(id)

    # Delete grades belonging to this student first
    Grade.query.filter_by(student_id=id).delete()

    # Then delete the student
    db.session.delete(student)

    db.session.commit()

    return {
        "message": "Student deleted successfully"
    }
# GET /courses
@app.route("/courses", methods=["GET"])
@jwt_required()
def get_courses():
    courses = Course.query.all()

    return render_template(
        "courses/list.html",
        courses=courses
    )

# GET /courses/new
@app.route("/courses/new", methods=["GET"])
@jwt_required()
def new_course():

    if not is_admin():
        return {"message": "Admin access required"}, 403

    return render_template("courses/new.html")

# POST /courses
@app.route("/courses", methods=["POST"])
@jwt_required()
def create_course():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip()

    if not name:
        return {"message": "Course name is required"}, 400

    if not code:
        return {"message": "Course code is required"}, 400

    existing_course = Course.query.filter_by(code=code).first()

    if existing_course:
        return {"message": "Course code already exists"}, 409

    course = Course(
        name=name,
        code=code
    )

    db.session.add(course)
    db.session.commit()

    return redirect("/courses")

# GET /courses/<id>
@app.route("/courses/<int:id>", methods=["GET"])
@jwt_required()
def get_course(id):

    course = Course.query.get_or_404(id)

    return render_template(
        "courses/details.html",
        course=course
    )


# GET /courses/<id>/edit
@app.route("/courses/<int:id>/edit", methods=["GET"])
@jwt_required()
def edit_course(id):

    if not is_admin():
        return {"message": "Admin access required"}, 403

    course = Course.query.get_or_404(id)

    return render_template(
        "courses/edit.html",
        course=course
    )

# PUT /courses/<id>
@app.route("/courses/<int:id>", methods=["PUT"])
@jwt_required()
def update_course(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403

    course = Course.query.get_or_404(id)

    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip()

    if not name:
        return {"message": "Course name is required"}, 400

    if not code:
        return {"message": "Course code is required"}, 400

    existing_course = Course.query.filter(
        Course.code == code,
        Course.id != id
    ).first()

    if existing_course:
        return {"message": "Course code already exists"}, 409

    course.name = name
    course.code = code

    db.session.commit()

    return redirect(f"/courses/{id}")

# PATCH /courses/<id>
@app.route("/courses/<int:id>", methods=["PATCH"])
@jwt_required()
def patch_course(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403

    course = Course.query.get_or_404(id)

    if "name" in request.form:
        name = request.form["name"].strip()

        if not name:
            return {"message": "Course name cannot be empty"}, 400

        course.name = name

    if "code" in request.form:
        code = request.form["code"].strip()

        if not code:
            return {"message": "Course code cannot be empty"}, 400

        existing_course = Course.query.filter(
            Course.code == code,
            Course.id != id
        ).first()

        if existing_course:
            return {"message": "Course code already exists"}, 409

        course.code = code

    db.session.commit()

    return redirect(f"/courses/{id}")
# DELETE /courses/<id>
@app.route("/courses/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_course(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403
    course = Course.query.get_or_404(id)
    Grade.query.filter_by(course_id=id).delete()
    db.session.delete(course)
    db.session.commit()

    return redirect("/courses")
# GET /grades/new
@app.route("/grades/new", methods=["GET"])
@jwt_required()
def new_grade():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    students = Student.query.all()
    courses = Course.query.all()

    return render_template(
        "grades/new.html",
        students=students,
        courses=courses
    )
# POST /grades
@app.route("/grades", methods=["POST"])
@jwt_required()
def create_grade():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    student_id = request.form.get("student_id")
    course_id = request.form.get("course_id")
    score = request.form.get("score")
    date_value = request.form.get("date")

    if not student_id:
        return {"message": "Student is required"}, 400

    if not course_id:
        return {"message": "Course is required"}, 400

    if not score:
        return {"message": "Score is required"}, 400

    if not date_value:
        return {"message": "Date is required"}, 400

    try:
        student_id = int(student_id)
        course_id = int(course_id)
        score = float(score)
    except ValueError:
        return {"message": "Invalid student, course, or score value"}, 400

    if score < 0 or score > 100:
        return {"message": "Score must be between 0 and 100"}, 400

    student = Student.query.get(student_id)

    if not student:
        return {"message": "Student not found"}, 404

    course = Course.query.get(course_id)

    if not course:
        return {"message": "Course not found"}, 404

    try:
        grade_date = datetime.strptime(
            date_value,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return {"message": "Invalid date format. Use YYYY-MM-DD"}, 400

    grade = Grade(
        student_id=student_id,
        course_id=course_id,
        score=score,
        date=grade_date
    )

    db.session.add(grade)
    db.session.commit()

    return redirect("/grades")
# GET /grades
@app.route("/grades", methods=["GET"])
@jwt_required()
def get_grades():

    if is_admin():
        grades = Grade.query.all()

    else:
        student = get_current_student()

        if not student:
            return {"message": "Student account not found"}, 404

        grades = Grade.query.filter_by(
            student_id=student.id
        ).all()

    return render_template(
        "grades/list.html",
        grades=grades
    )
# GET /grades/<id>/edit
@app.route("/grades/<int:id>/edit", methods=["GET"])
@jwt_required()
def edit_grade(id):

    if not is_admin():
        return {"message": "Admin access required"}, 403

    grade = Grade.query.get_or_404(id)

    students = Student.query.all()
    courses = Course.query.all()

    return render_template(
        "grades/edit.html",
        grade=grade,
        students=students,
        courses=courses
    )
# PUT /grades/<id>
@app.route("/grades/<int:id>", methods=["PUT"])
@jwt_required()
def update_grade(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403

    grade = Grade.query.get_or_404(id)

    student_id = request.form.get("student_id")
    course_id = request.form.get("course_id")
    score = request.form.get("score")
    date_value = request.form.get("date")

    if not student_id:
        return {"message": "Student is required"}, 400

    if not course_id:
        return {"message": "Course is required"}, 400

    if not score:
        return {"message": "Score is required"}, 400

    if not date_value:
        return {"message": "Date is required"}, 400

    try:
        student_id = int(student_id)
        course_id = int(course_id)
        score = float(score)
    except ValueError:
        return {"message": "Invalid student, course, or score value"}, 400

    if score < 0 or score > 100:
        return {"message": "Score must be between 0 and 100"}, 400

    student = Student.query.get(student_id)

    if not student:
        return {"message": "Student not found"}, 404

    course = Course.query.get(course_id)

    if not course:
        return {"message": "Course not found"}, 404

    try:
        grade_date = datetime.strptime(
            date_value,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return {"message": "Invalid date format. Use YYYY-MM-DD"}, 400

    grade.student_id = student_id
    grade.course_id = course_id
    grade.score = score
    grade.date = grade_date

    db.session.commit()

    return redirect("/grades")
@app.route("/grades/<int:id>", methods=["PATCH"])
@jwt_required()
def patch_grade(id):
    if not is_admin():
        return {"message": "Admin access required"}, 403

    grade = Grade.query.get_or_404(id)

    if "student_id" in request.form:
        try:
            student_id = int(request.form["student_id"])
        except ValueError:
            return {"message": "Invalid student ID"}, 400

        student = Student.query.get(student_id)

        if not student:
            return {"message": "Student not found"}, 404

        grade.student_id = student_id

    if "course_id" in request.form:
        try:
            course_id = int(request.form["course_id"])
        except ValueError:
            return {"message": "Invalid course ID"}, 400

        course = Course.query.get(course_id)

        if not course:
            return {"message": "Course not found"}, 404

        grade.course_id = course_id

    if "score" in request.form:
        try:
            score = float(request.form["score"])
        except ValueError:
            return {"message": "Invalid score"}, 400

        if score < 0 or score > 100:
            return {"message": "Score must be between 0 and 100"}, 400

        grade.score = score

    if "date" in request.form:
        try:
            grade.date = datetime.strptime(
                request.form["date"],
                "%Y-%m-%d"
            ).date()
        except ValueError:
            return {"message": "Invalid date format. Use YYYY-MM-DD"}, 400

    db.session.commit()

    return redirect("/grades")
# DELETE /grades/<id>
@app.route("/grades/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_grade(id):

    if not is_admin():
        return {"message": "Admin access required"}, 403

    grade = Grade.query.get_or_404(id)

    db.session.delete(grade)
    db.session.commit()

    return redirect("/grades")
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if not user:
        return {"message": "Invalid email or password"}, 401

    if not check_password_hash(user.password, password):
        return {"message": "Invalid email or password"}, 401

    access_token = create_access_token(
        identity=str(user.id)
    )

    if request.is_json:
        return {
            "message": "Login successful",
            "access_token": access_token
        }

    response = redirect("/students/view")

    set_access_cookies(response, access_token)

    return response
@app.route("/analytics", methods=["GET"])
@jwt_required()
def analytics():

    if not is_admin():
        return {"message": "Admin access required"}, 403

    # Get all courses and students for the dropdowns
    courses = Course.query.all()
    students = Student.query.all()

    # Get all grades
    grades = Grade.query.all()

    data = []

    for grade in grades:
        data.append({
            "student_id": grade.student_id,
            "course_id": grade.course_id,
            "student_name": grade.student.name,
            "course_name": grade.course.name,
            "score": grade.score
        })

    df = pd.DataFrame(data)

    if df.empty:
        return render_template(
            "analytics/dashboard.html",
            courses=courses,
            students=students,
            selected_course="",
            selected_student="",
            mean=0,
            median=0,
            std=0,
            total_grades=0,
            course_averages=[],
            rankings=[],
            grades=[]
        )

    # Read filters
    course_filter = request.args.get("course", "").strip()
    student_filter = request.args.get("student", "").strip()

    # Keep selected values for the dropdown
    selected_course = course_filter
    selected_student = student_filter

    # Apply course filter using course ID
    if course_filter:
        df = df[df["course_id"] == int(course_filter)]

    # Apply student filter using student ID
    if student_filter:
        df = df[df["student_id"] == int(student_filter)]

    if df.empty:
        return render_template(
            "analytics/dashboard.html",
            courses=courses,
            students=students,
            selected_course=selected_course,
            selected_student=selected_student,
            mean=0,
            median=0,
            std=0,
            total_grades=0,
            course_averages=[],
            rankings=[],
            grades=[]
        )

    # Average score by course
    average_by_course = (
        df.groupby("course_name")["score"]
        .mean()
        .reset_index()
    )

    course_averages = []

    for _, row in average_by_course.iterrows():
        course_averages.append({
            "course": row["course_name"],
            "average": row["score"]
        })

    # Student ranking within each course
    df["rank"] = (
        df.groupby("course_name")["score"]
        .rank(
            method="dense",
            ascending=False
        )
        .astype(int)
    )

    ranking = df[
        [
            "course_name",
            "student_id",
            "student_name",
            "score",
            "rank"
        ]
    ]

    rankings = []

    for _, row in ranking.iterrows():
        rankings.append({
            "rank": row["rank"],
            "student": row["student_name"],
            "course": row["course_name"],
            "average": row["score"]
        })

    # NumPy statistics
    scores = df["score"].to_numpy(dtype=float)

    mean_score = float(np.mean(scores))
    median_score = float(np.median(scores))

    std_score = (
        float(np.std(scores, ddof=1))
        if len(scores) > 1
        else 0.0
    )

    # Get actual Grade objects for the Grade Analysis table
    filtered_grades = []

    for grade in grades:

        if course_filter and str(grade.course_id) != course_filter:
            continue

        if student_filter and str(grade.student_id) != student_filter:
            continue

        filtered_grades.append(grade)

    return render_template(
        "analytics/dashboard.html",
        courses=courses,
        students=students,
        selected_course=selected_course,
        selected_student=selected_student,
        mean=mean_score,
        median=median_score,
        std=std_score,
        total_grades=len(filtered_grades),
        course_averages=course_averages,
        rankings=rankings,
        grades=filtered_grades
    )
@app.route("/grades/upload", methods=["GET"])
@jwt_required()
def upload_grades_page():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    return render_template("grades/upload.html")
@app.route("/grades/upload", methods=["POST"])
@jwt_required()
def upload_grades():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    if "file" not in request.files:
        return {"message": "CSV file is required"}, 400

    file = request.files["file"]

    if file.filename == "":
        return {"message": "No file selected"}, 400

    if not file.filename.lower().endswith(".csv"):
        return {"message": "Only CSV files are allowed"}, 400

    try:
        df = pd.read_csv(file)
    except Exception:
        return {"message": "Invalid CSV file"}, 400

    required_columns = [
        "student_id",
        "course_id",
        "score",
        "date"
    ]

    for column in required_columns:
        if column not in df.columns:
            return {
                "message": f"Missing required column: {column}"
            }, 400

    grades_to_add = []

    for index, row in df.iterrows():

        # Validate student ID
        try:
            student_id = int(row["student_id"])
        except (ValueError, TypeError):
            return {
                "message": f"Invalid student_id at row {index + 2}"
            }, 400

        student = Student.query.get(student_id)

        if not student:
            return {
                "message": f"Student not found: {student_id}"
            }, 404

        # Validate course ID
        try:
            course_id = int(row["course_id"])
        except (ValueError, TypeError):
            return {
                "message": f"Invalid course_id at row {index + 2}"
            }, 400

        course = Course.query.get(course_id)

        if not course:
            return {
                "message": f"Course not found: {course_id}"
            }, 404

        # Validate score
        try:
            score = float(row["score"])
        except (ValueError, TypeError):
            return {
                "message": f"Invalid score at row {index + 2}"
            }, 400

        if score < 0 or score > 100:
            return {
                "message": f"Score must be between 0 and 100 at row {index + 2}"
            }, 400

        # Validate date
        try:
            grade_date = datetime.strptime(
                str(row["date"]),
                "%Y-%m-%d"
            ).date()
        except ValueError:
            return {
                "message": f"Invalid date at row {index + 2}. Use YYYY-MM-DD"
            }, 400

        grades_to_add.append(
            Grade(
                student_id=student_id,
                course_id=course_id,
                score=score,
                date=grade_date
            )
        )

    # Add all validated grades
    db.session.add_all(grades_to_add)
    db.session.commit()

    return {
        "message": "Grades uploaded successfully",
        "records_added": len(grades_to_add)
    }, 201
@app.route("/analytics/export/csv", methods=["GET"])
@jwt_required()
def export_analytics_csv():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    grades = Grade.query.all()

    data = []

    for grade in grades:
        data.append({
            "student_id": grade.student_id,
            "course_id": grade.course_id,
            "course_name": grade.course.name,
            "score": grade.score,
            "date": grade.date
        })

    df = pd.DataFrame(data)

    if df.empty:
        return {"message": "No grade data available"}, 404

    csv_data = df.to_csv(index=False)

    from flask import Response

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=analytics.csv"
        }
    )
@app.route("/analytics/export/excel", methods=["GET"])
@jwt_required()
def export_analytics_excel():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    grades = Grade.query.all()

    data = []

    for grade in grades:
        data.append({
            "student_id": grade.student_id,
            "course_id": grade.course_id,
            "course_name": grade.course.name,
            "score": grade.score,
            "date": grade.date
        })

    df = pd.DataFrame(data)

    if df.empty:
        return {"message": "No grade data available"}, 404

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Analytics")

    output.seek(0)

    from flask import send_file

    return send_file(
        output,
        as_attachment=True,
        download_name="analytics.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@app.route("/analytics/dashboard", methods=["GET"])
@jwt_required()
def analytics_dashboard():
    if not is_admin():
        return {"message": "Admin access required"}, 403

    grades = Grade.query.all()

    data = []

    for grade in grades:
        data.append({
            "student_id": grade.student_id,
            "course_id": grade.course_id,
            "course_name": grade.course.name,
            "score": grade.score
        })

    df = pd.DataFrame(data)

    if df.empty:
        return {"message": "No grade data available"}, 404

    average_by_course = (
        df.groupby("course_name")["score"]
        .mean()
        .reset_index()
    )

    df["rank"] = (
        df.groupby("course_name")["score"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    ranking = df[
        ["course_name", "student_id", "score", "rank"]
    ]

     # Calculate statistics using NumPy
    scores = df["score"].to_numpy(dtype=float)

    statistics = {
    "mean": float(np.mean(scores)),
    "median": float(np.median(scores)),
    "standard_deviation": float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
}
    

    return render_template(
        "analytics/dashboard.html",
        average_by_course=average_by_course.to_dict(orient="records"),
        student_ranking=ranking.to_dict(orient="records"),
        statistics=statistics
    )
@app.route("/students/view", methods=["GET"])
@jwt_required()
def students_view():

    if not is_admin():
        return {"message": "Admin access required"}, 403

    search = request.args.get("search", "").strip()

    query = Student.query

    if search:
        query = query.filter(
            (Student.name.ilike(f"%{search}%")) |
            (Student.email.ilike(f"%{search}%"))
        )

    students = query.all()

    return render_template(
        "students/list.html",
        students=students,
        search=search
    )
@app.route("/students/<int:id>/delete", methods=["GET"])
@jwt_required()
def confirm_delete_student(id):

    if not is_admin():
        return {"message": "Admin access required"}, 403

    student = Student.query.get_or_404(id)

    return render_template(
        "students/delete.html",
        student=student
    )