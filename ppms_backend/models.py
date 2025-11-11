from flask_sqlalchemy import SQLAlchemy

# 'db' 객체를 생성합니다. (아직 app에 연결 안 함)
db = SQLAlchemy()

# 'production_schedules' 테이블의 Python 클래스
# 'production_schedules' 테이블의 Python 클래스
# 'production_schedules' 테이블의 Python 클래스
class ProductionSchedule(db.Model):
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
        # (읽기 어댑터 로직)
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
            
            # ▼▼▼ [수정] 누락되었던 3개 필드 추가 ▼▼▼
            "prod_year": self.prod_year,
            "prod_month": self.prod_month,
            "prod_week": self.prod_week
        }

class Manager(db.Model):
    __tablename__ = 'managers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)