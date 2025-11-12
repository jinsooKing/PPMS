from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

# 모든 공용 '도구'들을 여기서 한 번만 초기화합니다.
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()