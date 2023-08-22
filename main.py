from datetime import date, datetime
from functools import wraps
from sqlalchemy import func
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar

# todo get notifications, filter page, about page and contact us page working

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

year = date.today().strftime("%Y")


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    todos = relationship("ToDoLists", back_populates="owner", lazy='subquery')


# Café TABLE Configuration
class ToDoLists(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_name = db.Column(db.String(250), nullable=False)
    start_date = db.Column(db.DateTime(), default=func.now(), nullable=False)
    completed = db.Column(db.Boolean, nullable=False)
    date_created = db.Column(db.DateTime(), nullable=False)
    owner = relationship("User", back_populates="todos", lazy='subquery')
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))


def not_logged(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('home_page'))
        return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.id == user_id)).scalar()


@app.route('/', methods=['GET', 'POST'])
def home_page():
    number = None
    due = None
    the_todo = None
    details = None
    if request.method == 'POST':
        with app.app_context():
            name = request.form.get('list_name')
            start_dates = request.form.get('start_dates').split('T')

            if len(name) == 0 or len(start_dates) == 1:
                flash("Do not leave the fields empty, Please try again!")
                if current_user.is_authenticated:
                    is_available = True
                    details = db.session.execute(
                        db.select(ToDoLists).where(ToDoLists.owner_id == current_user.id)).scalars().all()
                    number = len(details)
                else:
                    is_available = False
            else:
                current_date = datetime.today().strftime('%Y-%m-%d %H:%M')
                dates = start_dates[0] + " " + start_dates[1]
                start = datetime.strptime(dates, '%Y-%m-%d %H:%M')
                item = ToDoLists(list_name=name,
                                 start_date=start,
                                 completed=bool(0),
                                 owner=current_user,
                                 date_created=datetime.strptime(current_date, '%Y-%m-%d %H:%M')
                                 )
                db.session.add(item)
                db.session.commit()

                return redirect(url_for('home_page'))

    else:
        if current_user.is_authenticated:
            is_available = True
            details = db.session.execute(
                db.select(ToDoLists).where(ToDoLists.owner_id == current_user.id)).scalars().all()

            for todo in details:
                remaining_days = str(todo.start_date - todo.date_created).split(',')[0].split('day')[0].split('days')[0]
                if int(remaining_days) <= 1:
                    if todo.completed != 1:
                        due = True
                        the_todo = todo
            number = len(details)
        else:
            is_available = False

    return render_template('index.html', the_todo=the_todo, due=due, number=number, details=details,
                           is_available=is_available,
                           logged_in=current_user.is_authenticated, year=year,
                           user=current_user)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        password = request.form.get('current')
        new_password = request.form.get('new')
        repeated = request.form.get('new_again')
        if check_password_hash(pwhash=current_user.password, password=password):
            if new_password == repeated:
                hashed_password = generate_password_hash(password=new_password, method="pbkdf2:sha256", salt_length=8)
                user = db.session.execute(db.select(User).where(User.password == current_user.password)).scalar()
                user.password = hashed_password
                db.session.commit()
                flash("Password successfully changed!", category='success')
            else:
                flash("New password doesn't match the repeated password, Please try again!")
        else:
            flash("Password doesn't match your current password, Please try again!")

        return redirect(url_for('home_page'))


@app.route('/register', methods=['GET', 'POST'])
@not_logged
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        repeated_passwords = request.form.get('repeat')
        if password == repeated_passwords:
            hashed_password = generate_password_hash(password=password, method="pbkdf2:sha256", salt_length=8)

            details = db.session.execute(db.select(User).where(User.email == email)).scalar()
            if details:
                return redirect(url_for('login', message=flash('This email already exists. Log In instead.')))
            else:
                new_user = User()
                new_user.name = name
                new_user.email = email
                new_user.password = hashed_password

                db.session.add(new_user)
                db.session.commit()

                already_logged = db.session.execute(db.select(User).where(User.email == email)).scalar()
                if already_logged:
                    login_user(already_logged)
                    flash('Registration successful!', category='success')
                    return redirect(url_for("home_page"))

        else:
            flash("That passwords don't match, Please try again!")

    return render_template("register.html", year=year, logged_in=current_user.is_authenticated, user=current_user)


@app.route('/filter', methods=['GET', 'POST'])
@login_required
def filters():
    details = None
    number = None
    empty = None
    is_available = True
    if request.method == 'POST':
        the_filter = request.form.get('select1')
        if the_filter == 'all':
            details = db.session.execute(
                db.select(ToDoLists).where(ToDoLists.owner_id == current_user.id)).scalars().all()
            number = len(details)
            if number == 0:
                empty = True
        else:

            details = db.session.execute(db.select(ToDoLists).where(ToDoLists.completed == the_filter,
                                                                    ToDoLists.owner_id ==
                                                                    current_user.id)).scalars().all()
            number = len(details)
            if number == 0:
                empty = True
    return render_template('index.html', empty=empty, number=number, details=details, is_available=is_available,
                           logged_in=current_user.is_authenticated, year=year,
                           user=current_user)


@app.route('/login', methods=['GET', 'POST'])
@not_logged
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with app.app_context():
            details = db.session.execute(db.select(User).where(User.email == email)).scalar()
            if details:
                if check_password_hash(pwhash=details.password, password=password):
                    login_user(details)
                    flash('Login successful!', category='success')
                    return redirect(url_for('home_page'))
                else:
                    flash('Password Incorrect, Please try again!')
            else:
                flash("That email doesn't exist, Please try again!")

    return render_template("login.html", year=year, logged_in=current_user.is_authenticated, user=current_user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home_page'))


@app.route('/update/<int:post_id>')
@login_required
def update(post_id):
    todo_to_delete = ToDoLists.query.get(post_id)
    if todo_to_delete.completed == 1:
        pass
    else:
        todo_to_delete.completed = 1
        db.session.commit()
    return redirect(url_for('home_page'))


@app.route("/delete/<int:post_id>")
@login_required
def delete(post_id):
    todo_to_delete = ToDoLists.query.get(post_id)
    db.session.delete(todo_to_delete)
    db.session.commit()
    return redirect(url_for('home_page'))


if __name__ == '__main__':
    app.run(debug=True)
