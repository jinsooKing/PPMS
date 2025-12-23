from flask import Blueprint, request, jsonify, send_from_directory
from models import db, ProductionSchedule, Manager, Company, ProductModel, ModelData, ModelFolder
import os
from werkzeug.utils import secure_filename

bp = Blueprint('production', __name__, url_prefix='/api/production')

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ==============================================================================
# [1] 생산 일정 (Schedule) 관리 API (기존 기능 복구)
# ==============================================================================

@bp.route('/schedules', methods=['GET'])
def get_schedules():
    try:
        year = request.args.get('year')
        month = request.args.get('month')
        week = request.args.get('weekNum')

        query = ProductionSchedule.query
        if year: query = query.filter_by(prod_year=year)
        if month: query = query.filter_by(prod_month=month)
        if week: query = query.filter_by(prod_week=week)
        
        schedules_from_db = query.all()
        return jsonify([s.to_dict() for s in schedules_from_db])
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/schedules', methods=['POST'])
def save_schedules():
    try:
        data = request.json
        week_info = data['weekInfo']
        schedules = data['schedules']

        # 해당 주차의 기존 데이터 삭제 (덮어쓰기)
        ProductionSchedule.query.filter_by(
            prod_year=week_info['year'],
            prod_month=week_info['month'],
            prod_week=week_info['weekNum']
        ).delete()

        for s in schedules:
            new_schedule = ProductionSchedule(
                prod_year=week_info['year'],
                prod_month=week_info['month'],
                prod_week=week_info['weekNum'],
                line=s.get('line'),
                company=s.get('company'),
                model=s.get('model'),
                order_year=s.get('orderYear'),
                order_month=s.get('orderMonth'),
                tb=s.get('tb'),
                lot=s.get('lot'),
                manager=s.get('manager'),
                start_date=s.get('startDate'),
                end_date=s.get('endDate'),
                actual_prod=s.get('actualProd', 0), # 실생산
                # 노트 등 추가 필드 필요 시 모델에 맞춰 추가
            )
            db.session.add(new_schedule)
        
        db.session.commit()
        return jsonify({"message": "저장되었습니다."}), 201
    except Exception as e: 
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/schedules/<int:id>', methods=['PUT'])
def update_schedule(id):
    try:
        schedule = db.session.get(ProductionSchedule, id)
        if not schedule: return jsonify({"error": "Not found"}), 404
        
        data = request.json
        # 동적 업데이트
        for key, val in data.items():
            if hasattr(schedule, key):
                setattr(schedule, key, val)
            # CamelCase to SnakeCase mapping (if needed)
            if key == 'actualProd': schedule.actual_prod = val
            if key == 'prodStart': schedule.actual_start_date = val
            if key == 'prodEnd': schedule.actual_end_date = val

        db.session.commit()
        return jsonify({"message": "Updated"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/schedules/<int:id>/notes', methods=['PATCH'])
def update_schedule_note(id):
    try:
        schedule = db.session.get(ProductionSchedule, id)
        if not schedule: return jsonify({"error": "Not found"}), 404
        schedule.notes = request.json.get('notes')
        db.session.commit()
        return jsonify({"message": "Note updated"})
    except Exception as e: return jsonify({"error": str(e)}), 500


# ==============================================================================
# [2] 통합 디렉토리(폴더) 관리 API (공정 지도용)
# ==============================================================================

@bp.route('/directory', methods=['GET'])
def get_directory_contents():
    try:
        company_id = request.args.get('company_id')
        folder_id = request.args.get('folder_id')
        
        if not company_id: return jsonify({"error": "Company ID required"}), 400
        if folder_id in ['null', 'undefined', '']: folder_id = None
        
        folders = ModelFolder.query.filter_by(company_id=company_id, parent_folder_id=folder_id).all()
        models = ProductModel.query.filter_by(company_id=company_id, folder_id=folder_id).all()

        return jsonify({
            "folders": [{"id": f.id, "name": f.name, "type": "folder"} for f in folders],
            "models": [{"id": m.id, "name": m.name, "type": "model"} for m in models]
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/folders', methods=['POST'])
def create_folder():
    try:
        data = request.json
        pid = data.get('parent_folder_id')
        if pid in ['null', '', None]: pid = None
        
        db.session.add(ModelFolder(name=data['name'], company_id=data['company_id'], parent_folder_id=pid))
        db.session.commit()
        return jsonify({"message": "Created"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/folders/<int:id>', methods=['PUT', 'DELETE'])
def manage_folder(id):
    try:
        folder = db.session.get(ModelFolder, id)
        if not folder: return jsonify({"error": "Not found"}), 404
        
        if request.method == 'PUT':
            folder.name = request.json['name']
        elif request.method == 'DELETE':
            db.session.delete(folder)
            
        db.session.commit()
        return jsonify({"message": "Success"})
    except Exception as e: return jsonify({"error": str(e)}), 500


# ==============================================================================
# [3] 기준 정보 (업체/모델/담당자) API
# ==============================================================================

@bp.route('/companies', methods=['GET', 'POST'])
def manage_companies():
    try:
        if request.method == 'GET':
            comps = Company.query.order_by(Company.name).all()
            res = []
            for c in comps:
                cnt = ProductModel.query.filter_by(company_id=c.id).count()
                res.append({"id": c.id, "name": c.name, "model_count": cnt})
            return jsonify(res)
        
        elif request.method == 'POST':
            name = request.json['name']
            if Company.query.filter_by(name=name).first(): return jsonify({"error": "Exist"}), 400
            c = Company(name=name)
            db.session.add(c)
            db.session.commit()
            return jsonify({"message": "Created", "id": c.id}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/companies/<int:id>', methods=['PUT', 'DELETE'])
def company_item(id):
    try:
        comp = db.session.get(Company, id)
        if not comp: return jsonify({"error": "Not found"}), 404
        
        if request.method == 'PUT': comp.name = request.json['name']
        elif request.method == 'DELETE': db.session.delete(comp)
        
        db.session.commit()
        return jsonify({"message": "Success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/managers', methods=['GET', 'POST'])
def manage_managers():
    if request.method == 'GET':
        return jsonify([m.to_dict() for m in Manager.query.all()])
    try:
        db.session.add(Manager(name=request.json['name']))
        db.session.commit()
        return jsonify({"message": "Created"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/managers/<int:id>', methods=['DELETE'])
def delete_manager(id):
    try:
        m = db.session.get(Manager, id)
        db.session.delete(m); db.session.commit()
        return jsonify({"message": "Deleted"})
    except: return jsonify({"error": "Error"}), 500

# --- 모델 관련 ---
@bp.route('/models', methods=['POST'])
def create_model():
    try:
        data = request.json
        fid = data.get('folder_id')
        if fid in ['null', '', None]: fid = None
        
        db.session.add(ProductModel(name=data['name'], company_id=data['company_id'], folder_id=fid))
        db.session.commit()
        return jsonify({"message": "Created"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/models/<int:id>', methods=['PUT', 'DELETE'])
def manage_model(id):
    try:
        model = db.session.get(ProductModel, id)
        if not model: return jsonify({"error": "Not found"}), 404
        
        if request.method == 'PUT':
            if 'name' in request.json: model.name = request.json['name']
            if 'folder_id' in request.json: model.folder_id = request.json['folder_id']
        elif request.method == 'DELETE':
            db.session.delete(model)
            
        db.session.commit()
        return jsonify({"message": "Success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# [중요] production.html 호환용: 모델 존재 확인 및 자동 생성
@bp.route('/models/check-and-create', methods=['POST'])
def check_and_create_model():
    try:
        data = request.json
        c_name = data.get('company', '').strip()
        m_name = data.get('model', '').strip()
        do_create = data.get('create', False)

        if not c_name or not m_name: return jsonify({"error": "Invalid data"}), 400

        # 업체 확인
        comp = Company.query.filter_by(name=c_name).first()
        if not comp:
            if not do_create: return jsonify({"status": "missing_company"})
            # 업체 생성
            comp = Company(name=c_name)
            db.session.add(comp)
            db.session.commit()

        # 모델 확인
        model = ProductModel.query.filter_by(company_id=comp.id, name=m_name).first()
        if not model:
            if not do_create: return jsonify({"status": "missing_model"})
            # 모델 생성 (기본적으로 최상위 루트에 생성)
            model = ProductModel(name=m_name, company_id=comp.id, folder_id=None)
            db.session.add(model)
            db.session.commit()
            return jsonify({"status": "created", "model_id": model.id})
        
        return jsonify({"status": "exists", "model_id": model.id})

    except Exception as e: return jsonify({"error": str(e)}), 500


# ==============================================================================
# [4] 파일 데이터 (BOM/좌표)
# ==============================================================================

@bp.route('/models/<int:model_id>/data', methods=['GET', 'POST'])
def handle_model_data(model_id):
    try:
        if request.method == 'GET':
            dtype = request.args.get('type')
            q = ModelData.query.filter_by(model_id=model_id)
            if dtype: q = q.filter_by(data_type=dtype)
            return jsonify([d.to_dict() for d in q.all()])
        
        elif request.method == 'POST':
            if 'file' not in request.files: return jsonify({"error": "No file"}), 400
            file = request.files['file']
            dtype = request.form.get('type')
            if file.filename == '': return jsonify({"error": "No filename"}), 400
            
            orig = secure_filename(file.filename)
            saved = f"{model_id}_{dtype}_{orig}"
            file.save(os.path.join(UPLOAD_FOLDER, saved))
            
            exist = ModelData.query.filter_by(model_id=model_id, data_type=dtype).first()
            if exist: exist.file_name = orig; exist.content = saved
            else: db.session.add(ModelData(model_id=model_id, data_type=dtype, file_name=orig, content=saved))
            
            db.session.commit()
            return jsonify({"message": "Uploaded"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/download/<path:filename>', methods=['GET'])
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)