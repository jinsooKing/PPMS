/**
 * PPMS Logo Library (logo.js)
 * - 기능: SVG 필터 자동 주입, 로고 렌더링, GSAP 글리치 애니메이션 적용
 * - 의존성: GSAP (TweenMax/TimelineMax)
 */

const PPMS_LOGO = {
    // 1. 로고의 모양을 결정하는 SVG Path 데이터 (production.html 원본 데이터)
    logoContent: `
        <g transform="translate(0.000000,240.000000) scale(0.100000,-0.100000)" stroke="none">
            <path d="M978 2385 c-184 -31 -309 -94 -433 -219 -143 -144 -199 -279 -198 -481 1 -235 87 -444 246 -592 271 -253 686 -282 997 -70 54 37 151 127 193 181 26 32 16 27 -66 -37 -189 -148 -291 -189 -467 -189 -275 1 -472 113 -575 327 -128 265 -86 586 101 773 99 99 243 150 389 138 172 -14 293 -86 355 -208 38 -77 41 -167 9 -253 -38 -102 -159 -206 -276 -240 l-23 -6 0 188 c0 134 4 193 12 201 7 7 31 12 55 12 32 0 43 4 43 15 0 13 -35 15 -251 15 -196 0 -250 -3 -247 -12 3 -7 24 -14 49 -16 24 -2 47 -9 51 -15 14 -21 10 -661 -4 -675 -7 -7 -31 -12 -55 -12 -32 0 -43 -4 -43 -15 0 -13 34 -15 250 -15 216 0 250 2 250 15 0 11 -12 15 -45 15 -59 0 -65 14 -65 139 l0 100 58 6 c109 11 184 26 236 46 183 68 285 273 230 460 -94 317 -404 487 -776 424z"/>
            <path d="M1991 638 c-60 -130 -103 -211 -120 -225 l-26 -22 73 -1 c39 0 72 3 72 6 0 3 -9 13 -19 22 -19 16 -19 19 -4 55 l15 37 87 0 c84 0 88 -1 99 -25 18 -38 15 -63 -8 -70 -45 -14 -15 -25 70 -25 50 0 90 3 90 6 0 3 -10 16 -21 28 -12 12 -61 109 -109 216 -48 107 -92 196 -97 197 -5 2 -52 -88 -102 -199z m113 -9 c14 -33 26 -62 26 -65 0 -2 -27 -4 -61 -4 -33 0 -59 4 -57 8 2 4 14 33 27 65 14 31 28 57 32 57 3 0 18 -27 33 -61z"/>
            <path d="M0 811 c0 -5 11 -16 25 -25 25 -16 25 -17 25 -179 0 -89 -4 -167 -8 -173 -4 -6 -15 -13 -24 -17 -43 -16 -13 -27 72 -27 50 0 90 4 90 9 0 5 -11 16 -25 25 -24 16 -26 22 -23 79 l3 62 85 5 c131 9 180 44 180 130 0 53 -22 84 -76 106 -38 16 -324 20 -324 5z m264 -35 c58 -24 69 -107 18 -146 -19 -15 -40 -20 -88 -20 l-64 0 0 78 c0 47 5 83 12 90 16 16 81 15 122 -2z"/>
            <path d="M440 810 c0 -6 11 -15 25 -20 l25 -10 0 -175 0 -175 -25 -10 c-50 -19 -26 -30 65 -30 50 0 90 4 90 9 0 5 -10 15 -22 23 -19 13 -23 26 -26 92 l-4 76 96 0 96 0 0 -75 c0 -68 -2 -76 -25 -91 -14 -9 -25 -20 -25 -25 0 -5 41 -9 90 -9 50 0 90 4 90 9 0 5 -11 16 -25 25 -25 16 -25 17 -25 181 0 164 0 165 25 181 14 9 25 20 25 25 0 5 -40 9 -90 9 -49 0 -90 -4 -90 -9 0 -5 11 -16 25 -25 23 -15 25 -23 25 -86 l0 -70 -96 0 -96 0 4 72 c3 60 7 73 26 86 12 8 22 18 22 23 0 5 -40 9 -90 9 -55 0 -90 -4 -90 -10z"/>
            <path d="M940 810 c0 -6 11 -15 25 -20 l25 -10 0 -167 c0 -93 -4 -173 -8 -179 -4 -6 -15 -13 -24 -17 -43 -16 -13 -27 72 -27 50 0 90 4 90 9 0 5 -11 16 -25 25 -25 16 -25 17 -25 181 0 164 0 165 25 181 14 9 25 20 25 25 0 5 -40 9 -90 9 -55 0 -90 -4 -90 -10z"/>
            <path d="M1170 810 c0 -6 8 -14 18 -17 9 -4 20 -11 24 -17 4 -6 8 -83 8 -171 0 -88 -4 -165 -8 -171 -4 -6 -15 -13 -24 -17 -10 -3 -18 -11 -18 -17 0 -6 66 -10 190 -10 l190 0 6 28 c3 15 10 42 15 61 15 60 -7 69 -36 15 -21 -39 -51 -59 -106 -69 -44 -8 -115 10 -123 31 -3 9 -6 81 -6 160 0 142 1 145 25 168 14 13 25 26 25 30 0 3 -40 6 -90 6 -55 0 -90 -4 -90 -10z"/>
            <path d="M1630 811 c0 -5 11 -16 25 -25 25 -16 25 -17 25 -181 0 -164 0 -165 -25 -181 -14 -9 -25 -20 -25 -25 0 -5 38 -9 85 -9 84 0 104 9 65 30 -19 10 -20 21 -20 185 0 164 1 175 20 185 39 21 19 30 -65 30 -47 0 -85 -4 -85 -9z"/>
            <path d="M532 273 c3 -17 40 -18 591 -21 582 -2 587 -2 587 18 0 20 -6 20 -591 20 -557 0 -590 -1 -587 -17z"/>
            <path d="M530 180 c0 -5 14 -10 30 -10 l30 0 0 -80 c0 -64 3 -80 15 -80 12 0 15 16 15 80 l0 80 30 0 c17 0 30 5 30 10 0 6 -32 10 -75 10 -43 0 -75 -4 -75 -10z"/>
            <path d="M700 100 l0 -90 65 0 c37 0 65 4 65 10 0 6 -25 10 -55 10 -54 0 -55 0 -55 30 0 29 1 30 50 30 28 0 50 5 50 10 0 6 -22 10 -50 10 -49 0 -50 1 -50 30 0 30 1 30 55 30 30 0 55 5 55 10 0 6 -28 10 -65 10 l-65 0 0 -90z"/>
            <path d="M850 101 l0 -91 60 0 c33 0 60 4 60 10 0 6 -20 10 -45 10 l-44 0 -3 77 c-2 50 -7 78 -15 81 -10 3 -13 -19 -13 -87z"/>
            <path d="M990 100 l0 -90 65 0 c37 0 65 4 65 10 0 6 -22 10 -50 10 -49 0 -50 1 -50 30 0 29 2 30 44 30 25 0 48 5 51 10 4 6 -13 10 -44 10 -50 0 -51 1 -51 30 0 29 1 30 50 30 28 0 50 5 50 10 0 6 -28 10 -65 10 l-65 0 0 -90z"/>
            <path d="M1161 164 c-32 -41 -28 -98 9 -136 26 -25 36 -29 62 -24 36 7 68 32 68 53 0 20 -16 16 -32 -8 -16 -24 -59 -29 -83 -9 -20 17 -20 94 1 114 20 20 58 21 78 1 16 -17 36 -20 36 -6 0 19 -45 41 -81 41 -29 0 -43 -6 -58 -26z"/>
            <path d="M1351 171 c-48 -48 -29 -143 33 -164 87 -29 148 89 83 161 -27 29 -89 30 -116 3z m103 -23 c47 -66 -19 -154 -79 -106 -29 23 -34 71 -9 106 20 30 68 30 88 0z"/>
            <path d="M1520 100 c0 -53 4 -90 10 -90 6 0 10 25 10 55 0 30 4 55 8 55 5 0 16 -25 26 -56 22 -71 43 -70 71 6 l20 55 3 -58 c2 -40 7 -57 15 -54 18 6 17 172 -2 172 -12 0 -22 -20 -63 -125 -9 -23 -12 -19 -39 53 -42 107 -59 104 -59 -13z"/>
        </g>
    `,

    // 2. SVG 필터(투명 도구)를 body에 주입하는 함수
    injectFilter: function() {
        // 중복 주입 방지
        if (document.getElementById('logo-filter-def')) return; 
        
        const div = document.createElement('div');
        // production.html에 있는 filter 정의와 동일
        div.innerHTML = `
            <svg style="position: absolute; width: 0; height: 0;" width="0" height="0" version="1.1" xmlns="http://www.w3.org/2000/svg" id="logo-filter-def" class="svg-sprite">
                <defs>
                    <filter id="filter">
                        <feTurbulence type="fractalNoise" baseFrequency="0.01 0.004" numOctaves="1" result="warp" seed="1"></feTurbulence>
                        <feDisplacementMap xChannelSelector="R" yChannelSelector="G" scale="30" in="SourceGraphic" in2="warp"></feDisplacementMap>
                    </filter>
                </defs>
            </svg>
        `;
        document.body.insertBefore(div.firstElementChild, document.body.firstChild);
    },

    // 3. HTML 내의 'placeholder'를 찾아 실제 로고 SVG로 교체하는 함수
    renderLogo: function() {
        const placeholders = document.querySelectorAll('.ppms-logo-placeholder');
        
        placeholders.forEach(el => {
            // 이미 렌더링된 경우 건너뜀
            if(el.querySelector('svg')) return;

            // 클래스 추가 (CSS 스타일 및 애니메이션 타겟팅 용도)
            el.classList.add('header-logo-wrapper', 'btn-glitch');
            
            // SVG 주입
            el.innerHTML = `
                <svg class="header-logo" version="1.0" xmlns="http://www.w3.org/2000/svg"
                     width="233.000000pt" height="240.000000pt" viewBox="0 0 233.000000 240.000000"
                     preserveAspectRatio="xMidYMid meet">
                    ${this.logoContent}
                </svg>
            `;
        });
    },

    // 4. GSAP 애니메이션 초기화 함수
    initAnimation: function() {
        const filter = document.querySelector('#logo-filter-def');
        if (!filter) return;

        const turb = filter.querySelector('#filter feTurbulence');
        const glitchElements = document.querySelectorAll('.btn-glitch');
        
        // 애니메이션 변수
        let turbVal = { val: 0.000001 };
        let turbValX = { val: 0.000001 };
        
        // Timeline 생성
        let timeline = new TimelineMax({
            repeat: -1, 
            repeatDelay: 2, 
            paused: true,
            onUpdate: function () { 
                turb.setAttribute('baseFrequency', turbVal.val + ' ' + turbValX.val); 
            }
        });
        
        // 애니메이션 시퀀스 (일그러짐 효과)
        timeline.to(turbValX, 0.1, { val: 0.5 })
                .to(turbVal, 0.1, { val: 0.02 })
                .set(turbValX, { val: 0.000001 })
                .set(turbVal, { val: 0.000001 })
                .to(turbValX, 0.2, { val: 0.4 }, 0.4)
                .to(turbVal, 0.2, { val: 0.002 }, 0.4)
                .set(turbValX, { val: 0.000001 })
                .set(turbVal, { val: 0.000001 });

        // 마우스 이벤트 바인딩
        glitchElements.forEach(el => {
            el.addEventListener('mouseenter', function() { 
                this.classList.add('btn-glitch-active'); 
                timeline.restart(); 
            });
            el.addEventListener('mouseleave', function() { 
                this.classList.remove('btn-glitch-active'); 
                timeline.pause(); 
                gsap.set(turbVal, {val:0}); 
                gsap.set(turbValX, {val:0}); 
                turb.setAttribute('baseFrequency', '0.000001 0.000001'); 
            });
        });
    },

    // 5. 메인 초기화 함수 (외부에서 호출)
    init: function() {
        this.injectFilter();
        this.renderLogo();
        
        // GSAP가 로드되었는지 확인 후 애니메이션 실행
        if (window.gsap || window.TimelineMax) {
            this.initAnimation();
        } else {
            // GSAP가 늦게 로드될 경우를 대비해 0.1초 뒤 재시도
            setTimeout(() => this.initAnimation(), 100);
        }
    }
};

// 페이지 로드 시 자동 실행
document.addEventListener('DOMContentLoaded', () => {
    PPMS_LOGO.init();
});