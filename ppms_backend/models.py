from extensions import db  # ▼ [수정] flask_sqlalchemy 대신 extensions에서 db를 가져옵니다.
from flask_login import UserMixin

# db = SQLAlchemy()  <-- (삭제) 이 줄은 extensions.py로 이동했습니다.

# ... (ProductionSchedule, Manager, Company 클래스는 동일) ...
class ProductionSchedule(db.Model):
    # (내용 변경 없음)
    __tablename__ = 'production_schedules'
    id = db.Column(db.Integer, primary_key=True)
    prod_year = db.Column(db.Integer, nullable=False)
    prod_month = db.Column(db.Integer, nullable=False)
    prod_week = db.Column(db.Integer, nullable=False)
    line = db.Column(db.String(10), nullable=False)
    company = db.Column(db.String(100))
    model = db.Column(db.String(100))
    order_year = db.Column(db.Integer)
    order_month = db.Column(db.String(20))
    tb = db.Column(db.String(50))
    start_date = db.Column(db.String(50))
    end_date = db.Column(db.String(50))
    manager = db.Column(db.String(100))
    actual_prod = db.Column(db.Integer, default=0)
    actual_start_date = db.Column(db.String(50))
    actual_end_date = db.Column(db.String(50))
    notes = db.Column(db.Text)
    batch_quantity = db.Column(db.Integer, default=0)
    total_quantity = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        batch = self.batch_quantity or 0
        total = self.total_quantity or 0
        if total > 0 and batch != total:
            lot_string = f"{batch}/{total}"
        else:
            lot_string = f"{batch}"
        
        return {
            "id": self.id,
            "line": self.line,
            "company": self.company,
            "model": self.model,
            "orderYear": self.order_year, 
            "orderMonth": self.order_month,
            "tb": self.tb,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "manager": self.manager,
            "actualProd": self.actual_prod,
            "actualStartDate": self.actual_start_date,
            "actualEndDate": self.actual_end_date,
            "notes": self.notes,
            "lot": lot_string,
            "prod_year": self.prod_year,
            "prod_month": self.prod_month,
            "prod_week": self.prod_week
        }

class Manager(db.Model):
    # (내용 변경 없음)
    __tablename__ = 'managers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Company(db.Model):
    # (내용 변경 없음)
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class User(UserMixin, db.Model):
    # (내용 변경 없음)
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    
class DipGroup(db.Model):
    __tablename__ = 'dip_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100), nullable=False)
    lot = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False, default=0) 
    month = db.Column(db.String(20), nullable=False, default='')
    # 같은 모델+LOT 중복 방지
    status = db.Column(db.String(20), nullable=False, default='ongoing')
    
    __table_args__ = (
        db.UniqueConstraint('model', 'year', 'month', 'lot', name='unique_dip_group_key'),
    )

    histories = db.relationship('DipHistory', backref='group', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'model': self.model,
            'lot': self.lot,
            'year': self.year,   # [신규]
            'month': self.month, # [신규]
            'status': self.status,
            'histories': [h.to_dict() for h in self.histories]
        }

class DipHistory(db.Model):
    __tablename__ = 'dip_histories'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('dip_groups.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False) # YYYY-MM-DD
    type = db.Column(db.String(10), nullable=False) # 'ship' or 'receive'
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'date': self.date,
            'type': self.type,
            'quantity': self.quantity
        }