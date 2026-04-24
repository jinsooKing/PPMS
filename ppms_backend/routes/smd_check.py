from flask import Blueprint, request, jsonify, render_template, current_app
from mobile_utils import mobile_render
from models import db, SmdEquipmentCheck, EnvironmentCheck, AcLeakageCheck, SheetPreset
from sqlalchemy import func
from datetime import datetime
import json, hmac, hashlib

bp = Blueprint('smd_check', __name__, url_prefix='/api/smd_check')

# ==========================================================
# [0] 화면 연결
# ==========================================================
@bp.route('/dashboard', methods=['GET'])
def dashboard_view():
    return mobile_render('smd_check_dashboard.html', 'mobile_inspection_dashboard.html')

@bp.route('/smd_daily', methods=['GET'])
def smd_daily_view():
    return render_template('smd_equipment_sheet.html')

@bp.route('/wave_solder', methods=['GET'])
def wave_solder_view():
    return render_template('wave_solder_sheet.html')

@bp.route('/metal_mask', methods=['GET'])
def metal_mask_view():
    return render_template('metal_mask_sheet.html')

@bp.route('/environment', methods=['GET'])
def environment_view():
    return render_template('environment_sheet.html')

@bp.route('/ac_leakage', methods=['GET'])
def ac_leakage_view():
    return render_template('ac_leakage_sheet.html')


# ==========================================================
# [QR] 모바일 점검 페이지 & 토큰 시스템
# ==========================================================

def _make_token(payload: str) -> str:
    """서버 SECRET_KEY로 HMAC 토큰 생성"""
    secret = current_app.config.get('SECRET_KEY', 'ppms-secret')
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]

def _verify_token(payload: str, token: str) -> bool:
    return hmac.compare_digest(_make_token(payload), token)

def _qr_payload(params: dict) -> str:
    """파라미터를 정렬된 문자열로 직렬화 (토큰 일관성 보장)"""
    # QR 코드에 원래 포함되었던 필수 식별자(s, m)만 추출하여 검증합니다.
    valid_keys = {'s', 'm'}
    return '|'.join(f"{k}={v}" for k, v in sorted(params.items()) if k in valid_keys)

# 모바일 페이지 (로그인 불필요)
@bp.route('/mobile', methods=['GET'])
def mobile_check_view():
    return render_template('mobile_check.html')


# QR 토큰 발급 (관리자만 호출, PC에서)
@bp.route('/qr/token', methods=['GET'])
def get_qr_token():
    try:
        params = {k: v for k, v in request.args.items()}
        payload = _qr_payload(params)
        token = _make_token(payload)
        return jsonify({'token': token, 'payload': payload})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 모바일 제출 API (토큰 검증 후 DB 저장)
@bp.route('/qr/submit', methods=['POST'])
def qr_submit():
    try:
        data    = request.json
        token   = data.pop('t', '')
        payload = _qr_payload(data)

        if not _verify_token(payload, token):
            return jsonify({'success': False, 'message': '유효하지 않은 요청입니다.'}), 403

        sheet   = data.get('s')   # 시트 종류
        today   = datetime.now().date()
        today_s = today.strftime('%Y-%m-%d')

        # ── SMD 설비 / Wave Solder / Metal Mask ──────────────
        if sheet in ('smd_daily', 'wave_solder', 'metal_mask'):
            equip    = data.get('e', '')
            freq     = data.get('f', '')        # 'D'|'W'|'M'|'ALL'
            items_raw= data.get('items', [])    # [{no, status}]
            checker  = data.get('checker', '')

            for item in items_raw:
                item_no = int(item['no'])
                status  = item['status']
                record = SmdEquipmentCheck.query.filter_by(
                    sheet_type=sheet, equipment=equip,
                    item_no=item_no, date=today
                ).first()
                if record:
                    if status: record.status = status
                    if checker: record.checker = checker
                else:
                    record = SmdEquipmentCheck(
                        sheet_type=sheet, equipment=equip,
                        item_no=item_no, date=today,
                        status=status, checker=checker, note=''
                    )
                    db.session.add(record)

            # Metal Mask 점검자 (item_no=0)
            if sheet == 'metal_mask' and checker:
                rec = SmdEquipmentCheck.query.filter_by(
                    sheet_type=sheet, equipment=equip, item_no=0, date=today
                ).first()
                if rec:
                    rec.checker = checker
                else:
                    db.session.add(SmdEquipmentCheck(
                        sheet_type=sheet, equipment=equip, item_no=0,
                        date=today, status='', checker=checker, note=''
                    ))
            db.session.commit()

        # ── 환경 점검 ─────────────────────────────────────────
        elif sheet == 'environment':
            check_type = data.get('c')
            slots_raw  = data.get('slots', [])  # [{slot, temperature, humidity, status}]
            for s in slots_raw:
                slot = s.get('slot', '10:00')
                rec = EnvironmentCheck.query.filter_by(
                    check_type=check_type, date=today, time_slot=slot
                ).first()
                if rec:
                    if s.get('temperature') is not None: rec.temperature = s['temperature']
                    if s.get('humidity')    is not None: rec.humidity    = s['humidity']
                    if s.get('status'):                  rec.status      = s['status']
                else:
                    db.session.add(EnvironmentCheck(
                        check_type=check_type, date=today, time_slot=slot,
                        temperature=s.get('temperature'), humidity=s.get('humidity'),
                        status=s.get('status', ''), note=''
                    ))
            db.session.commit()

        # ── AC 누설전류 ───────────────────────────────────────
        elif sheet == 'ac_leakage':
            line      = data.get('l')
            equipment = data.get('e')
            voltage   = data.get('voltage')
            if voltage is not None:
                voltage = float(voltage)
                status  = 'NG' if voltage > 5 else 'OK'
                month   = today.month
                rec = AcLeakageCheck.query.filter_by(
                    year=today.year, month=month, line=line, equipment=equipment
                ).first()
                if rec:
                    rec.voltage = voltage
                    rec.status  = status
                else:
                    db.session.add(AcLeakageCheck(
                        year=today.year, month=month, line=line,
                        equipment=equipment, voltage=voltage, status=status
                    ))
                db.session.commit()

        return jsonify({'success': True, 'date': today_s})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ==========================================================
# [1] SMD 설비 점검 API (smd_daily / wave_solder / metal_mask)
# ==========================================================

# 월간 데이터 조회
@bp.route('/equipment/monthly', methods=['GET'])
def get_equipment_monthly():
    try:
        sheet_type = request.args.get('sheet_type')  # 'smd_daily' | 'wave_solder' | 'metal_mask'
        year       = int(request.args.get('year'))
        month      = int(request.args.get('month'))
        equipment  = request.args.get('equipment', '')  # 특정 설비 필터 (선택)

        q = SmdEquipmentCheck.query.filter(
            SmdEquipmentCheck.sheet_type == sheet_type,
            func.extract('year',  SmdEquipmentCheck.date) == year,
            func.extract('month', SmdEquipmentCheck.date) == month
        )
        if equipment:
            q = q.filter(SmdEquipmentCheck.equipment == equipment)

        records = q.all()
        # { "LOADER_1_2026-03-01": {status, checker, note}, ... }
        result = {}
        for r in records:
            key = f"{r.equipment}_{r.item_no}_{r.date.strftime('%Y-%m-%d')}"
            result[key] = r.to_dict()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 상태 저장 (upsert)
@bp.route('/equipment/toggle', methods=['POST'])
def toggle_equipment():
    try:
        data       = request.json
        sheet_type = data['sheet_type']
        equipment  = data['equipment']
        item_no    = int(data['item_no'])
        date_obj   = datetime.strptime(data['date'], '%Y-%m-%d').date()
        status     = data.get('status', '')
        checker    = data.get('checker', '')
        note       = data.get('note', '')

        record = SmdEquipmentCheck.query.filter_by(
            sheet_type=sheet_type, equipment=equipment,
            item_no=item_no, date=date_obj
        ).first()

        if record:
            record.status  = status
            record.checker = checker
            record.note    = note
        else:
            record = SmdEquipmentCheck(
                sheet_type=sheet_type, equipment=equipment,
                item_no=item_no, date=date_obj,
                status=status, checker=checker, note=note
            )
            db.session.add(record)

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================================================
# [2] 환경 점검 API (fridge / room / dehumid)
# ==========================================================

# 월간 데이터 조회
@bp.route('/environment/monthly', methods=['GET'])
def get_environment_monthly():
    try:
        check_type = request.args.get('check_type')  # 'fridge' | 'room' | 'dehumid'
        year       = int(request.args.get('year'))
        month      = int(request.args.get('month'))

        records = EnvironmentCheck.query.filter(
            EnvironmentCheck.check_type == check_type,
            func.extract('year',  EnvironmentCheck.date) == year,
            func.extract('month', EnvironmentCheck.date) == month
        ).all()

        # { "2026-03-01_10:00": {temperature, humidity, status, note}, ... }
        result = {}
        for r in records:
            key = f"{r.date.strftime('%Y-%m-%d')}_{r.time_slot}"
            result[key] = r.to_dict()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 환경 점검 저장
@bp.route('/environment/save', methods=['POST'])
def save_environment():
    try:
        data       = request.json
        check_type = data['check_type']
        date_obj   = datetime.strptime(data['date'], '%Y-%m-%d').date()
        time_slot  = data.get('time_slot', '10:00')
        temperature = data.get('temperature')
        humidity    = data.get('humidity')
        status      = data.get('status', '')
        note        = data.get('note', '')

        record = EnvironmentCheck.query.filter_by(
            check_type=check_type, date=date_obj, time_slot=time_slot
        ).first()

        if record:
            record.temperature = temperature
            record.humidity    = humidity
            record.status      = status
            record.note        = note
        else:
            record = EnvironmentCheck(
                check_type=check_type, date=date_obj, time_slot=time_slot,
                temperature=temperature, humidity=humidity,
                status=status, note=note
            )
            db.session.add(record)

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================================================
# [3] AC 누설전류 API
# ==========================================================

# 연간 데이터 조회
@bp.route('/ac_leakage/yearly', methods=['GET'])
def get_ac_leakage_yearly():
    try:
        year = int(request.args.get('year'))
        records = AcLeakageCheck.query.filter_by(year=year).all()

        # { "A_LOADER_3": {voltage, status}, ... }
        result = {}
        for r in records:
            key = f"{r.line}_{r.equipment}_{r.month}"
            result[key] = r.to_dict()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# AC 누설전류 저장
@bp.route('/ac_leakage/save', methods=['POST'])
def save_ac_leakage():
    try:
        data      = request.json
        year      = int(data['year'])
        month     = int(data['month'])
        line      = data['line']
        equipment = data['equipment']
        voltage   = data.get('voltage')
        status    = data.get('status', '')

        record = AcLeakageCheck.query.filter_by(
            year=year, month=month, line=line, equipment=equipment
        ).first()

        if record:
            record.voltage = voltage
            record.status  = status
        else:
            record = AcLeakageCheck(
                year=year, month=month, line=line,
                equipment=equipment, voltage=voltage, status=status
            )
            db.session.add(record)

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================================
# [4] 프리셋 API (관리자 설정값 저장/조회)
# ==========================================================

@bp.route('/preset/<sheet_type>', methods=['GET'])
def get_preset(sheet_type):
    try:
        record = SheetPreset.query.filter_by(sheet_type=sheet_type).first()
        if not record:
            return jsonify({'sheet_type': sheet_type, 'preset_data': {}})
        return jsonify(record.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/preset/<sheet_type>', methods=['POST'])
def save_preset(sheet_type):
    try:
        data = request.json.get('preset_data', {})
        record = SheetPreset.query.filter_by(sheet_type=sheet_type).first()
        if record:
            record.preset_data = json.dumps(data, ensure_ascii=False)
        else:
            record = SheetPreset(
                sheet_type=sheet_type,
                preset_data=json.dumps(data, ensure_ascii=False)
            )
            db.session.add(record)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500