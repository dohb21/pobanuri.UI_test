# pobanuri UI 자동화 테스트

Playwright 기반의 드림몰(dream.onuri.co.kr) UI 자동화 테스트 도구입니다. 
PC와 모바일 환경을 동시에 검증하며, 테스트 결과를 스크린샷·영상·마크다운 리포트로 저장합니다.


---

## 목차

- [테스트 원리](#테스트-원리)
- [테스트 항목](#테스트-항목)
- [설치 방법](#설치-방법)
- [설정](#설정)
- [실행 방법](#실행-방법)
- [결과물 확인](#결과물-확인)
- [디렉터리 구조](#디렉터리-구조)

---

## 테스트 원리

```
main.py
  └─ run_platform() × 2 (PC / Mobile)
       ├─ Playwright Chromium 브라우저 실행 (headless)
       ├─ PC: viewport 1280×800
       ├─ Mobile: Galaxy S5 에뮬레이션
       └─ 각 테스트 모듈 순차 실행 → TestResult 수집
```

1. **Playwright** 로 실제 Chromium 브라우저를 제어합니다. 실제 브라우저가 페이지를 열고 버튼을 클릭하므로 JS 렌더링, AJAX 응답, 동적 UI를 포함한 실제 사용자 시나리오를 검증합니다.
2. 각 테스트는 `tests/` 폴더 아래 별도 모듈로 분리되어 있으며, `run(page, ...)` 함수를 통해 호출됩니다.
3. 테스트 성공 시 `note` 문자열을, 실패 시 `AssertionError` 또는 `Exception` 을 발생시킵니다.
4. `base.run_test()` 래퍼가 예외를 캐치해 실패 스크린샷을 자동 저장하고 `TestResult` 객체로 통일합니다.
5. 팝업 테스트는 별도 브라우저 컨텍스트로 **비디오 녹화**까지 수행합니다.
6. 7일이 지난 스크린샷·리포트·영상은 실행 시 자동 삭제됩니다.

---

## 테스트 항목

PC와 Mobile 각각 아래 8개 시나리오를 순서대로 실행합니다.

| # | 테스트명 | 모듈 | 검증 내용 |
|---|---------|------|---------|
| 1 | **메인 화면 진입** | `test_main.py` | 페이지 로드 성공, 타이틀 비어있지 않음, `<body>` 요소 표시 |
| 2 | **메인 팝업 노출** | `test_popup.py` | 배너 팝업 컨테이너 탐지, Swiper 슬라이드 링크 진입 확인, 닫기 버튼 동작 (스크린샷 + 영상 저장) |
| 3 | **검색 기능** | `test_search.py` | config의 유효 키워드 중 3개 무작위 선택 → UI 검색 시도 → URL 직접 이동 폴백 → 결과 상품 1개 이상 확인 |
| 4 | **카테고리 상품 노출** | `test_category.py` | config의 카테고리 풀에서 무작위 N개 선택 → GNB 카테고리 메뉴 진입 → 중분류 클릭 → 상품 목록 1개 이상 확인 |
| 5 | **GNB 메뉴 진입** | `test_gnb.py` | 상단 네비게이션 메뉴 전체 순회 → 일반 링크·기획전·JS 팝업·할부 팝업 유형별 분기 → 페이지 이동 또는 모달 열림 확인 |
| 6 | **하단 인기상품 목록** | `test_popular.py` | 메인 하단 `div.section.sec_6` 섹션 존재 확인, 카테고리 탭 및 상품 목록 로드 확인 |
| 7 | **장바구니 담기** | `test_cart.py` | 로그인 → 사전 장바구니 비우기 → 인기상품 "장바구니 담기" 클릭 → 옵션 선택 → 장바구니 항목 수 증가 확인 → "주문하기" 클릭 → 결제 페이지 이동 확인 → 사후 비우기 |
| 8 | **배송지 등록 양식** | `test_shipping.py` | 로그인 → 배송지 관리 페이지 진입 → "배송지 추가" 클릭 → 팝업 폼 필드(이름·전화·우편번호·주소) 입력 가능 여부 확인 |

> 7·8번은 `.env`의 `ACCOUNT_USERNAME`이 설정된 경우에만 실행됩니다.

---

## 설치 방법

**Python 3.11 이상** 필요

```bash
# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

---

## 설정

설정은 `config.yaml`(테스트 동작)과 `.env`(민감 정보) 두 파일로 분리 관리합니다.

### config.yaml — 테스트 동작 설정

```yaml
urls:
  pc: "https://dream.onuri.co.kr/main"       # PC 테스트 URL
  mobile: "https://mdream.onuri.co.kr/main"  # 모바일 테스트 URL

search:
  valid:                # 검색 테스트용 유효 키워드 풀 (매 실행마다 3개 무작위 선택)
    - 생수
    - 수건
    # ...

categories:
  pool:                 # 카테고리 테스트 대상 풀
    - 가전/디지털
    - 식품
    # ...
  count: 5              # 풀에서 무작위로 선택할 카테고리 수

dooray:
  bot_name: "드림몰 테스트봇"
```

### .env — 민감 정보 (git 제외)

```env
ACCOUNT_USERNAME=아이디       # 장바구니·배송지 테스트에 사용 (없으면 두 항목 스킵)
ACCOUNT_PASSWORD=비밀번호
DOORAY_WEBHOOK_URL=https://...
```

> GitHub Actions에서는 `.env` 대신 Repository Secrets(`username`, `password`, `WEBHOOK_URL`)로 관리합니다.

---

## 실행 방법

### 기본 실행 (브라우저 숨김, headless)

```bash
python main.py
```

### 브라우저 화면 표시하며 실행

```bash
python main.py --show
```

실행하면 PC → Mobile 순으로 테스트가 진행되며, 터미널에 각 항목의 진행 상황이 출력됩니다.

```
[PC] 테스트 시작...
  [1/8] 메인 화면 진입... ✅
  [2/8] 메인 팝업 노출... ✅
  [3/8] 검색 기능... ✅
  ...
PC 완료: 8/8 통과

[Mobile] 테스트 시작...
  ...
```

테스트 실패 항목이 하나라도 있으면 종료 코드 `1`로 종료합니다 (CI 연동 가능).

### GitHub Actions 자동 실행

매일 **08:38**, **14:38** (KST) 두 차례 자동 실행됩니다.
수동 실행은 GitHub 저장소의 **Actions → 9-17 scheduler → Run workflow**에서 트리거할 수 있습니다.

Repository Secrets에 아래 세 항목이 등록되어 있어야 합니다.

| Secret 이름 | 설명 |
|-------------|------|
| `username` | 테스트 계정 아이디 |
| `password` | 테스트 계정 비밀번호 |
| `WEBHOOK_URL` | 두레이 웹훅 URL |

---

## 결과물 확인

| 경로 | 내용 |
|------|------|
| `screenshots/` | 실패 시 자동 저장되는 스크린샷 (팝업 테스트는 성공 시도 저장). 파일명: `YYYYMMDD_HHMMSS_플랫폼_테스트명.png` |
| `videos/` | 팝업 테스트 영상 (WebM 형식) |
| `reports/` | 마크다운 형식 리포트. 파일명: `report_YYYYMMDD_HHMMSS.md` |

> 7일 이상 지난 파일은 다음 실행 시 자동 삭제됩니다.

---

## 디렉터리 구조

```
UI_test/
├── main.py              # 진입점: 설정 로드, PC/Mobile 순차 실행, 리포트 저장
├── config.yaml          # URL, 검색 키워드, 카테고리, 두레이 봇 이름 설정
├── .env                 # 계정 정보·웹훅 URL (git 제외, 로컬 전용)
├── requirements.txt     # Python 의존성
├── tests/
│   ├── base.py          # 공통 유틸: 브라우저 초기화, 팝업 닫기, 로그인, 스크린샷
│   ├── test_main.py     # 메인 화면 진입
│   ├── test_popup.py    # 메인 팝업 노출 및 링크 검증
│   ├── test_search.py   # 검색 기능
│   ├── test_category.py # 카테고리 메뉴 진입 및 상품 노출
│   ├── test_gnb.py      # GNB 전체 메뉴 진입
│   ├── test_popular.py  # 하단 인기상품 목록
│   ├── test_cart.py     # 장바구니 담기 및 주문하기
│   └── test_shipping.py # 배송지 등록 양식
├── report/
│   ├── generator.py     # 마크다운 리포트 생성
│   └── dooray.py        # 두레이 웹훅 발송
├── screenshots/         # 스크린샷 저장 디렉터리
├── videos/              # 영상 저장 디렉터리
└── reports/             # 마크다운 리포트 저장 디렉터리
```