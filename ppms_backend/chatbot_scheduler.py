"""
PPMS KakaoTalk 점검 알림 스케줄러
chatbot_scheduler.py  (프로젝트 루트에 배치)

[필수 설치]
pip install apscheduler holidays

[app.py 수정 내용]
from chatbot_scheduler import create_scheduler

def create_app():
    ...
    app.register_blueprint(chatbot_bp)
    create_scheduler(app)
    ...
    return app

[카카오 알림 푸시 활성화]
KAKAO_ADMIN_KEY, KAKAO_CHANNEL_PUBLIC_ID 에
실제 값 입력 시 자동 활성화.
비어있으면 로그만 출력하고 푸시는 생략.
"""

import requests
import logging
import calendar
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────────
KAKAO_ADMIN_KEY         = "78aeaf6c3741e2bb7dd98c46593cfe00"
KAKAO_CHANNEL_PUBLIC_ID = "_hxgEMX"

try:
    import holidays as _holidays
    KR_HOLIDAYS = _holidays.KR()
except ImportError:
    KR_HOLIDAYS = {}
    logger.warning("[Scheduler] 'holidays' 패키지 미설치 - 공휴일 체크 비활성화")


# ─────────────────────────────────────────────────────────────────
# 공휴일 / 평일 판단
# ─────────────────────────────────────────────────────────────────
def _is_holiday(d: date) -> bool:
    return d.weekday() >= 5 or d in KR_HOLIDAYS

def _is_last_weekday_of_week(d: date) -> bool:
    if _is_holiday(d):
        return False
    next_d = d + timedelta(days=1)
    while next_d.weekday() != 0:
        if not _is_holiday(next_d):
            return False
        next_d += timedelta(days=1)
    return True

def _is_last_weekday_of_month(d: date) -> bool:
    if _is_holiday(d):
        return False
    last_day = calendar.monthrange(d.year, d.month)[1]
    next_d   = d + timedelta(days=1)
    while next_d.day <= last_day:
        if not _is_holiday(next_d):
            return False
        next_d += timedelta(days=1)
    return True


# ─────────────────────────────────────────────────────────────────
# 카카오 채널 푸시 메시지 발송
# ─────────────────────────────────────────────────────────────────
def _kakao_push(text: str):
    if not KAKAO_ADMIN_KEY or not KAKAO_CHANNEL_PUBLIC_ID:
        logger.info(f"[Scheduler] 푸시 비활성화 (키 미설정)\n발송 예정 메시지:\n{text}")
        return

    url     = f"https://kapi.kakao.com/v1/api/talk/channels/{KAKAO_CHANNEL_PUBLIC_ID}/message"
    headers = {
        "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
        "Content-Type":  "application/json; charset=UTF-8"
    }
    try:
        resp = requests.post(
            url, headers=headers,
            json={"template_object": {"object_type": "text", "text": text, "link": {}}},
            timeout=10
        )
        if resp.status_code == 200:
            logger.info("[Scheduler] 카카오 알림 발송 성공")
        else:
            logger.error(f"[Scheduler] 발송 실패: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"[Scheduler] 발송 오류: {e}")


# ─────────────────────────────────────────────────────────────────
# 점검 미완료 항목 조회
# ─────────────────────────────────────────────────────────────────
def _check_daily(app, target: date):
    from models import (VisionInspection, SmdEquipmentCheck,
                        EnvironmentCheck, EsdInspection, Manager)
    from extensions import db

    incomplete = []
    with app.app_context():

        # 비전 점검
        for mid in [1, 2]:
            if not VisionInspection.query.filter_by(
                date=target, machine_id=mid
            ).first():
                incomplete.append(f"비전검사 {mid}호기")

        # SMD 설비 점검 (smd_daily) - 단일 항목
        done_count = db.session.query(SmdEquipmentCheck.id).filter(
            SmdEquipmentCheck.sheet_type == 'smd_daily',
            SmdEquipmentCheck.date       == target,
            SmdEquipmentCheck.status     != ''
        ).count()
        if done_count == 0:
            incomplete.append("SMD 일일 설비 점검")

        # Wave Solder 일일 점검 (D항목)
        WAVE_D_ITEMS = [1, 2, 4, 5, 6, 8, 9, 12]
        done_wave = {
            r.item_no for r in SmdEquipmentCheck.query.filter(
                SmdEquipmentCheck.sheet_type == 'wave_solder',
                SmdEquipmentCheck.date       == target,
                SmdEquipmentCheck.status     != ''
            ).all()
        }
        missing_wave_d = [no for no in WAVE_D_ITEMS if no not in done_wave]
        if missing_wave_d:
            incomplete.append("Wave Solder 일일 점검")

        # 환경 점검
        done_env = {e[0] for e in db.session.query(EnvironmentCheck.check_type).filter(
            EnvironmentCheck.date == target
        ).distinct().all()}
        for ct, label in [
            ('fridge',  '냉장고 온도'),
            ('room',    '실내 온습도'),
            ('dehumid', '제습함 온습도')
        ]:
            if ct not in done_env:
                incomplete.append(f"환경점검 - {label}")

        # ESD(제전화) 점검 - 담당자별
        all_managers = Manager.query.order_by(Manager.name).all()
        done_mgr_ids = {e[0] for e in db.session.query(EsdInspection.manager_id).filter(
            EsdInspection.date == target
        ).distinct().all()}
        for mgr in all_managers:
            if mgr.id not in done_mgr_ids:
                incomplete.append(f"제전화 점검 - {mgr.name}")

    return incomplete


# SMD 설비 점검 항목 정의 (프론트엔드 EQUIPMENTS 객체와 동일)
SMD_ITEMS = {
    'Loader':            {6:'W', 7:'M', 8:'M', 9:'M'},
    'Screen Printer':    {7:'W', 8:'W', 9:'W', 10:'W', 11:'M', 12:'M', 13:'M'},
    'SPI':               {7:'W', 8:'M', 9:'M'},
    'Multi Mounter 471': {6:'W', 7:'W', 8:'W', 9:'W', 10:'W', 11:'W', 12:'W', 13:'M', 14:'M', 15:'M'},
    'Chip Mounter 411':  {6:'W', 7:'W', 8:'W', 9:'W', 10:'W', 11:'W', 12:'M', 13:'M', 14:'M'},
    'Multi Mounter 421': {6:'W', 7:'W', 8:'W', 9:'W', 10:'W', 11:'W', 12:'W', 13:'M', 14:'M', 15:'M'},
    'Multi Mounter':     {6:'W', 7:'W', 8:'W', 9:'W', 10:'W', 11:'W', 12:'W', 13:'M', 14:'M', 15:'M'},
    'Reflow':            {10:'W', 11:'W', 12:'W', 13:'M', 14:'M', 15:'M'},
    'Unloader':          {6:'W', 7:'M', 8:'M', 9:'M'},
}


# Wave Solder 주간 항목
WAVE_W_ITEMS = [3, 7, 10, 11, 13, 14]

# Metal Mask 주간 항목 (item_no 1~4)
METAL_MASK_W_ITEMS = [1, 2, 3, 4]


def _check_weekly(app, target: date):
    from models import SmdEquipmentCheck
    from extensions import db

    incomplete = []
    week_start = target - timedelta(days=target.weekday())

    with app.app_context():

        # SMD 설비 주간 점검 (W항목)
        for equipment, item_map in SMD_ITEMS.items():
            w_items = [no for no, freq in item_map.items() if freq == 'W']
            if not w_items:
                continue

            done_items = {
                r.item_no for r in SmdEquipmentCheck.query.filter(
                    SmdEquipmentCheck.equipment  == equipment,
                    SmdEquipmentCheck.sheet_type == 'smd_daily',
                    SmdEquipmentCheck.date       >= week_start,
                    SmdEquipmentCheck.date       <= target,
                    SmdEquipmentCheck.status     != ''
                ).all()
            }
            missing = [no for no in w_items if no not in done_items]
            if missing:
                incomplete.append(f"SMD 주간점검 - {equipment} ({len(missing)}항목)")

        # Wave Solder 주간 점검 (W항목)
        done_wave_w = {
            r.item_no for r in SmdEquipmentCheck.query.filter(
                SmdEquipmentCheck.sheet_type == 'wave_solder',
                SmdEquipmentCheck.date       >= week_start,
                SmdEquipmentCheck.date       <= target,
                SmdEquipmentCheck.status     != ''
            ).all()
        }
        missing_wave_w = [no for no in WAVE_W_ITEMS if no not in done_wave_w]
        if missing_wave_w:
            incomplete.append(f"Wave Solder 주간점검 ({len(missing_wave_w)}항목)")

        # Metal Mask 주간 점검 (item_no 1~4, 이번 주 기록 확인)
        done_metal = {
            r.item_no for r in SmdEquipmentCheck.query.filter(
                SmdEquipmentCheck.sheet_type == 'metal_mask',
                SmdEquipmentCheck.date       >= week_start,
                SmdEquipmentCheck.date       <= target,
                SmdEquipmentCheck.status     != ''
            ).all()
        }
        missing_metal = [no for no in METAL_MASK_W_ITEMS if no not in done_metal]
        if missing_metal:
            incomplete.append(f"Metal Mask 주간점검 ({len(missing_metal)}항목)")

    return incomplete


def _check_monthly(app, target: date):
    from models import AcLeakageCheck, SmdEquipmentCheck
    from extensions import db
    import calendar as _cal

    incomplete  = []
    year, month = target.year, target.month
    prev_month  = month - 1 if month > 1 else 12
    prev_year   = year  if month > 1 else year - 1

    # 이번 달 1일
    month_start = target.replace(day=1)

    with app.app_context():
        # AC 누설전류 점검
        all_ac = {(r[0], r[1]) for r in db.session.query(
            AcLeakageCheck.line, AcLeakageCheck.equipment
        ).filter(
            AcLeakageCheck.year  == prev_year,
            AcLeakageCheck.month == prev_month
        ).all()}

        done_ac = {(r[0], r[1]) for r in db.session.query(
            AcLeakageCheck.line, AcLeakageCheck.equipment
        ).filter(
            AcLeakageCheck.year    == year,
            AcLeakageCheck.month   == month,
            AcLeakageCheck.voltage != None
        ).all()}

        for line, equip in sorted(all_ac - done_ac):
            incomplete.append(f"AC 누설 - {line} {equip}")

        # SMD 설비 월간 점검 (freq=M 항목)
        for equipment, item_map in SMD_ITEMS.items():
            m_items = [no for no, freq in item_map.items() if freq == 'M']
            if not m_items:
                continue

            done_items = {
                r.item_no for r in SmdEquipmentCheck.query.filter(
                    SmdEquipmentCheck.equipment  == equipment,
                    SmdEquipmentCheck.sheet_type == 'smd_daily',
                    SmdEquipmentCheck.date       >= month_start,
                    SmdEquipmentCheck.date       <= target,
                    SmdEquipmentCheck.status     != ''
                ).all()
            }

            missing = [no for no in m_items if no not in done_items]
            if missing:
                incomplete.append(f"SMD 월간점검 - {equipment} ({len(missing)}항목)")

    return incomplete


# ─────────────────────────────────────────────────────────────────
# 스케줄러 실행 함수 (매일 16:00)
# ─────────────────────────────────────────────────────────────────
def _run_daily_check(app):
    today = date.today()

    if _is_holiday(today):
        logger.info(f"[Scheduler] {today} 공휴일/주말 - 알림 생략")
        return

    # 일간 점검 알림
    daily_items = _check_daily(app, today)
    if daily_items:
        items_str = '\n'.join(f"  - {i}" for i in daily_items)
        _kakao_push(
            f"[PPMS 일간 점검 미완료]\n"
            f"{today} 오후 4시 기준\n\n"
            f"[ 미완료 항목 ] ({len(daily_items)}건)\n"
            f"{items_str}"
        )
        logger.info(f"[Scheduler] 일간 알림: {len(daily_items)}건")
    else:
        logger.info("[Scheduler] 일간 점검 완료 - 알림 없음")

    # 주간 점검 알림
    if _is_last_weekday_of_week(today):
        weekly_items = _check_weekly(app, today)
        if weekly_items:
            items_str = '\n'.join(f"  - {i}" for i in weekly_items)
            _kakao_push(
                f"[PPMS 주간 점검 미완료]\n"
                f"이번 주 마지막 평일 ({today})\n\n"
                f"[ 미완료 항목 ] ({len(weekly_items)}건)\n"
                f"{items_str}"
            )
            logger.info(f"[Scheduler] 주간 알림: {len(weekly_items)}건")

    # 월간 점검 알림
    if _is_last_weekday_of_month(today):
        monthly_items = _check_monthly(app, today)
        if monthly_items:
            items_str = '\n'.join(f"  - {i}" for i in monthly_items)
            _kakao_push(
                f"[PPMS 월간 점검 미완료]\n"
                f"이번 달 마지막 평일 ({today})\n\n"
                f"[ 미완료 항목 ] ({len(monthly_items)}건)\n"
                f"{items_str}"
            )
            logger.info(f"[Scheduler] 월간 알림: {len(monthly_items)}건")


# ─────────────────────────────────────────────────────────────────
# 스케줄러 초기화
# ─────────────────────────────────────────────────────────────────
def create_scheduler(app):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("[Scheduler] 'apscheduler' 미설치 - 스케줄러 비활성화")
        return None

    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(
        func=lambda: _run_daily_check(app),
        trigger='cron',
        hour=16, minute=0,
        id='ppms_daily_check',
        replace_existing=True
    )
    scheduler.start()
    logger.info("[Scheduler] 시작 완료 - 매일 평일 16:00 실행")
    return scheduler