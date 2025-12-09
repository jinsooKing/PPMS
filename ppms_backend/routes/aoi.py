from flask import Blueprint, request, jsonify
from models import db, AoiRecord, ProductionSchedule
from sqlalchemy import or_, and_, func
from datetime import datetime
from dateutil.relativedelta import relativedelta # [수정] 오타 해결

bp = Blueprint('aoi', __name__, url_prefix='/api/aoi')

@bp.route('/available_models', methods=['GET'])
def get_available_models():
    try:
        # 1. 파라미터 받기
        s_year = request.args.get('start_year')
        s_month = request.args.get('start_month')
        e_year = request.args.get('end_year')
        e_month = request.args.get('end_month')
        
        now = datetime.now()
        
        # 2. 값 없으면 기본값 (현재월 ±1개월)
        if not all([s_year, s_month, e_year, e_month]):
            start_dt = now - relativedelta(months=1)
            end_dt = now + relativedelta(months=1)
        else:
            start_dt = datetime(int(s_year), int(s_month), 1)
            end_dt = datetime(int(e_year), int(e_month), 1)

        # 3. 검색 대상 기간의 (연도, 월) 리스트 생성
        # 예: 2025-11 ~ 2026-01 -> [(2025, "11월분"), (2025, "12월분"), (2026, "1월분")]
        target_periods = []
        curr = start_dt
        # 종료 월까지 루프 (연/월만 비교하므로 day는 1일로 고정)
        while curr <= end_dt:
            # DB 저장 형식("1월분", "12월분")에 맞춤 (앞에 0 제거)
            month_str = f"{curr.month}월분" 
            target_periods.append((curr.year, month_str))
            curr += relativedelta(months=1)

        # 4. 쿼리 생성 (OR 조건으로 여러 기간 검색)
        # (year=2025 AND month='11월분') OR (year=2026 AND month='1월분') ...
        period_filters = [
            and_(ProductionSchedule.order_year == y, ProductionSchedule.order_month == m)
            for y, m in target_periods
        ]

        query = db.session.query(
            ProductionSchedule.company,
            ProductionSchedule.model,
            ProductionSchedule.order_year,
            ProductionSchedule.order_month,
            ProductionSchedule.total_quantity
        ).filter(
            ProductionSchedule.actual_prod > 0, # 실적 있는 것만
            or_(*period_filters) # 위에서 만든 기간 조건 적용
        ).group_by(
            ProductionSchedule.company, ProductionSchedule.model,
            ProductionSchedule.order_year, ProductionSchedule.order_month,
            ProductionSchedule.total_quantity
        ).order_by(
            ProductionSchedule.company, 
            ProductionSchedule.order_year.desc(), 
            ProductionSchedule.order_month.desc()
        )

        models = query.all()
        
        # 5. 결과 포맷팅
        grouped = {}
        for m in models:
            comp = m.company if m.company else '미지정'
            if comp not in grouped: grouped[comp] = []
            
            # order_month에서 숫자만 추출하거나 그대로 사용
            month_display = m.order_month.replace('월분', '') 
            
            grouped[comp].append({
                'model': m.model,
                'year': m.order_year,
                'month': month_display, # 화면엔 숫자만 보여줌 (예: 11)
                'lot': str(m.total_quantity)
            })

        return jsonify([{'company': k, 'models': v} for k, v in grouped.items()])

    except Exception as e:
        print(f"Error fetching models: {e}")
        return jsonify({'error': str(e)}), 500

# [API 2] 메인 화면 테이블 데이터 (오늘 날짜 기록)
# [API 2] 메인 화면 테이블 데이터 (누적 수량 계산 로직 추가)
@bp.route('/records', methods=['GET'])
def get_aoi_records():
    try:
        # 프론트엔드에서 보낸 필터 조건 받기
        model = request.args.get('model')
        year = request.args.get('year')
        month = request.args.get('month')
        lot = request.args.get('lot')
        
        # 날짜 범위 검색 파라미터
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # 기본 쿼리 시작
        query = AoiRecord.query

        # 1. 모델/LOT 등 특정 조건이 있는 경우 (필터링 우선)
        if model and year and month and lot:
            query = query.filter_by(
                model=model,
                order_year=year,
                order_month=month,
                lot=lot
            )
        # 2. 날짜 범위가 있는 경우 (기간 조회)
        elif start_date and end_date:
            query = query.filter(
                AoiRecord.date >= start_date,
                AoiRecord.date <= end_date
            )
        # 3. 아무 조건도 없으면 오늘 날짜 기준 (기본값)
        else:
            target_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
            query = query.filter_by(date=target_date)

        # 최신순 정렬하여 목록 가져오기
        records = query.order_by(AoiRecord.id.desc()).all()
        
        # ---------------------------------------------------------
        # [핵심 수정] 각 레코드별 '누적 수량(cumulative_qty)' 계산
        # ---------------------------------------------------------
        results = []
        
        # 중복 쿼리 방지를 위한 캐시 (한 화면에 같은 LOT가 여러 번 나올 경우 대비)
        lot_cache = {} 

        for r in records:
            # 1. 현재 레코드를 딕셔너리로 변환
            r_dict = r.to_dict()
            
            # 2. 고유 주문 키 생성 (모델 + 연 + 월 + LOT)
            lot_key = (r.model, r.order_year, r.order_month, r.lot)
            
            # 3. 캐시에 없으면 DB에서 전체 기간 합계 조회
            if lot_key not in lot_cache:
                total_qty = db.session.query(func.sum(AoiRecord.inspection_qty)).filter_by(
                    model=r.model,
                    order_year=r.order_year,
                    order_month=r.order_month,
                    lot=r.lot
                ).scalar()
                
                # 결과가 없으면(None) 0으로 처리
                lot_cache[lot_key] = total_qty or 0
            
            # 4. 조회한 누적 수량을 데이터에 추가
            r_dict['cumulative_qty'] = lot_cache[lot_key]
            
            results.append(r_dict)

        return jsonify(results)

    except Exception as e:
        print(f"Error fetching records: {e}")
        return jsonify({"error": str(e)}), 500

# [API 3] 기록 생성 (모델 선택 시 행 추가)
@bp.route('/records', methods=['POST'])
def add_aoi_record():
    try:
        data = request.json
        new_record = AoiRecord(
            model=data['model'],
            order_year=data['year'],
            order_month=data['month'],
            lot=str(data['lot']),
            date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
            
            # 초기값 0
            inspection_point=0, inspection_qty=0,
            reverse=0, missing=0, wrong=0, skewed=0, flipped=0,
            unsoldered=0, damaged=0, manhattan=0, short=0,
            cold=0, lifted=0, detached=0, material=0, dip=0,
            total_defect=0, good_qty=0
        )
        db.session.add(new_record)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# [API 4] 기록 수정 (인라인 편집)
@bp.route('/records/<int:record_id>', methods=['PUT'])
def update_aoi_record(record_id):
    try:
        data = request.json
        record = AoiRecord.query.get_or_404(record_id)
        
        # 1. 전달된 필드 업데이트
        editable_fields = [
            'inspection_point', 'inspection_qty', 
            'reverse', 'missing', 'wrong', 'skewed', 'flipped', 'unsoldered',
            'damaged', 'manhattan', 'short', 'cold', 'lifted', 'detached', 'material', 'dip'
        ]
        
        for field in editable_fields:
            if field in data:
                setattr(record, field, int(data[field]))
        
        # 2. 총 불량 및 양품 재계산
        total_defect = (
            record.reverse + record.missing + record.wrong + record.skewed + 
            record.flipped + record.unsoldered + record.damaged + record.manhattan + 
            record.short + record.cold + record.lifted + record.detached + 
            record.material + record.dip
        )
        record.total_defect = total_defect
        
        # 검사수량이 있을 때만 양품 계산
        if record.inspection_qty:
            record.good_qty = record.inspection_qty - total_defect
        else:
            record.good_qty = 0 # 검사수량 미입력 시 0 처리 (혹은 -total_defect)

        db.session.commit()
        return jsonify({'success': True, 'updated_record': record.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
@bp.route('/records/<int:record_id>', methods=['DELETE'])
def delete_aoi_record(record_id):
    try:
        record = AoiRecord.query.get_or_404(record_id)
        db.session.delete(record)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500