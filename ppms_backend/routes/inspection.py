# 파일명: inspection.py
from flask import Blueprint, request, jsonify, send_file, render_template, current_app
from mobile_utils import mobile_render
from models import db, VisionInspection, EsdInspection, Manager
from sqlalchemy import func
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import calendar
import holidays
import hmac
import hashlib

# URL 접두사를 '/api/inspection'으로 분리
bp = Blueprint('inspection', __name__, url_prefix='/api/inspection')
# ==========================================================================
# [0] 화면 연결 (View)
# ==========================================================================
@bp.route('/dashboard', methods=['GET'])
def inspection_dashboard():
    return mobile_render('inspection_dashboard.html', 'mobile_inspection_dashboard.html')

@bp.route('/vision', methods=['GET'])
def vision_view():
    # templates 폴더 안에 있는 'vision_sheet.html'을 보여줍니다.
    return render_template('vision_sheet.html')

# --------------------------------------------------------------------------
# [1] 비젼 장비 점검 API
# --------------------------------------------------------------------------
@bp.route('/holidays', methods=['GET'])
def get_kr_holidays():
    try:
        # 프론트엔드에서 요청한 연도 가져오기 (기본값: 현재 연도)
        year = request.args.get('year', type=int)
        
        # 한국(KR) 공휴일 객체 생성
        kr_holidays = holidays.KR(years=year)
        
        # {"2026-01-01": "New Year's Day", ...} 형태의 딕셔너리로 변환
        holiday_dict = {
            date.strftime('%Y-%m-%d'): name 
            for date, name in kr_holidays.items()
        }
        
        return jsonify(holiday_dict)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# 1. 상태 토글 (저장)
@bp.route('/vision/toggle', methods=['POST'])
def toggle_vision_inspection():
    try:
        data = request.json
        date_str = data.get('date')
        machine_id = data.get('machine_id')
        status = data.get('status') # 'ok', 'ng', 'empty'

        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 기존 기록 조회
        record = VisionInspection.query.filter_by(
            date=target_date, 
            machine_id=machine_id
        ).first()

        if status == 'empty':
            # 초기화(3번 터치) 시 DB에서 삭제
            if record: db.session.delete(record)
        else:
            # 상태 변경 또는 신규 생성
            if record:
                record.status = status
            else:
                new_record = VisionInspection(
                    date=target_date, 
                    machine_id=machine_id, 
                    status=status
                )
                db.session.add(new_record)
        
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# 2. 월간 데이터 조회 (달력 렌더링용)
@bp.route('/vision/monthly', methods=['GET'])
def get_vision_monthly():
    try:
        year = int(request.args.get('year'))
        month = int(request.args.get('month'))
        machine_id = int(request.args.get('machine_id'))

        records = VisionInspection.query.filter(
            func.extract('year', VisionInspection.date) == year,
            func.extract('month', VisionInspection.date) == month,
            VisionInspection.machine_id == machine_id
        ).all()

        # 프론트엔드가 편하게 쓸 수 있도록 { "YYYY-MM-DD": "ok" } 딕셔너리로 변환
        result = {r.date.strftime('%Y-%m-%d'): r.status for r in records}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. PDF 다운로드 (월간 리포트)
@bp.route('/vision/export_pdf', methods=['GET'])
def export_vision_pdf():
    try:
        year = int(request.args.get('year'))
        month = int(request.args.get('month'))
        machine_id = int(request.args.get('machine_id'))

        # PDF 생성 (메모리 버퍼)
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # 헤더 작성
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, f"Vision Inspection Report - {year}.{month:02d}")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, f"Machine: No.{machine_id}")
        p.line(50, height - 80, width - 50, height - 80)

        # 데이터 조회
        records = VisionInspection.query.filter(
            func.extract('year', VisionInspection.date) == year,
            func.extract('month', VisionInspection.date) == month,
            VisionInspection.machine_id == machine_id
        ).all()
        data_map = {r.date.day: r.status for r in records}

        # 표 그리기 (간단 버전)
        y = height - 120
        x_date = 50
        x_status = 150
        
        last_day = calendar.monthrange(year, month)[1]
        
        # 2단 레이아웃 계산
        col_width = 250
        mid_point = 16 

        for d in range(1, last_day + 1):
            # 컬럼 변경 (16일 부터는 오른쪽으로)
            curr_x_date = x_date if d <= mid_point else x_date + col_width
            curr_x_status = x_status if d <= mid_point else x_status + col_width
            curr_y = y - ((d-1) % mid_point) * 20

            status = data_map.get(d, "-")
            mark = "OK" if status == 'ok' else ("NG" if status == 'ng' else "-")
            color = (0, 0, 1) if status == 'ok' else ((1, 0, 0) if status == 'ng' else (0.5, 0.5, 0.5))

            p.setFillColorRGB(0, 0, 0)
            p.drawString(curr_x_date, curr_y, f"{month}/{d:02d}")
            
            p.setFillColorRGB(*color)
            p.drawString(curr_x_status, curr_y, mark)

        p.save()
        buffer.seek(0)
        
        filename = f"Vision_Check_{year}{month:02d}_{machine_id}Ho.pdf"
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    # 0. ESD 화면 연결
@bp.route('/esd', methods=['GET'])
def esd_view():
    return render_template('esd_sheet.html')

# 상태 토글 (저장)
@bp.route('/esd/toggle', methods=['POST'])
def toggle_esd_inspection():
    try:
        data = request.json
        date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date()
        manager_id = data['manager_id']
        target = data['target'] # 'shoes' 또는 'wrist'
        status = data['status'] # 'O', 'X', 'C', 또는 ''

        record = EsdInspection.query.filter_by(date=date_obj, manager_id=manager_id).first()

        if not record:
            record = EsdInspection(date=date_obj, manager_id=manager_id)
            db.session.add(record)

        if target == 'shoes':
            record.shoes_status = status
        else:
            record.wrist_status = status

        # 두 상태가 모두 빈칸('')이 되면 불필요한 데이터이므로 삭제 처리
        if not record.shoes_status and not record.wrist_status:
            db.session.delete(record)

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# 월간 데이터 조회
@bp.route('/esd/monthly', methods=['GET'])
def get_esd_monthly():
    try:
        year = int(request.args.get('year'))
        month = int(request.args.get('month'))
        
        records = EsdInspection.query.filter(
            func.extract('year', EsdInspection.date) == year,
            func.extract('month', EsdInspection.date) == month
        ).all()

        result = []
        for r in records:
            result.append({
                "date": r.date.strftime('%Y-%m-%d'),
                "manager_id": r.manager_id,
                "shoes": r.shoes_status,
                "wrist": r.wrist_status
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================================================
# [QR] 비전/ESD 모바일 QR 토큰 & 제출
# ==========================================================================

def _make_token(payload: str) -> str:
    secret = current_app.config.get('SECRET_KEY', 'ppms-secret')
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]

def _qr_payload(params: dict) -> str:
    # QR 코드에 원래 포함되었던 필수 식별자(s, m)만 추출하여 검증합니다.
    valid_keys = {'s', 'm'}
    return '|'.join(f"{k}={v}" for k, v in sorted(params.items()) if k in valid_keys)

def _verify_token(payload: str, token: str) -> bool:
    return hmac.compare_digest(_make_token(payload), token)


@bp.route('/qr/token', methods=['GET'])
def get_qr_token():
    try:
        params  = {k: v for k, v in request.args.items()}
        payload = _qr_payload(params)
        return jsonify({'token': _make_token(payload)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/qr/submit', methods=['POST'])
def qr_submit():
    try:
        data    = request.json
        token   = data.pop('t', '')
        payload = _qr_payload(data)

        if not _verify_token(payload, token):
            return jsonify({'success': False, 'message': '유효하지 않은 요청입니다.'}), 403

        sheet = data.get('s')
        today = datetime.now().date()
        today_s = today.strftime('%Y-%m-%d')

        # ── 비전 장비 점검 ─────────────────────────────────
        if sheet == 'vision':
            machine_id = int(data.get('m', 1))
            status     = data.get('status', 'ok')   # 'ok' | 'ng'

            record = VisionInspection.query.filter_by(
                date=today, machine_id=machine_id
            ).first()
            if record:
                record.status = status
            else:
                db.session.add(VisionInspection(
                    date=today, machine_id=machine_id, status=status
                ))
            db.session.commit()

        # ── 제전화 점검 ─────────────────────────────────────
        elif sheet == 'esd':
            name   = data.get('name', '').strip()
            status = data.get('status', 'O')        # 'O' | 'X' | 'C'

            if not name:
                return jsonify({'success': False, 'message': '이름을 입력해주세요.'}), 400

            # 이름으로 manager 조회
            manager = Manager.query.filter_by(name=name).first()
            if not manager:
                return jsonify({'success': False, 'message': f"'{name}' 담당자를 찾을 수 없습니다."}), 404

            record = EsdInspection.query.filter_by(
                date=today, manager_id=manager.id
            ).first()
            if not record:
                record = EsdInspection(date=today, manager_id=manager.id)
                db.session.add(record)

            record.shoes_status = status
            record.wrist_status = status
            db.session.commit()

        else:
            return jsonify({'success': False, 'message': '알 수 없는 시트입니다.'}), 400

        return jsonify({'success': True, 'date': today_s})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/managers/list', methods=['GET'])
def get_managers_list():
    """모바일 ESD 폼용 담당자 이름 목록"""
    try:
        managers = Manager.query.order_by(Manager.name).all()
        return jsonify([m.name for m in managers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500