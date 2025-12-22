from extensions import db
from flask_login import UserMixin

# 1. 생산 계획 모델
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

# 2. 관리자 모델
class Manager(db.Model):
    __tablename__ = 'managers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

# 3. 업체 모델
class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

# 4. 사용자 모델
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    
# 5. DIP 그룹 모델
class DipGroup(db.Model):
    __tablename__ = 'dip_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100), nullable=False)
    lot = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False, default=0) 
    month = db.Column(db.String(20), nullable=False, default='')
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
            'year': self.year,
            'month': self.month,
            'status': self.status,
            'histories': [h.to_dict() for h in self.histories]
        }

# 6. DIP 이력 모델
class DipHistory(db.Model):
    __tablename__ = 'dip_histories'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('dip_groups.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
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

# 7. [수정됨] AOI 기록 모델 (레퍼런스 컬럼 추가)
class AoiRecord(db.Model):
    __tablename__ = 'aoi_records'

    id = db.Column(db.Integer, primary_key=True)
    
    # 고유 주문 키
    model = db.Column(db.String(100), nullable=False)
    order_year = db.Column(db.Integer, nullable=False)
    order_month = db.Column(db.String(20), nullable=False)
    lot = db.Column(db.String(50), nullable=False) 
    
    # 기본 정보
    date = db.Column(db.String(20))
    
    # 검사 기준 정보
    inspection_point = db.Column(db.Integer, default=0)
    inspection_qty = db.Column(db.Integer, default=0)
    
    # --- 불량 유형 (수량 & 레퍼런스 짝꿍) ---
    
    # 1. 실장오류
    missing = db.Column(db.Integer, default=0)
    missing_ref = db.Column(db.String(100), default='')
    
    wrong = db.Column(db.Integer, default=0)
    wrong_ref = db.Column(db.String(100), default='')
    
    reverse = db.Column(db.Integer, default=0)
    reverse_ref = db.Column(db.String(100), default='')
    
    skewed = db.Column(db.Integer, default=0)
    skewed_ref = db.Column(db.String(100), default='')
    
    flipped = db.Column(db.Integer, default=0)
    flipped_ref = db.Column(db.String(100), default='')
    
    # 2. 부품결함
    damaged = db.Column(db.Integer, default=0)
    damaged_ref = db.Column(db.String(100), default='')
    
    manhattan = db.Column(db.Integer, default=0)
    manhattan_ref = db.Column(db.String(100), default='')
    
    detached = db.Column(db.Integer, default=0)
    detached_ref = db.Column(db.String(100), default='')
    
    # 3. 납땜불량
    cold = db.Column(db.Integer, default=0)
    cold_ref = db.Column(db.String(100), default='')
    
    unsoldered = db.Column(db.Integer, default=0)
    unsoldered_ref = db.Column(db.String(100), default='')
    
    short = db.Column(db.Integer, default=0)
    short_ref = db.Column(db.String(100), default='')
    
    # 4. 기타
    lifted = db.Column(db.Integer, default=0) # 들뜸(코드엔 있으나 화면엔 안쓰일 수도 있음)
    lifted_ref = db.Column(db.String(100), default='')
    
    material = db.Column(db.Integer, default=0)
    material_ref = db.Column(db.String(100), default='')
    
    dip = db.Column(db.Integer, default=0)
    dip_ref = db.Column(db.String(100), default='')
    
    # 합계 데이터
    total_defect = db.Column(db.Integer, default=0)
    good_qty = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'model': self.model,
            'year': self.order_year,
            'month': self.order_month,
            'lot': self.lot,
            'date': self.date,
            'inspection_point': self.inspection_point,
            'inspection_qty': self.inspection_qty,
            
            # 불량 상세 (수량)
            'reverse': self.reverse, 'missing': self.missing, 'wrong': self.wrong,
            'skewed': self.skewed, 'flipped': self.flipped, 'unsoldered': self.unsoldered,
            'damaged': self.damaged, 'manhattan': self.manhattan, 'short': self.short,
            'cold': self.cold, 'lifted': self.lifted, 'detached': self.detached,
            'material': self.material, 'dip': self.dip,
            
            # 불량 상세 (레퍼런스) - [신규]
            'reverse_ref': self.reverse_ref, 'missing_ref': self.missing_ref, 'wrong_ref': self.wrong_ref,
            'skewed_ref': self.skewed_ref, 'flipped_ref': self.flipped_ref, 'unsoldered_ref': self.unsoldered_ref,
            'damaged_ref': self.damaged_ref, 'manhattan_ref': self.manhattan_ref, 'short_ref': self.short_ref,
            'cold_ref': self.cold_ref, 'lifted_ref': self.lifted_ref, 'detached_ref': self.detached_ref,
            'material_ref': self.material_ref, 'dip_ref': self.dip_ref,
            
            # 합계
            'total_defect': self.total_defect,
            'good_qty': self.good_qty
        }
        
        # 8. [신규] 제품 모델 (업체 하위의 '모델 폴더' 역할)
class ProductModel(db.Model):
    __tablename__ = 'product_models'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # 모델명
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False) # 어느 업체 소속인지 (FK)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # 관계 설정 (선택사항: Company 삭제 시 모델도 같이 삭제되게 하려면 cascade 설정 필요)
    # company = db.relationship('Company', backref=db.backref('models', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'company_id': self.company_id,
            'created_at': self.created_at
        }

# 9. [신규] 모델 데이터 (BOM, 좌표 등 실데이터 저장)
class ModelData(db.Model):
    __tablename__ = 'model_data'
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('product_models.id'), nullable=False) # 어느 모델 소속인지
    data_type = db.Column(db.String(20), nullable=False) # 예: 'BOM', 'COORDINATE'
    content = db.Column(db.Text) # 실제 데이터 (JSON 문자열이나 텍스트)
    file_name = db.Column(db.String(255)) # 업로드된 원본 파일명 (예: A모델_BOM.xlsx)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'model_id': self.model_id,
            'type': self.data_type,
            'fileName': self.file_name,
            'content': self.content, # 필요에 따라 빼고 리스트만 줄 수도 있음
            'updated_at': self.updated_at
        }