from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort
import time
import os
import random
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_migrate import Migrate

# t_index - це глобальна змінна, яка використовується для контролю ініціалізації завдань(якщо завдання вже додані то ставити t_index=0, якщо треба додати то t_index=1)
t_index = 0

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

app.config['SQLALCHEMY_DATABASE_URI'] = (
    'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'users.db')
)

app.config['UPLOAD_FOLDER'] = os.path.join(
    BASE_DIR, 'static', 'uploads'
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


migrate = Migrate(app, db)

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)




class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    photos = db.relationship('Photo', backref='user', lazy=True)
    
    level = db.Column(db.Integer, default=0)
     # ось нове
    followed = db.relationship(
    'User', secondary=followers,
    primaryjoin=(followers.c.follower_id == id),
    secondaryjoin=(followers.c.followed_id == id),
    backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    likes_given = db.relationship('Like', backref='user', lazy='dynamic')

    @property
    def total_likes_received(self):
        return sum(len(photo.likes.all()) for photo in self.photos)

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def following_count(self):
        return self.followed.count()

    def followers_count(self):
        return self.followers.count()


#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel
#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel
#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel
#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel
#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel




# Модельки залишаються такими ж:
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    reward = db.Column(db.Integer, nullable=False)
    check_function = db.Column(db.String(100), nullable=False)

class UserTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

# Перевірочні функції:
def check_upload_photo(user):
    return any(file.startswith(f"collage_{user.id}_") for file in os.listdir(app.config['UPLOAD_FOLDER']))


def check_follow_three_users(user):
    return len(user.followed.all()) >= 3

def check_get_first_follower(user):
    return len(user.followers.all()) >= 1

def check_get_five_followers(user):
    return len(user.followers.all()) >= 5


def check_upload_five_photos(user):
    user_photos = [file for file in os.listdir(app.config['UPLOAD_FOLDER']) if file.startswith(f"collage_{user.id}_")]
    return len(user_photos) >= 5



# Мапа функцій перевірки:
check_functions = {
    'check_upload_photo': check_upload_photo,
    'check_follow_three_users': check_follow_three_users,
    'check_get_first_follower': check_get_first_follower,
    'check_upload_five_photos': check_upload_five_photos,
    'check_get_five_followers': check_get_five_followers
}

@app.route('/complete_task/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    # Перевіряємо чи вже виконав
    existing = UserTask.query.filter_by(user_id=current_user.id, task_id=task_id).first()
    if existing:
        flash('Ти вже виконав це завдання!', 'warning')
        return redirect(url_for('level_page'))  # <-- тут

    # Дістаємо завдання
    task = Task.query.get(task_id)
    if not task:
        flash('Завдання не знайдено.', 'danger')
        return redirect(url_for('level_page'))  # <-- і тут

    # Шукаємо функцію перевірки
    check_func = check_functions.get(task.check_function)
    if check_func and check_func(current_user):
        # Завдання виконано 🎯
        current_user.level += task.reward
        db.session.add(current_user)
        db.session.add(UserTask(user_id=current_user.id, task_id=task.id))
        db.session.commit()
        flash(f'Завдання "{task.title}" виконано! Отримано {task.reward} рівнів.', 'success')
    else:
        flash('Ви ще не виконали це завдання.', 'danger')

    return redirect(url_for('level_page'))  # <-- і тут також

# Роут для перегляду завдань:

# Додавання завдань в базу (робиться один раз, наприклад через Flask CLI):
def seed_tasks():
    tasks = [
        Task(title="Завантаж перше фото", description="Завантаж своє перше фото в профіль", reward=1, check_function='check_upload_photo'),
        Task(title="Підпишись на трьох", description="Підпишись на 3 користувачів", reward=1, check_function='check_follow_three_users'),
        Task(title="Отримай першу підписку", description="Отримай 1 підписника", reward=1, check_function='check_get_first_follower'),
        Task(title="Завантаж 5 фото", description="Завантаж 5 своїх фото", reward=1, check_function='check_upload_five_photos'),
        Task(title="Отримай першу п'ятірку", description="Отримай 5 підписників", reward=1, check_function='check_get_five_followers')
    ]
    for task in tasks:
        db.session.add(task)
    db.session.commit()


@app.route("/level")
@login_required
def level_page():
    global t_index
    if t_index == 1:
        seed_tasks()
        t_index =0
    user_level = current_user.level  # Беремо рівень користувача
    tasks = Task.query.all()  # Всі завдання
    completed_tasks = UserTask.query.filter_by(user_id=current_user.id).all()
    completed_task_ids = [task.task_id for task in completed_tasks]
    return render_template('level.html', level=user_level, tasks=tasks, completed_task_ids=completed_task_ids)


#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel
#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel
#levellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvellevellevelvel



@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    user_to_follow = User.query.get_or_404(user_id)
    if user_to_follow == current_user:
        flash("Ви не можете підписатися на себе.")
        return redirect(url_for('user_profile', username=current_user.username))

    if current_user.is_following(user_to_follow):
        current_user.unfollow(user_to_follow)
    else:
        current_user.follow(user_to_follow)

    db.session.commit()
    return redirect(url_for('user_profile', username=user_to_follow.username))  



class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), nullable=False)
    caption = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    likes = db.relationship('Like', backref='photo', lazy='dynamic')

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'photo_id', name='_user_photo_uc'),)


@app.route("/like_count/<int:photo_id>")
@login_required
def like_count(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    liked = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first() is not None
    like_count = Like.query.filter_by(photo_id=photo.id).count()
    return jsonify({
        "like_count": like_count,
        "liked": liked
    })

@app.route('/like/<int:photo_id>', methods=['POST'])
@login_required
def like_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    user = current_user

    like = Like.query.filter_by(user_id=user.id, photo_id=photo.id).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        new_like = Like(user_id=user.id, photo_id=photo.id)
        db.session.add(new_like)
        liked = True

    db.session.commit()

    like_count = Like.query.filter_by(photo_id=photo.id).count()
    return jsonify({"liked": liked, "like_count": like_count})

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/reglog')
def reglog():
    if not current_user.is_authenticated:
        return render_template('reglog.html')
    return redirect(url_for('profile'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Перевірка чи username вже існує
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Такий нікнейм вже зайнятий. Виберіть інший.', 'danger')
            return redirect(url_for('register'))

        # Якщо ні - хешуємо пароль і реєструємо
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash('Реєстрація успішна! Увійдіть у свій акаунт.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            
            return redirect(url_for('profile'))
        else:
            flash('Неправильний логін або пароль!', 'danger')

    return render_template('login.html')


@app.route("/profile")
@login_required
def profile():
    return redirect(url_for('user_profile', username=current_user.username))

@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if "profile_picture" not in request.files:
        return redirect(url_for("profile"))
    file = request.files["profile_picture"]
    if file.filename == "":
        return redirect(url_for("profile"))
    if file:
        filename = f'user_{current_user.id}.jpg'  # Унікальне ім'я для кожного користувача
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
    return redirect(url_for("profile"))


@app.route('/users')
def users():
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/user/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        abort(404)  # Якщо користувача немає, повертаємо 404

    # Визначаємо, чи це профіль поточного користувача
    editable = (current_user.is_authenticated and current_user.username == username)

    # Шлях до фото профілю
    profile_image_filename = f'user_{user.id}.jpg'
    profile_image_path = os.path.join(app.config['UPLOAD_FOLDER'], profile_image_filename)
    user_level =  user.level
    if os.path.exists(profile_image_path):
        profile_image_url = url_for('uploaded_file', filename=profile_image_filename)
    else:
        profile_image_url = url_for('static', filename="default_profile.png")

    # Отримуємо всі фото, які завантажив користувач
    user_photos = [
    {
        'id': photo.id,
        'src': url_for('static', filename='uploads/' + photo.filename),
        'caption': photo.caption,
        'user': {'username': photo.user.username}
    }
    for photo in user.photos
]
    

    following_count = user.followed.count() if hasattr(user.followed, 'count') else len(user.followed)
    followers_count = user.followers.count() if hasattr(user.followers, 'count') else len(user.followers)
    is_following = False
    if current_user.is_authenticated and current_user != user:
        is_following = current_user.is_following(user)

    return render_template("profile.html",
    user=user,
    username=user.username,
    profile_image=profile_image_url,
    editable=editable,
    user_photos=user_photos,
    level=user_level,
    followers_count=followers_count,
    following_count=following_count,
    is_following=is_following)   # <-- додав

@app.route("/upload_collage", methods=["POST"])
@login_required
def upload_collage():
    if "collage_photo" not in request.files:
        return jsonify({"status": "error", "message": "Файл не знайдено"}), 400

    file = request.files["collage_photo"]
    caption = request.form.get("caption", "")  # <-- Ось тут дістаємо підпис

    if file.filename == "":
        return jsonify({"status": "error", "message": "Файл не обрано"}), 400

    allowed_extensions = {"png", "jpg", "jpeg", "gif"}
    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({"status": "error", "message": "Недопустимий формат файлу"}), 400

    filename = f"collage_{current_user.id}_{int(time.time())}.jpg"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # !!! Додай колонку 'caption' у свою модель Photo, якщо ще нема
    new_photo = Photo(filename=filename, user_id=current_user.id, caption=caption)
    db.session.add(new_photo)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "Фото додано"})


@app.route("/get_collage_photos")
def get_collage_photos():
    photos = Photo.query.order_by(Photo.id.desc()).all()

    images = [{
        "id": photo.id,
        "src": url_for('uploaded_file', filename=photo.filename),
        "caption": photo.caption,
        "user": {
            "id": photo.user.id,
            "username": photo.user.username
        }
    } for photo in photos]
    random.shuffle(images)
    return jsonify(images)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/logout')
@login_required
def logout():
    logout_user()
        
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
