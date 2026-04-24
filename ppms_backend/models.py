from extensions import db
from flask_login import UserMixin
from datetime import datetime

# 1. 생산 계획 모델
# [models.py 수정본 - ProductionSchedule 클래스 부분]

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
    
    # --- [공정별 독립 실적 컬럼 추가] ---
    
    # (1) 생산 부서 영역
    manager = db.Column(db.String(100))
    actual_prod = db.Column(db.Integer, default=0)
    actual_start_date = db.Column(db.String(50))
    actual_end_date = db.Column(db.String(50))
    
    # (2) 조립(DIP) 부서 영역 (신규 추가)
    assy_actual = db.Column(db.Integer, default=0) # 조립 완료 수량
    assy_start_date = db.Column(db.String(50))
    assy_end_date = db.Column(db.String(50))
    assy_worker = db.Column(db.String(100))        # 조립 담당자
    
    # ----------------------------------
    
    notes = db.Column(db.Text)
    batch_quantity = db.Column(db.Integer, default=0)
    total_quantity = db.Column(db.Integer, default=0)
    aoi_done = db.Column(db.Boolean, default=False)  # AOI 검사 완료 여부
    
    def to_dict(self):
        batch = self.batch_quantity or 0
        total = self.total_quantity or 0
        lot_string = f"{batch}/{total}" if total > 0 and batch != total else f"{batch}"
        
        return {
            "id": self.id, "line": self.line, "company": self.company, "model": self.model,
            "orderYear": self.order_year, "orderMonth": self.order_month, "tb": self.tb,
            "startDate": self.start_date, "endDate": self.end_date, "manager": self.manager,
            "actualProd": self.actual_prod, "actualStartDate": self.actual_start_date,
            "actualEndDate": self.actual_end_date, 
            # 조립 및 AOI 데이터 포함
            "assyActual": self.assy_actual,
            "assyWorker": self.assy_worker,
            "notes": self.notes, "lot": lot_string,
            "prod_year": self.prod_year, "prod_month": self.prod_month, "prod_week": self.prod_week
        }

# 2. 관리자 모델
class Manager(db.Model):
    __tablename__ = 'managers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    
    # [신규 추가 인적 정보]
    position = db.Column(db.String(50))    # 직급
    department = db.Column(db.String(50))  # 부서
    roles = db.Column(db.String(255))      # 역할 (쉼표로 구분하여 저장)
    contact = db.Column(db.String(50))     # 연락처
    email = db.Column(db.String(100))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'position': self.position or '',
            'department': self.department or '',
            'roles': self.roles or '',
            'contact': self.contact or '',
            'email': self.email or ''
        }

# 3. 업체 모델
class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    # [추가] 업체 목록 조회 시 필요
    def to_dict(self):
        return {'id': self.id, 'name': self.name}

# 4. 사용자 모델
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    
    # [추가] 사용자 관리 화면 등이 있을 경우 필요 (비밀번호 해시는 절대 포함 금지)
    def to_dict(self):
        return {'id': self.id, 'username': self.username, 'role': self.role}

# 5. DIP 그룹 모델
class DipGroup(db.Model):
    __tablename__ = 'dip_groups'
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100), nullable=False)
    lot = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False, default=0) 
    month = db.Column(db.String(20), nullable=False, default='')
    status = db.Column(db.String(20), nullable=False, default='ongoing')
    
    __table_args__ = (db.UniqueConstraint('model', 'year', 'month', 'lot', name='unique_dip_group_key'),)
    histories = db.relationship('DipHistory', backref='group', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'model': self.model, 'lot': self.lot, 'year': self.year,
            'month': self.month, 'status': self.status,
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
        return {'id': self.id, 'group_id': self.group_id, 'date': self.date, 'type': self.type, 'quantity': self.quantity}

# 7. AOI 기록 모델
class AoiRecord(db.Model):
    __tablename__ = 'aoi_records'
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100), nullable=False)
    order_year = db.Column(db.Integer, nullable=False)
    order_month = db.Column(db.String(20), nullable=False)
    lot = db.Column(db.String(50), nullable=False) 
    date = db.Column(db.String(20))
    inspection_point = db.Column(db.Integer, default=0)
    inspection_qty = db.Column(db.Integer, default=0)
    
    # 불량 유형 및 레퍼런스 (생략 없이 유지)
    missing = db.Column(db.Integer, default=0); missing_ref = db.Column(db.String(100), default='')
    wrong = db.Column(db.Integer, default=0); wrong_ref = db.Column(db.String(100), default='')
    reverse = db.Column(db.Integer, default=0); reverse_ref = db.Column(db.String(100), default='')
    skewed = db.Column(db.Integer, default=0); skewed_ref = db.Column(db.String(100), default='')
    flipped = db.Column(db.Integer, default=0); flipped_ref = db.Column(db.String(100), default='')
    damaged = db.Column(db.Integer, default=0); damaged_ref = db.Column(db.String(100), default='')
    manhattan = db.Column(db.Integer, default=0); manhattan_ref = db.Column(db.String(100), default='')
    detached = db.Column(db.Integer, default=0); detached_ref = db.Column(db.String(100), default='')
    cold = db.Column(db.Integer, default=0); cold_ref = db.Column(db.String(100), default='')
    unsoldered = db.Column(db.Integer, default=0); unsoldered_ref = db.Column(db.String(100), default='')
    short = db.Column(db.Integer, default=0); short_ref = db.Column(db.String(100), default='')
    lifted = db.Column(db.Integer, default=0); lifted_ref = db.Column(db.String(100), default='')
    material = db.Column(db.Integer, default=0); material_ref = db.Column(db.String(100), default='')
    dip = db.Column(db.Integer, default=0); dip_ref = db.Column(db.String(100), default='')
    
    total_defect = db.Column(db.Integer, default=0)
    good_qty = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id, 'model': self.model, 'year': self.order_year, 'month': self.order_month,
            'lot': self.lot, 'date': self.date, 'inspection_point': self.inspection_point, 'inspection_qty': self.inspection_qty,
            'reverse': self.reverse, 'missing': self.missing, 'wrong': self.wrong, 'skewed': self.skewed,
            'flipped': self.flipped, 'unsoldered': self.unsoldered, 'damaged': self.damaged, 'manhattan': self.manhattan,
            'short': self.short, 'cold': self.cold, 'lifted': self.lifted, 'detached': self.detached,
            'material': self.material, 'dip': self.dip,
            'reverse_ref': self.reverse_ref, 'missing_ref': self.missing_ref, 'wrong_ref': self.wrong_ref,
            'skewed_ref': self.skewed_ref, 'flipped_ref': self.flipped_ref, 'unsoldered_ref': self.unsoldered_ref,
            'damaged_ref': self.damaged_ref, 'manhattan_ref': self.manhattan_ref, 'short_ref': self.short_ref,
            'cold_ref': self.cold_ref, 'lifted_ref': self.lifted_ref, 'detached_ref': self.detached_ref,
            'material_ref': self.material_ref, 'dip_ref': self.dip_ref,
            'total_defect': self.total_defect, 'good_qty': self.good_qty
        }
# 8. 폴더 모델
class ModelFolder(db.Model):
    __tablename__ = 'model_folders'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(20), nullable=False, default='production')
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True) 
    parent_folder_id = db.Column(db.Integer, db.ForeignKey('model_folders.id'), nullable=True)
    
    # 하위 폴더 연쇄 삭제 설정 (기존)
    sub_folders = db.relationship('ModelFolder', backref=db.backref('parent', remote_side=[id]), cascade="all, delete-orphan")

    # [핵심 수정] 폴더 삭제 시 내부에 있는 모델/파일도 함께 삭제되도록 설정
    items = db.relationship('ProductModel', backref='folder', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'section': self.section,
            'company_id': self.company_id, 'parent_folder_id': self.parent_folder_id
        }

# 9. 제품 모델 (파일 포함)
class ProductModel(db.Model):
    __tablename__ = 'product_models'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False, default='model')
    section = db.Column(db.String(20), nullable=False, default='production')
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('model_folders.id'), nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'type': self.type, 
            'section': self.section, 'company_id': self.company_id, 'folder_id': self.folder_id
        }

# 10. 모델 데이터 모델
class ModelData(db.Model):
    __tablename__ = 'model_data'
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('product_models.id'), nullable=False)
    data_type = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text)
    file_name = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id, 'model_id': self.model_id, 'type': self.data_type,
            'fileName': self.file_name, 'content': self.content, 'updated_at': self.updated_at

        }
        
# models.py 기존 코드 하단에 추가

# ==========================================================
# [섹션] 점검(Inspection) 관련 모델
# ==========================================================
class VisionInspection(db.Model):
    __tablename__ = 'vision_inspection'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)        # 점검일
    machine_id = db.Column(db.Integer, nullable=False)  # 1호기, 2호기 구분
    status = db.Column(db.String(10), nullable=False)   # 'ok', 'ng'
    
    # 수정일자 (누가 언제 체크했는지 추적용)
    checked_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 같은 날짜, 같은 호기에는 하나의 기록만 존재하도록 제약
    __table_args__ = (db.UniqueConstraint('date', 'machine_id', name='uix_vision_date_machine'),)
    
    
# models.py 최하단에 추가

class EsdInspection(db.Model):
    __tablename__ = 'esd_inspection'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    # 기존 Manager 테이블의 id를 외래키(ForeignKey)로 연결
    manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    
    shoes_status = db.Column(db.String(10), default='') # 제전화 상태: 'O', 'X', 'C'
    wrist_status = db.Column(db.String(10), default='') # 손목띠 상태: 'O', 'X', 'C'
    
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    # Manager 모델과의 관계 설정 (선택 사항이지만 데이터 조회 시 유용)
    manager = db.relationship('Manager', backref=db.backref('esd_records', lazy=True))

    # 한 담당자는 하루에 하나의 점검 기록만 가지도록 제약 조건 설정
    __table_args__ = (db.UniqueConstraint('date', 'manager_id', name='uix_esd_date_manager'),)


# ==========================================================
# [섹션] SMD / 생산 점검 관련 모델
# ==========================================================

# 1. SMD 설비 일일점검 (SMD설비일일, Wave Solder, Metal Mask 공통 사용)
class SmdEquipmentCheck(db.Model):
    __tablename__ = 'smd_equipment_checks'

    id          = db.Column(db.Integer, primary_key=True)
    sheet_type  = db.Column(db.String(30), nullable=False)  # 'smd_daily' | 'wave_solder' | 'metal_mask'
    equipment   = db.Column(db.String(50), nullable=False)  # 설비명 (Loader, Screen Printer 등)
    item_no     = db.Column(db.Integer, nullable=False)      # 점검항목 번호
    date        = db.Column(db.Date, nullable=False)
    status      = db.Column(db.String(10), default='')       # 'O','V','△','X','☆','□' 등
    checker     = db.Column(db.String(50), default='')       # 점검자 (Metal Mask용)
    note        = db.Column(db.String(200), default='')      # 비고
    updated_at  = db.Column(db.DateTime, default=db.func.current_timestamp(),
                             onupdate=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('sheet_type', 'equipment', 'item_no', 'date',
                                           name='uix_smd_equip_check'),)

    def to_dict(self):
        return {
            'id': self.id, 'sheet_type': self.sheet_type,
            'equipment': self.equipment, 'item_no': self.item_no,
            'date': self.date.strftime('%Y-%m-%d'),
            'status': self.status, 'checker': self.checker, 'note': self.note
        }


# 2. 환경 점검 (냉장고 온도 / 실내 온습도 / 제습함 온습도)
class EnvironmentCheck(db.Model):
    __tablename__ = 'environment_checks'

    id          = db.Column(db.Integer, primary_key=True)
    check_type  = db.Column(db.String(20), nullable=False)   # 'fridge' | 'room' | 'dehumid'
    date        = db.Column(db.Date, nullable=False)
    time_slot   = db.Column(db.String(10), default='10:00')  # '10:00' | '18:00' (실내온습도 2회)
    temperature = db.Column(db.Float, nullable=True)          # 온도 (℃)
    humidity    = db.Column(db.Float, nullable=True)          # 습도 (%RH, 냉장고는 null)
    status      = db.Column(db.String(10), default='')        # 'O' | 'X' (냉장고 pass/fail)
    note        = db.Column(db.String(200), default='')
    updated_at  = db.Column(db.DateTime, default=db.func.current_timestamp(),
                             onupdate=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('check_type', 'date', 'time_slot',
                                           name='uix_env_check'),)

    def to_dict(self):
        return {
            'id': self.id, 'check_type': self.check_type,
            'date': self.date.strftime('%Y-%m-%d'), 'time_slot': self.time_slot,
            'temperature': self.temperature, 'humidity': self.humidity,
            'status': self.status, 'note': self.note
        }


# 3. AC 누설전류 점검 (월 1회, 연간 관리)
class AcLeakageCheck(db.Model):
    __tablename__ = 'ac_leakage_checks'

    id          = db.Column(db.Integer, primary_key=True)
    year        = db.Column(db.Integer, nullable=False)
    month       = db.Column(db.Integer, nullable=False)       # 1~12
    line        = db.Column(db.String(10), nullable=False)    # 'A', 'B', 'C'
    equipment   = db.Column(db.String(50), nullable=False)    # 'LOADER', 'PRINTER' 등
    voltage     = db.Column(db.Float, nullable=True)           # 측정값 (V)
    status      = db.Column(db.String(10), default='')         # 'OK' | 'NG' | ''
    updated_at  = db.Column(db.DateTime, default=db.func.current_timestamp(),
                             onupdate=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('year', 'month', 'line', 'equipment',
                                           name='uix_ac_leakage'),)

    def to_dict(self):
        return {
            'id': self.id, 'year': self.year, 'month': self.month,
            'line': self.line, 'equipment': self.equipment,
            'voltage': self.voltage, 'status': self.status
        }

# 점검 시트 프리셋 (관리자 설정값)
class SheetPreset(db.Model):
    __tablename__ = 'sheet_presets'

    id          = db.Column(db.Integer, primary_key=True)
    sheet_type  = db.Column(db.String(30), nullable=False, unique=True)  # 'environment' | 'ac_leakage'
    preset_data = db.Column(db.Text, nullable=False, default='{}')       # JSON 문자열
    updated_at  = db.Column(db.DateTime, default=db.func.current_timestamp(),
                             onupdate=db.func.current_timestamp())

    def to_dict(self):
        import json
        return {
            'sheet_type': self.sheet_type,
            'preset_data': json.loads(self.preset_data or '{}')
        }

# ==========================================================
# [섹션] 수리 (Repair) 관련 모델
# ==========================================================

# 1. 수리 군집 (고유주문 단위)
class RepairGroup(db.Model):
    __tablename__ = 'repair_groups'

    id          = db.Column(db.Integer, primary_key=True)
    model       = db.Column(db.String(100), nullable=False)
    order_year  = db.Column(db.Integer, nullable=False)
    order_month = db.Column(db.String(20), nullable=False)
    lot         = db.Column(db.String(50), nullable=False)
    notes       = db.Column(db.Text, default='')
    status      = db.Column(db.String(20), nullable=False, default='active')
    created_at  = db.Column(db.DateTime, default=datetime.now)
    done_at     = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint('model', 'order_year', 'order_month', 'lot',
                                          name='uix_repair_group_key'),)

    batches = db.relationship('RepairBatch', backref='group',
                              cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'model': self.model,
            'order_year': self.order_year,
            'order_month': self.order_month,
            'lot': self.lot,
            'notes': self.notes or '',
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else '',
            'done_at': self.done_at.strftime('%Y-%m-%d %H:%M') if self.done_at else None,
            'batches': [b.to_dict() for b in self.batches]
        }


# 2. 수리 배치 (AoiRecord 단위)
class RepairBatch(db.Model):
    __tablename__ = 'repair_batches'

    id            = db.Column(db.Integer, primary_key=True)
    group_id      = db.Column(db.Integer, db.ForeignKey('repair_groups.id'), nullable=False)
    aoi_record_id = db.Column(db.Integer, db.ForeignKey('aoi_records.id'), nullable=False, unique=True)
    defect_qty    = db.Column(db.Integer, nullable=False, default=0)
    aoi_date      = db.Column(db.String(20), default='')
    is_done       = db.Column(db.Boolean, nullable=False, default=False)
    done_at       = db.Column(db.DateTime, nullable=True)
    scrap_qty     = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'aoi_record_id': self.aoi_record_id,
            'defect_qty': self.defect_qty,
            'aoi_date': self.aoi_date or '',
            'is_done': self.is_done,
            'done_at': self.done_at.strftime('%Y-%m-%d %H:%M') if self.done_at else None,
            'scrap_qty': self.scrap_qty or 0
        }