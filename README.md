# 온누리몰 모니터링 및 매출 통계 메일 자동 발송

온누리 계열 몰을 자동으로 점검하고, 드림몰 Admin 통계와 매출 통계를 메일로 보내는 저장소입니다. 두 프로그램이 들어 있고, 각각 별도 GitHub Actions 워크플로로 실행됩니다.

| 프로그램 | 위치 | 하는 일 | 워크플로 | 자세한 내용 |
|----------|------|---------|----------|-------------|
| UI 모니터링 | 루트 (`main.py`) | Playwright로 몰의 PC·모바일 화면을 열어 9개 시나리오(메인, 팝업, 검색, 카테고리 등)를 점검하고 결과를 두레이로 발송 | `schedule.yml` | [모니터링_가이드.html](모니터링_가이드.html) |
| Admin 통계 / 매출 통계 | `admin_stat/` | Selenium으로 Admin에 로그인해 일일 통계와 주간·월간 매출 통계를 수집하고 메일·카카오톡으로 발송 | `admin_stat.yml` | [매출통계_발송가이드.html](매출통계_발송가이드.html) |

설치, 설정(`config.yaml`, `.env`, Secrets), 실행 옵션, 문제 해결은 각 가이드에 정리되어 있습니다. HTML 파일은 저장소를 받은 뒤 브라우저로 열어서 보면 됩니다.

## 빠른 실행

```bash
# UI 모니터링
pip install -r requirements.txt
playwright install chromium
python main.py

# Admin 통계 / 매출 통계
cd admin_stat
pip install -r requirements.txt
python main.py --sales-weekly
```

두 프로그램 모두 계정 정보를 `.env`(로컬)나 GitHub Secrets에 넣어야 동작합니다. 필요한 키는 각 가이드의 환경 변수 항목을 참고하세요.

## 구조

```
UI_test/
├── main.py                  # 진입점: 설정 로드, 몰/플랫폼별 실행, 리포트 저장, 두레이 발송
├── config.yaml              # 몰 목록, 검색어, 카테고리, 두레이 봇 이름
├── requirements.txt         # Python 의존성
├── .env                     # 계정·웹훅 (git 제외, 로컬 전용)
├── 모니터링_가이드.html       # UI 모니터링 상세 가이드
├── 매출통계_발송가이드.html    # Admin 통계·매출 통계 상세 가이드
├── .github/workflows/
│   ├── schedule.yml         # GitHub Actions: UI_Test scheduler
│   └── admin_stat.yml       # GitHub Actions: 드림몰 Admin 통계
├── tests/
│   ├── base.py              # 브라우저 초기화, 로그인, 팝업 닫기, 스크린샷, run_test
│   ├── test_main.py         # 메인 화면 진입
│   ├── test_popup.py        # 메인 팝업
│   ├── test_search.py       # 검색
│   ├── test_category.py     # 카테고리
│   ├── test_gnb.py          # GNB 메뉴
│   ├── test_popular.py      # 하단 인기상품
│   ├── test_cart.py         # 장바구니
│   ├── test_shipping.py     # 배송지 등록 양식
│   └── test_exhibition.py   # 기획전 오류 확인
├── report/
│   ├── generator.py         # 마크다운 리포트 / 두레이 요약 메시지
│   └── dooray.py            # 두레이 웹훅 발송
├── screenshots/ reports/    # 결과물 (git 제외)
└── admin_stat/              # 드림몰 Admin 통계·매출 통계 프로그램
    ├── main.py              # 로그인, 통계 수집, 매출 통계 API 호출, 메일 발송
    ├── chart_builder.py     # 주문/클레임 차트, 카카오톡용 리포트 이미지
    ├── report/
    │   ├── sales.py         # 매출 통계 메일 본문, 엑셀 첨부
    │   ├── email.py         # 일일 Admin 리포트 메일, SMTP 발송
    │   ├── html.py          # PDF용 HTML 리포트
    │   └── kakao.py         # 카카오톡(솔라피) 발송
    ├── DreamAdminStat.bat   # 로컬 작업 스케줄러용 실행 파일
    └── requirements.txt
```
