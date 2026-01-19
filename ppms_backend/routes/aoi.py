from flask import Blueprint, request, jsonify, render_template
# [중요] 필요한 모델 모두 Import
from models import db, AoiRecord, ProductionSchedule, DipGroup, DipHistory
from sqlalchemy import or_, and_, func
from datetime import datetime
from dateutil.relativedelta import relativedelta
from difflib import SequenceMatcher

bp = Blueprint('aoi', __name__, url_prefix='/api/aoi')

@bp.route('/view', methods=['GET'])
def aoi_view():
    # templates 폴더 내의 aoi.html 파일을 읽어서 전달합니다.
    return render_template('aoi.html')

def calculate_similarity(a, b):
    """문자열 유사도를 0.0 ~ 1.0 사이로 반환 (공백 무시, 대소문자 무시)"""
    a = str(a).upper().replace(" ", "").strip()
    b = str(b).upper().replace(" ", "").strip()
    return SequenceMatcher(None, a, b).ratio()

# -------------------------------------------------------------------------
# [Helper] 수량 감소 시 완료 상태를 해제하는 함수 (복구 로직)
# -------------------------------------------------------------------------
def check_and_revert_status(model, year, month, lot):
    try:
        # [방어 로직 1] 연도는 정수형으로 변환
        try:
            year_int = int(year)
        except:
            year_int = year 

        # [방어 로직 2] 월 포맷 유연화 ("12월분", "12" 모두 찾기)
        month_str_1 = f"{month}월분"
        month_str_2 = str(month)
        
        # 1. 그룹 찾기 (DipGroup.year는 Integer)
        group = DipGroup.query.filter(
            DipGroup.model == model,
            DipGroup.year == year_int, 
            (DipGroup.month == month_str_1) | (DipGroup.month == month_str_2),
            DipGroup.lot == str(lot)
        ).first()

        if not group:
            # 디버깅용 로그 (서버 콘솔에서 확인 가능)
            print(f"[AOI Debug] 그룹 찾기 실패: {model}, {year}, {month}, {lot}")
            return

        # 2. 이미 '완료(aoi_completed)' 상태인 경우에만 체크
        if group.status == 'aoi_completed':
            
            # AoiRecord 조회용 월 포맷 정규화 ("12월분" -> "12")
            try:
                m_clean_int = int(str(month).replace('월분', '').replace('월', ''))
                m_query_str = str(m_clean_int) 
            except:
                m_query_str = str(month)

            current_aoi_total = db.session.query(func.sum(AoiRecord.inspection_qty)).filter_by(
                model=model,
                order_year=year_int,     
                order_month=m_query_str, 
                lot=str(lot)
            ).scalar() or 0
            
            # 비교 대상 LOT 수량 (쉼표 제거)
            try:
                target_lot = int(str(lot).replace(',', ''))
            except:
                target_lot = 0
            
            print(f"[AOI Check] {model} | 현재:{current_aoi_total} / 목표:{target_lot}")

            # 3. [핵심 수정] 수량이 LOT보다 적어지면 -> 상태를 'ongoing'으로 변경
            # (None으로 설정하면 DB의 nullable=False 제약조건 때문에 저장이 거부됨)
            if current_aoi_total < target_lot:
                group.status = 'ongoing'  # <--- ★ 여기가 수정된 부분입니다 ★
                db.session.commit()
                print(f"[AOI System] '{model}' 모델의 상태가 '진행중(ongoing)'으로 복구되었습니다.")

    except Exception as e:
        print(f"[AOI Error] Status Revert Failed: {e}")
        pass

# -------------------------------------------------------------------------
# [API 1] 생산완료 모델 목록 조회
# -------------------------------------------------------------------------
@bp.route('/available_models', methods=['GET'])
def get_available_models():
    try:
        s_year = request.args.get('start_year')
        s_month = request.args.get('start_month')
        e_year = request.args.get('end_year')
        e_month = request.args.get('end_month')
        
        now = datetime.now()
        
        # 1. 날짜 범위 설정 (조회 기간)
        if not all([s_year, s_month, e_year, e_month]):
            start_dt = now - relativedelta(months=1)
            end_dt = now + relativedelta(months=1)
        else:
            start_dt = datetime(int(s_year), int(s_month), 1)
            end_dt = datetime(int(e_year), int(e_month), 1)

        # 2. 생산 계획(ProductionSchedule) 조회
        # [핵심 수정] 이제 DipGroup이 아닌 생산 계획 테이블을 직접 바라봅니다.
        query = ProductionSchedule.query

        # prod_year, prod_month 숫자를 이용해 기간 필터링
        query = query.filter(
            (ProductionSchedule.prod_year * 100 + ProductionSchedule.prod_month) >= (start_dt.year * 100 + start_dt.month),
            (ProductionSchedule.prod_year * 100 + ProductionSchedule.prod_month) <= (end_dt.year * 100 + end_dt.month)
        )

        schedules = query.all()

        # 3. 데이터 가공 및 그룹화
        grouped_result = {}

        for s in schedules:
            company = s.company or '업체 미지정'
            if company not in grouped_result:
                grouped_result[company] = []

            # [핵심 매핑] 
            # - recv_qty: ProductionSchedule에 저장된 조립 실적(assy_actual)
            # - aoi_qty: ProductionSchedule에 저장된 AOI 실적(aoi_insp_qty)
            # - lot: 생산 계획의 목표 수량(total_quantity)
            
            grouped_result[company].append({
                'id': s.id,
                'model': s.model,
                'year': s.order_year,  # 통계 매칭용 연도 (Int)
                'month': str(s.order_month).replace('월분', '').strip(), # 통계 매칭용 월 (String)
                'lot': str(s.total_quantity),
                'recv_qty': getattr(s, 'assy_actual', 0) or 0,
                'aoi_qty': getattr(s, 'aoi_insp_qty', 0) or 0
            })

        return jsonify([{'company': k, 'models': v} for k, v in grouped_result.items()])

    except Exception as e:
        print(f"Error fetching available models from schedule: {e}")
        return jsonify({'error': str(e)}), 500
    
def sync_aoi_to_schedule(model, year, month, lot):
    """AOI 실적을 메인 ProductionSchedule 테이블에 동기화 (LOT '/' 규칙 적용)"""
    try:
        # 1. LOT 문자열 파싱 (생산일정 등록과 동일한 규칙 적용)
        lot_str = str(lot).strip()
        target_total_qty = 0
        
        if '/' in lot_str:
            # '100/500' 형태일 경우 뒤의 500을 전체 수량으로 인식
            parts = lot_str.split('/')
            try:
                if len(parts) > 1 and parts[1].strip():
                    target_total_qty = int(parts[1])
                else:
                    target_total_qty = int(parts[0])
            except ValueError:
                target_total_qty = 0
        else:
            # '/'가 없으면 입력값 자체가 전체 수량
            try:
                target_total_qty = int(lot_str)
            except ValueError:
                target_total_qty = 0

        # 2. 해당 모델/LOT의 모든 AOI 기록 합산
        totals = db.session.query(
            func.sum(AoiRecord.inspection_qty).label('total_insp'),
            func.sum(AoiRecord.total_defect).label('total_defect')
        ).filter_by(
            model=model, 
            order_year=year, 
            order_month=str(month), 
            lot=lot_str # DB의 lot 문자열과 일치하는 기록 합산
        ).first()

        total_insp = totals.total_insp or 0
        total_defect = totals.total_defect or 0

        # 3. ProductionSchedule 테이블에서 동기화할 대상 탐색
        # total_quantity 컬럼을 기준으로 비교하여 정확한 매칭 수행
        schedule = ProductionSchedule.query.filter_by(
            model=model, 
            order_year=year, 
            order_month=str(month), 
            total_quantity=target_total_qty
        ).first()
        
        if schedule:
            schedule.aoi_insp_qty = total_insp
            schedule.aoi_defect_qty = total_defect
            db.session.commit()
            print(f"[AOI Sync Success] {model} (Total LOT: {target_total_qty})")
        else:
            print(f"[AOI Sync Skip] 계획에 없는 모델이거나 수량이 일치하지 않습니다: {model}")
            
    except Exception as e:
        print(f"[AOI Sync Error] {e}")
        db.session.rollback()
    
@bp.route('/sync_manual_record', methods=['POST'])
def sync_manual_record():
    """수동 입력된 AOI 기록을 공식 생산계획 데이터로 덮어쓰고 통합함"""
    try:
        data = request.json
        # AOI에 수동 입력된 정보 (검색용)
        manual_model = data['manual_model']
        manual_lot = data['manual_lot']
        
        # 생산계획서의 공식 정보 (덮어씌울 기준)
        official_model = data['official_model']
        official_lot = str(data['official_lot'])
        official_year = int(data['official_year'])
        official_month = str(data['official_month']).replace('월분', '').strip()

        # 1. 수동 입력된 모든 AOI 기록 찾기
        records = AoiRecord.query.filter_by(
            model=manual_model, 
            lot=manual_lot
        ).all()
        
        if not records:
            return jsonify({"success": False, "message": "통합할 수동 기록을 찾을 수 없습니다."}), 404

        # 2. 공식 데이터로 덮어쓰기 (생산계획 우선 원칙)
        for r in records:
            r.model = official_model
            r.lot = official_lot
            r.order_year = official_year
            r.order_month = official_month
        
        db.session.commit()

        # 3. 통합된 실적을 메인 계획 테이블(ProductionSchedule)에 즉시 반영
        sync_aoi_to_schedule(official_model, official_year, official_month, official_lot)

        return jsonify({
            "success": True, 
            "message": f"[{manual_model}] 기록이 공식 모델 [{official_model}]으로 통합되었습니다."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# -------------------------------------------------------------------------
# [API 1-1] AOI 검사 완료 처리 (리스트에서 숨기기)
# -------------------------------------------------------------------------
@bp.route('/groups/<int:group_id>/complete', methods=['POST'])
def complete_aoi_group(group_id):
    try:
        group = DipGroup.query.get_or_404(group_id)
        group.status = 'aoi_completed'
        db.session.commit()
        return jsonify({'success': True, 'message': '검사 완료 처리되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# [API 2] 메인 화면 테이블 데이터 조회
@bp.route('/records', methods=['GET'])
def get_aoi_records():
    try:
        model = request.args.get('model')
        year = request.args.get('year')
        month = request.args.get('month')
        lot = request.args.get('lot')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = AoiRecord.query

        if model and year and month and lot:
            query = query.filter_by(model=model, order_year=year, order_month=month, lot=lot)
        elif start_date and end_date:
            query = query.filter(AoiRecord.date >= start_date, AoiRecord.date <= end_date)
        else:
            target_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
            query = query.filter_by(date=target_date)

        records = query.order_by(AoiRecord.id.desc()).all()
        
        results = []
        lot_cache = {} 

        for r in records:
            r_dict = r.to_dict()
            lot_key = (r.model, r.order_year, r.order_month, r.lot)
            if lot_key not in lot_cache:
                total_qty = db.session.query(func.sum(AoiRecord.inspection_qty)).filter_by(
                    model=r.model, order_year=r.order_year, order_month=r.order_month, lot=r.lot
                ).scalar()
                lot_cache[lot_key] = total_qty or 0
            r_dict['cumulative_qty'] = lot_cache[lot_key]
            results.append(r_dict)

        return jsonify(results)

    except Exception as e:
        print(f"Error fetching records: {e}")
        return jsonify({"error": str(e)}), 500

# [API 3] 기록 생성
@bp.route('/records', methods=['POST'])
def add_aoi_record():
    try:
        data = request.json
        new_record = AoiRecord(
            model=data['model'], order_year=data['year'], order_month=data['month'], lot=str(data['lot']),
            date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
            inspection_point=0, inspection_qty=0,
            reverse=0, missing=0, wrong=0, skewed=0, flipped=0,
            unsoldered=0, damaged=0, manhattan=0, short=0,
            cold=0, lifted=0, detached=0, material=0, dip=0,
            reverse_ref='', missing_ref='', wrong_ref='', skewed_ref='', flipped_ref='',
            unsoldered_ref='', damaged_ref='', manhattan_ref='', short_ref='',
            cold_ref='', lifted_ref='', detached_ref='', material_ref='', dip_ref='',
            total_defect=0, good_qty=0
        )
        db.session.add(new_record)
        db.session.commit()
        sync_aoi_to_schedule(data['model'], data['year'], data['month'], data['lot'])
        
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# [API 4] 기록 수정 (상태 복구 로직 포함)
@bp.route('/records/<int:record_id>', methods=['PUT'])
def update_aoi_record(record_id):
    try:
        data = request.json
        record = AoiRecord.query.get_or_404(record_id)
        
        editable_fields = [
            'inspection_point', 'inspection_qty', 
            'reverse', 'missing', 'wrong', 'skewed', 'flipped', 'unsoldered',
            'damaged', 'manhattan', 'short', 'cold', 'lifted', 'detached', 'material', 'dip',
            'reverse_ref', 'missing_ref', 'wrong_ref', 'skewed_ref', 'flipped_ref', 'unsoldered_ref',
            'damaged_ref', 'manhattan_ref', 'short_ref', 'cold_ref', 'lifted_ref', 'detached_ref', 'material_ref', 'dip_ref'
        ]
        
        for field in editable_fields:
            if field in data:
                if field.endswith('_ref'): setattr(record, field, str(data[field]))
                else: setattr(record, field, int(data[field]))
        
        total_defect = (
            record.reverse + record.missing + record.wrong + record.skewed + record.flipped + 
            record.unsoldered + record.damaged + record.manhattan + record.short + 
            record.cold + record.lifted + record.detached + record.material + record.dip
        )
        record.total_defect = total_defect
        if record.inspection_qty: record.good_qty = record.inspection_qty - total_defect
        else: record.good_qty = 0

        # 1. 커밋
        db.session.commit()
        check_and_revert_status(record.model, record.order_year, record.order_month, record.lot)
        sync_aoi_to_schedule(record.model, record.order_year, record.order_month, record.lot)

        # 2. 상태 복구 체크 (커밋 후 실행)
        check_and_revert_status(record.model, record.order_year, record.order_month, record.lot)

        return jsonify({'success': True, 'updated_record': record.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# [API 5] 기록 삭제 (상태 복구 로직 포함)
@bp.route('/records/<int:record_id>', methods=['DELETE'])
def delete_aoi_record(record_id):
    try:
        record = AoiRecord.query.get_or_404(record_id)
        
        model, year, month, lot = record.model, record.order_year, record.order_month, record.lot

        db.session.delete(record)
        db.session.commit()

        check_and_revert_status(model, year, month, lot)
        sync_aoi_to_schedule(model, year, month, lot)

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500