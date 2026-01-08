from flask import Blueprint, request, jsonify
# [중요] 필요한 모델 모두 Import
from models import db, AoiRecord, ProductionSchedule, DipGroup, DipHistory
from sqlalchemy import or_, and_, func
from datetime import datetime
from dateutil.relativedelta import relativedelta

bp = Blueprint('aoi', __name__, url_prefix='/api/aoi')

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
        
        # 1. 날짜 범위 설정
        if not all([s_year, s_month, e_year, e_month]):
            start_dt = now - relativedelta(months=1)
            end_dt = now + relativedelta(months=1)
        else:
            start_dt = datetime(int(s_year), int(s_month), 1)
            end_dt = datetime(int(e_year), int(e_month), 1)

        # 2. 검색 대상 기간 생성
        period_filters = []
        curr = start_dt
        while curr <= end_dt:
            y_int = int(curr.year) 
            m_str_1 = f"{curr.month}월분"
            m_str_2 = str(curr.month)
            
            period_filters.append(and_(DipGroup.year == y_int, DipGroup.month == m_str_1))
            period_filters.append(and_(DipGroup.year == y_int, DipGroup.month == m_str_2))
            
            curr += relativedelta(months=1)

        # 3. 필터링 쿼리 실행
        # 조건: 기간 일치 AND 상태가 'aoi_completed'가 아닌 것
        # ('ongoing' 상태인 그룹들이 검색됨)
        dip_groups = DipGroup.query.filter(
            or_(*period_filters),
            DipGroup.status != 'aoi_completed' 
        ).all()

        # 4. 업체명 매핑 (생산 스케줄 참조)
      # [수정] aoi.py 내 get_available_models 함수의 업체 매핑 부분
        # 4. 업체명 매핑 (생산 스케줄 참조)
        prods = db.session.query(
            ProductionSchedule.model,
            ProductionSchedule.order_year,
            ProductionSchedule.order_month,
            ProductionSchedule.total_quantity,
            ProductionSchedule.company
        ).all()
        
        company_map = {}
        for p in prods:
            # [핵심 보정] 연도는 숫자형(int) 그대로 사용, 월은 '월분' 제거하여 정규화
            m_norm = str(p.order_month).replace('월분', '').replace('월', '').strip()
            key = (p.model, p.order_year, m_norm, str(p.total_quantity))
            company_map[key] = p.company

        # 5. 데이터 가공
        grouped_result = {}

        for g in dip_groups:
            # 수량 집계
            total_ship = sum(h.quantity for h in g.histories if h.type == 'ship')
            total_recv = sum(h.quantity for h in g.histories if h.type == 'receive')
            
            # [핵심 보정] DIP 그룹의 월 데이터도 동일하게 정규화하여 매칭률 향상
            g_month_norm = str(g.month).replace('월분', '').replace('월', '').strip()
            
            # AOI 누적 검사 수량 조회 시 사용하는 월 포맷
            m_query_str = g_month_norm

            # AOI 누적 검사 수량 조회
            aoi_total = db.session.query(func.sum(AoiRecord.inspection_qty)).filter_by(
                model=g.model,
                order_year=g.year,       
                order_month=m_query_str, 
                lot=g.lot
            ).scalar() or 0

            # 정규화된 정보를 바탕으로 업체명 검색
            group_key = (g.model, g.year, g_month_norm, g.lot)
            company = company_map.get(group_key, '업체 미지정')

            if company not in grouped_result:
                grouped_result[company] = []

            grouped_result[company].append({
                'id': g.id,
                'model': g.model,
                'year': g.year,
                'month': str(g.month).replace('월분', ''),
                'lot': g.lot,
                'ship_qty': total_ship,
                'recv_qty': total_recv,
                'aoi_qty': aoi_total
            })

        return jsonify([{'company': k, 'models': v} for k, v in grouped_result.items()])

    except Exception as e:
        print(f"Error fetching available models: {e}")
        return jsonify({'error': str(e)}), 500

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

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500