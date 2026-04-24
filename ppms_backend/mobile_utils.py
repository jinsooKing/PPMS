"""
mobile_utils.py
모바일 User-Agent 감지 공통 유틸리티

위치: 프로젝트 루트 (app.py 와 같은 디렉터리)

사용법:
    from mobile_utils import is_mobile, mobile_render

    @bp.route('/view')
    def view():
        return mobile_render('page.html', 'mobile_page.html')

routes/ 서브폴더 안의 블루프린트 파일에서도 동일하게 import 가능합니다.
app.py 의 sys.path 처리로 별도 작업 불필요.
"""

import sys
import os

# routes/ 안에서 직접 import 할 때를 대비한 경로 보장
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from flask import request, render_template


# ──────────────────────────────────────────────────────
# 모바일 User-Agent 키워드
# ──────────────────────────────────────────────────────
_MOBILE_UA_KEYWORDS = [
    'iphone', 'android', 'mobile', 'ipad',
    'blackberry', 'windows phone', 'opera mini',
    'silk', 'kindle',
]


def is_mobile(req=None) -> bool:
    """
    현재 요청이 모바일 기기인지 판별한다.

    우선순위:
    1. ?force_desktop=1  →  항상 데스크탑 반환  (개발·테스트용)
    2. ?force_mobile=1   →  항상 모바일 반환    (개발·테스트용)
    3. User-Agent 키워드 매칭

    Args:
        req: Flask request 객체 (생략 시 현재 request 사용)

    Returns:
        bool: True → 모바일, False → 데스크탑
    """
    req = req or request

    # 강제 오버라이드 (쿼리 파라미터)
    if req.args.get('force_desktop'):
        return False
    if req.args.get('force_mobile'):
        return True

    ua = req.headers.get('User-Agent', '').lower()
    return any(kw in ua for kw in _MOBILE_UA_KEYWORDS)


def mobile_render(desktop_template: str, mobile_template: str, **ctx):
    """
    모바일 여부에 따라 적절한 템플릿을 렌더링한다.

    Args:
        desktop_template : 데스크탑용 HTML 템플릿 파일명
        mobile_template  : 모바일용  HTML 템플릿 파일명
        **ctx            : render_template 에 전달할 컨텍스트 변수

    Example:
        return mobile_render('production.html', 'mobile_production.html')
    """
    template = mobile_template if is_mobile() else desktop_template
    return render_template(template, **ctx)
