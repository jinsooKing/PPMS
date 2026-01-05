from flask import Blueprint, request, jsonify, send_from_directory
from models import db, ProductionSchedule, Manager, Company, ProductModel, ModelData, ModelFolder
import os
from werkzeug.utils import secure_filename
from flask import current_app
import re

bp = Blueprint('production', __name__, url_prefix='/api/production')

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ==============================================================================
# [1] 생산 일정 (Schedule) 관리 API (기존 기능 복구)
# ==============================================================================

def normalize_name(name):
    if not name: return ""
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', name).upper()

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

# [전체 교체] models.py 변경 사항(LOT -> Batch/Total)을 반영한 저장 로직
@bp.route('/schedules', methods=['POST'])
def save_schedules():
    try:
        data = request.json
        week_info = data['weekInfo']
        schedules = data['schedules']

        # 1. 해당 주차의 기존 데이터 삭제 (덮어쓰기 방식)
        # 주의: 이렇게 하면 기존의 Notes(비고)가 삭제될 수 있으므로, 
        # 실제 운영 시에는 기존 데이터를 조회하여 Notes를 백업하거나 Update 방식을 권장합니다.
        ProductionSchedule.query.filter_by(
            prod_year=week_info['year'],
            prod_month=week_info['month'],
            prod_week=week_info['weekNum']
        ).delete()

        for s in schedules:
            # [핵심 수정] 프론트엔드의 문자열 LOT("100/200" 또는 "100")을 정수형 Batch/Total로 변환
            lot_str = str(s.get('lot', '')).strip()
            batch_qty = 0
            total_qty = 0
            
            if '/' in lot_str:
                parts = lot_str.split('/')
                try:
                    batch_qty = int(parts[0])
                    # 뒤에 숫자가 있을 때만 파싱
                    if len(parts) > 1 and parts[1].strip():
                        total_qty = int(parts[1])
                except ValueError:
                    pass # 숫자가 아닌 경우 0으로 처리
            elif lot_str:
                try:
                    # "/"가 없으면 입력값을 Batch로, Total은 동일하게(또는 0) 처리
                    batch_qty = int(lot_str)
                    total_qty = batch_qty 
                except ValueError:
                    pass

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
                # [수정] lot 컬럼 제거 -> batch_quantity, total_quantity 매핑
                batch_quantity=batch_qty,
                total_quantity=total_qty,
                manager=s.get('manager'),
                start_date=s.get('startDate'),
                end_date=s.get('endDate'),
                actual_prod=s.get('actualProd', 0)
            )
            db.session.add(new_schedule)
        
        db.session.commit()
        return jsonify({"message": "저장되었습니다."}), 201
    except Exception as e: 
        db.session.rollback()
        # 디버깅을 위해 에러 로그 출력
        print(f"Error saving schedules: {str(e)}")
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
    
    # [추가] 모델 이동 및 복사 API
@bp.route('/models/transfer', methods=['POST'])
def transfer_model():
    try:
        data = request.json
        action = data.get('action') # 'copy' 또는 'move'
        target_folder_id = data.get('target_folder_id')
        
        # 1. 단일 ID와 리스트 형태 모두 호환되도록 처리
        model_ids = data.get('model_ids', [])
        if not model_ids and data.get('model_id'):
            model_ids = [data.get('model_id')]
            
        if not model_ids:
            return jsonify({"error": "선택된 항목이 없습니다."}), 400

        if target_folder_id in ['null', '', None, 'root']: 
            target_folder_id = None

        if action == 'move':
            # [이동/잘라내기] 원본을 지우는 게 아니라 folder_id만 한꺼번에 변경합니다.
            ProductModel.query.filter(ProductModel.id.in_(model_ids)).update(
                {ProductModel.folder_id: target_folder_id}, 
                synchronize_session=False
            )
            db.session.commit()
            return jsonify({"message": f"{len(model_ids)}개 항목 이동 완료"})

        elif action == 'copy':
            # [복사] 원본은 두고 새로운 데이터를 생성합니다.
            for mid in model_ids:
                source = db.session.get(ProductModel, mid)
                if not source: continue
                
                # 모델 복제
                new_model = ProductModel(
                    name=f"{source.name}_복사본",
                    company_id=source.company_id,
                    folder_id=target_folder_id,
                    section=source.section,
                    type=source.type
                )
                db.session.add(new_model)
                db.session.flush() # 신규 ID 할당을 위해 수행
                
                # 내부 데이터(BOM 등) 복제
                original_data = ModelData.query.filter_by(model_id=mid).all()
                for d in original_data:
                    db.session.add(ModelData(
                        model_id=new_model.id,
                        data_type=d.data_type,
                        content=d.content,
                        file_name=d.file_name
                    ))
            
            db.session.commit()
            return jsonify({"message": f"{len(model_ids)}개 항목 복사 완료"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# [3] 기준 정보 (업체/모델/담당자) API
# ==============================================================================
# [전체 교체] production.py: 섹션별 모델 개수를 정확히 집계하는 로직
@bp.route('/companies', methods=['GET', 'POST'])
def manage_companies():
    try:
        if request.method == 'GET':
            # [수정] 쿼리 파라미터로 섹션 정보를 받음 (기본값 'common')
            section = request.args.get('section', 'common')
            
            comps = Company.query.order_by(Company.name).all()
            res = []
            for c in comps:
                # [핵심 수정] 해당 업체 ID와 요청된 섹션이 일치하는 모델만 카운트
                cnt = ProductModel.query.filter_by(
                    company_id=c.id, 
                    section=section
                ).count()
                
                res.append({
                    "id": c.id, 
                    "name": c.name, 
                    "model_count": cnt
                })
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

# [전체 교체] 부서 순서(생산-품질-기능-관리)가 반영된 담당자 관리 API
@bp.route('/managers', methods=['GET', 'POST'])
def manage_managers():
    if request.method == 'GET':
        try:
            # 1. 정렬 기준 설정: 생산(1) > 품질(2) > 기능(3) > 관리(4)
            dept_order = {"생산": 1, "품질": 2, "기능": 3, "관리": 4}
            # 직급 순서: 부장(1) > 차장(2) > 과장(3) > 대리(4) > 주임(5) > 사원(6)
            rank_order = {"부장": 1, "차장": 2, "과장": 3, "대리": 4, "주임": 5, "사원": 6}
            
            managers = Manager.query.all()
            
            # 2. 부서 순서 우선 정렬 후, 부서 내에서 직급순으로 정렬
            sorted_managers = sorted(managers, key=lambda m: (
                dept_order.get(m.department, 99),
                rank_order.get(m.position, 99)
            ))
            
            return jsonify([m.to_dict() for m in sorted_managers])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.json
            name = data.get('name')
            if not name:
                return jsonify({"error": "이름을 입력하세요."}), 400
            
            # 모달에서 전달받은 상세 정보 추가 저장
            new_manager = Manager(
                name=name,
                position=data.get('position'),
                department=data.get('department'),
                roles=data.get('roles'),
                contact=data.get('contact'),
                email=data.get('email')
            )
            db.session.add(new_manager)
            db.session.commit()
            return jsonify({"message": "Created", "id": new_manager.id}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

@bp.route('/managers/<int:id>', methods=['DELETE'])
def delete_manager(id):
    try:
        m = db.session.get(Manager, id)
        db.session.delete(m); db.session.commit()
        return jsonify({"message": "Deleted"})
    except: return jsonify({"error": "Error"}), 500
    
# [추가] 담당자 상세 정보 수정 API
@bp.route('/managers/<int:manager_id>', methods=['PUT'])
def update_manager(manager_id):
    try:
        manager = Manager.query.get_or_404(manager_id)
        data = request.json

        # 프론트엔드에서 보낸 데이터로 필드 업데이트
        if 'position' in data:
            manager.position = data.get('position')
        if 'department' in data:
            manager.department = data.get('department')
        if 'roles' in data:
            manager.roles = data.get('roles')
        if 'contact' in data:
            manager.contact = data.get('contact')
        if 'email' in data:
            manager.email = data.get('email')
        
        # 이름 수정이 필요한 경우 (Context Menu용)
        if 'name' in data:
            manager.name = data.get('name')

        db.session.commit()
        return jsonify({'success': True, 'message': '담당자 정보가 수정되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- 모델 관련 ---
@bp.route('/models', methods=['POST'])
def create_model():
    try:
        data = request.json
        fid = data.get('folder_id')
        section = data.get('section', 'production') # 섹션 정보 가져오기
        if fid in ['null', '', None]: fid = None
        
        # [수정] 생성 시 section 정보 포함
        db.session.add(ProductModel(
            name=data['name'], 
            company_id=data['company_id'], 
            folder_id=fid,
            section=section
        ))
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

# [전체 교체] 정규화 비교가 적용된 모델 체크 함수
@bp.route('/models/check-and-create', methods=['POST'])
def check_and_create_model():
    try:
        data = request.json
        c_name = data.get('company', '').strip()
        m_name = data.get('model', '').strip()
        do_create = data.get('create', False)
        folder_id = data.get('folder_id') 
        section = data.get('section', 'common') 

        if not c_name or not m_name: 
            return jsonify({"error": "Invalid data"}), 400

        comp = Company.query.filter_by(name=c_name).first()
        if not comp:
            return jsonify({"status": "missing_company"}), 200

        # [핵심 수정] 1. 해당 업체의 모든 모델을 가져옴
        existing_models = ProductModel.query.filter_by(company_id=comp.id, section=section).all()
        
        # 2. 입력받은 모델명을 정규화함
        input_norm = normalize_name(m_name)
        
        # 3. 기존 모델 중 정규화된 이름이 일치하는 것이 있는지 탐색
        found_model = None
        for em in existing_models:
            if normalize_name(em.name) == input_norm:
                found_model = em
                break
        
        # 일치하는 모델이 없는 경우
        if not found_model:
            if not do_create: 
                return jsonify({"status": "missing_model", "company_id": comp.id})
            
            new_model = ProductModel(
                name=m_name, 
                company_id=comp.id, 
                folder_id=folder_id if folder_id else None,
                section=section 
            )
            db.session.add(new_model)
            db.session.commit()
            return jsonify({"status": "created", "model_id": new_model.id})
        
        # 일치하는 모델이 이미 있는 경우 (정규화된 이름 기준)
        return jsonify({"status": "exists", "model_id": found_model.id})

    except Exception as e: 
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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

# [추가] 섹션별 전역 검색 API
@bp.route('/search', methods=['GET'])
def search_global():
    section = request.args.get('section', 'production')
    query = request.args.get('query', '')
    
    if not query:
        return jsonify({"folders": [], "models": []})

    # 1. 해당 섹션에 속한 폴더 검색
    folders = ModelFolder.query.filter(
        ModelFolder.section == section,
        ModelFolder.name.ilike(f'%{query}%')
    ).all()
    
    # 2. 해당 섹션 폴더들에 포함된 모델 검색
    # (참고: ProductModel은 folder_id를 통해 ModelFolder와 연결됨)
    section_folders = ModelFolder.query.filter_by(section=section).all()
    section_folder_ids = [f.id for f in section_folders]
    
    models = ProductModel.query.filter(
        ProductModel.folder_id.in_(section_folder_ids),
        ProductModel.name.ilike(f'%{query}%')
    ).all()
    
    return jsonify({
        "folders": [{"id": f.id, "name": f.name, "type": "folder", "company_id": f.company_id, "section": f.section} for f in folders],
        "models": [{"id": m.id, "name": m.name, "type": "model", "company_id": m.company_id} for m in models]
    })

# [production.py] 디렉토리 조회 및 생성 로직 전면 수정

@bp.route('/directory', methods=['GET'])
def get_directory_contents():
    try:
        company_id = request.args.get('company_id')
        folder_id = request.args.get('folder_id')
        section = request.args.get('section', 'production')
        
        if folder_id in ['null', 'undefined', '', 'root']: folder_id = None
        if company_id in ['null', 'undefined', '']: company_id = None

        # [핵심 수정] 
        # common 섹션: 기존처럼 company_id 필수
        # 그 외 섹션: company_id가 없어도(None) 해당 섹션의 루트 폴더 조회 가능
        query_filter = {
            'section': section,
            'parent_folder_id': folder_id
        }
        if company_id: # 업체 내부를 조회하는 경우
            query_filter['company_id'] = company_id
        elif section != 'common': # 자유 탭의 루트인 경우 (업체 필터 제거)
            query_filter['company_id'] = None

        folders = ModelFolder.query.filter_by(**query_filter).all()
        
        # 모델/파일 조회도 동일한 로직 적용
        model_filter = {
            'section': section,
            'folder_id': folder_id
        }
        if company_id:
            model_filter['company_id'] = company_id
        elif section != 'common':
            model_filter['company_id'] = None

        models = ProductModel.query.filter_by(**model_filter).all()

        return jsonify({
            "folders": [{"id": f.id, "name": f.name, "type": "folder"} for f in folders],
            "models": [m.to_dict() for m in models]
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/folders', methods=['POST'])
def create_folder():
    try:
        data = request.json
        pid = data.get('parent_folder_id')
        section = data.get('section', 'production')
        comp_id = data.get('company_id') # 없을 수 있음

        if pid in ['null', '', None]: pid = None
        if comp_id in ['null', '', None]: comp_id = None
        
        db.session.add(ModelFolder(
            name=data['name'], 
            company_id=comp_id, # None 허용
            parent_folder_id=pid,
            section=section
        ))
        db.session.commit()
        return jsonify({"message": "Created"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/files/upload', methods=['POST'])
def upload_general_file():
    try:
        if 'file' not in request.files: return jsonify({"error": "No file"}), 400
        file = request.files['file']
        
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > 50 * 1024 * 1024: return jsonify({"error": "File too large"}), 413

        folder_id = request.form.get('folder_id')
        company_id = request.form.get('company_id')
        section = request.form.get('section', 'production')

        if folder_id in ['null', 'undefined', '']: folder_id = None
        if company_id in ['null', 'undefined', '']: company_id = None

        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, f"gen_{section}_{filename}")
        file.save(save_path)
        
        new_file = ProductModel(
            name=filename,
            company_id=company_id, # None 허용
            folder_id=folder_id,
            section=section,
            type='file'
        )
        db.session.add(new_file)
        db.session.commit()

        return jsonify({"message": "Success"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500