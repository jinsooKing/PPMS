// 전역 로그인 상태 변수
window.currentUser = {
    isLoggedIn: false,
    username: null,
    role: null
};

/**
 * [보안 가드] 페이지 로드 시 로그인 상태를 확인하는 함수
 * @param {string} requiredRole - (선택) 'admin' 등 특정 역할이 필요한 경우
 */
async function checkLoginStatus(requiredRole = null) {
    
    // 1. (예외) 이미 login.html 페이지라면 확인 중단
    if (window.location.pathname.endsWith('login.html')) {
        return; 
    }

    try {
        // 2. 백엔드에 '내 세션 정보 줘'라고 요청
        const response = await fetch('http://127.0.0.1:5000/api/auth/check_session', {
            credentials: 'include' // 세션 쿠키를 함께 보냄
        });

        if (response.ok) {
            // 3. (로그인 성공)
            const user = await response.json();
            window.currentUser.isLoggedIn = user.is_logged_in;
            window.currentUser.username = user.username;
            window.currentUser.role = user.role;
            
            // 4. (관리자 페이지 접근 제어)
            // 'admin' 역할이 필요한데, 현재 사용자가 'admin'이 아닐 경우
            if (requiredRole === 'admin' && user.role !== 'admin') {
                alert('접근 권한이 없습니다.');
                window.location.href = 'index.html'; // 홈으로 쫓아내기
            }
            
            // (로그인 상태이고 권한도 문제 없으면 페이지 로드 계속)

        } else {
            // 4. (로그인 실패 / 401 에러)
            // 'login.html'로 쫓아내기
            window.location.href = 'login.html';
        }
    } catch (error) {
        // 5. (백엔드 서버 꺼짐 등)
        console.error('세션 확인 API 통신 오류:', error);
        alert('서버에 연결할 수 없습니다. login.html로 이동합니다.');
        window.location.href = 'login.html';
    }
}

/**
 * [로그아웃] 'id="logout-btn"' 버튼에 로그아웃 기능을 연결하는 함수
 */
function setupLogoutButton() {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (!confirm('로그아웃 하시겠습니까?')) {
                return;
            }
            
            localStorage.removeItem('ppms_user_role');

            try {
                await fetch('http://127.0.0.1:5000/api/auth/logout', {
                    method: 'POST',
                    credentials: 'include'
                });
                alert('로그아웃 되었습니다.');
                window.location.href = 'login.html'; // 로그인 페이지로 이동
            } catch (error) {
                console.error('로그아웃 실패:', error);
                alert('로그아웃 중 오류가 발생했습니다.');
            }
        });
    }
}