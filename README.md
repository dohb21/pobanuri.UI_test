# 온누리몰 UI 자동화 테스트

Playwright 기반의 온누리 계열 몰 UI 자동화 점검 도구입니다.
몰마다 PC와 모바일 화면을 실제 Chromium 브라우저로 열어 9개 시나리오를 검증하고, 결과를 마크다운 리포트·스크린샷으로 저장하며 두레이 메신저로 요약을 발송합니다.

같은 레포의 `admin_stat/`에는 드림몰 Admin 통계를 수집해 전송하는 별도 프로그램이 있습니다. 두 프로그램은 서로 다른 워크플로로 실행됩니다([GitHub Actions](#github-actions) 참고).

---

## 목차

- [점검 대상](#점검-대상)
- [동작 원리](#동작-원리)
- [테스트 항목](#테스트-항목)
- [설치 방법](#설치-방법)
- [설정](#설정)
- [실행 방법](#실행-방법)
- [GitHub Actions](#github-actions)
- [결과물 확인](#결과물-확인)
- [디렉터리 구조](#디렉터리-구조)

---

## 점검 대상

`config.yaml`의 `malls` 목록이 점검 대상입니다.

| 몰 | id | 로그인 |
|----|----|--------|
| 드림몰 | `dream` | 필요 |
| 교직원공제회(thek) | `thek` | 필요 |

---

## 동작 원리

```
main.py
  └─ config.yaml 의 malls 로드 (skip: true 인 몰 제외)
       └─ 몰마다 별도 프로세스로 실행 (동시 실행 수: MAX_WORKERS, 기본 2)
            └─ PC → Mobile 순서로
                 ├─ Chromium 실행 (PC 1280×800 / Mobile iPhone 14 Pro Max 에뮬레이션)
                 ├─ 로그인이 필요한 몰이면 ID / PASSWORD 로 로그인
                 ├─ 9개 시나리오를 순차 실행 → TestResult 수집
                 └─ 실패 시 스크린샷 자동 저장
  └─ reports/report_YYYYMMDD_HHMMSS.md 저장
  └─ 두레이 웹훅으로 요약 발송 (DOORAY_WEBHOOK_URL 이 설정된 경우)
  └─ 실패가 1건이라도 있으면 종료 코드 1
```

- 각 시나리오는 `tests/` 아래 별도 모듈이며 `run(page, ...)` 함수로 호출됩니다.
- 성공하면 비고 문자열을 반환하고, 실패하면 예외를 발생시킵니다.
- `tests/base.py`의 `run_test()`가 예외를 잡아 실패 스크린샷을 저장하고 결과 객체로 통일합니다.
- 7일이 지난 스크린샷·리포트는 실행할 때 자동 삭제됩니다.

---

## 테스트 항목

| # | 테스트명 | 모듈 | 검증 내용 |
|---|---------|------|---------|
| 1 | 메인 화면 진입 | `test_main.py` | 페이지 로드, 타이틀·`<body>` 표시 |
| 2 | 메인 팝업 노출 | `test_popup.py` | 배너 팝업 탐지, 슬라이드 링크 진입, 닫기 동작 |
| 3 | 검색 기능 | `test_search.py` | 유효 키워드 풀에서 무작위 선택 → 검색 결과 상품 1개 이상 |
| 4 | 카테고리 상품 노출 | `test_category.py` | 카테고리 풀에서 무작위 N개 선택 → 메뉴 진입 → 상품 목록 1개 이상 |
| 5 | GNB 메뉴 진입 | `test_gnb.py` | 상단 메뉴 전체 순회, 페이지 이동 또는 모달 열림 확인 |
| 6 | 하단 인기상품 목록 | `test_popular.py` | 메인 하단 `div.section.sec_6`의 탭과 상품 목록(`#searchUnitList li`) 로드 |
| 7 | 장바구니 담기 | `test_cart.py` | 장바구니 비우기 → 인기상품 담기 → 주문하기로 주문 페이지 진입 확인 → 다시 비우기 |
| 8 | 배송지 등록 양식 | `test_shipping.py` | 배송지 추가 팝업이 열리고 입력 필드가 동작하는지 확인 (저장하지 않음) |
| 9 | 기획전 오류 확인 | `test_exhibition.py` | 기획전 상세 페이지가 오류 코드(PRD0001~0003) 화면이 아닌지 확인. 기획전이 없으면 통과(스킵) |

- 7·8번은 `ID`가 설정된 경우에만 실행됩니다.
- 7번은 **테스트 계정의 장바구니를 시작과 끝에 비웁니다.** 전용 테스트 계정을 사용하세요.

---

## 설치 방법

Python 3.11 이상이 필요합니다.

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## 설정

설정은 `config.yaml`(테스트 동작)과 `.env`(민감 정보) 두 곳으로 분리합니다.

### config.yaml

```yaml
malls:
  - name: "드림몰"
    id: dream
    urls:
      pc: "https://dream.onuri.co.kr/main"
      mobile: "https://mdream.onuri.co.kr/main"
    requires_login: true
    categories:               # 이 몰 전용 카테고리 (없으면 categories.pool 사용)
      - 가전/디지털
      - 식품

search:
  valid:                      # 검색 테스트용 키워드 풀 (실행마다 무작위 선택)
    - 생수
    - 수건

categories:
  pool:                       # 카테고리 테스트 기본 풀
    - 가전/디지털
    - 식품
  count: 5                    # 풀에서 무작위로 뽑는 개수

dooray:
  bot_name: "드림몰 테스트봇"
```

몰 항목에서 쓰는 필드입니다.

| 필드 | 설명 |
|------|------|
| `name`, `id` | 리포트에 표시되는 이름 / `--mall` 옵션에서 쓰는 식별자 |
| `urls.pc`, `urls.mobile` | PC / 모바일 메인 주소 |
| `requires_login` | `true`이면 `ID`/`PASSWORD`로 로그인 |
| `login_url` | 로그인 주소가 기본 규칙(`/main` → `/indexLogin`)과 다를 때 지정 |
| `search_valid` | 이 몰 전용 검색어 (없으면 `search.valid` 사용) |
| `categories` | 이 몰 전용 카테고리 (없으면 `categories.pool` 사용). 몰에 실제로 있는 카테고리만 적어야 합니다 |
| `skip` | `true`이면 몰 전체를 점검에서 제외 |
| `skip_tests` | 이 몰에서만 제외할 시나리오 이름 목록 (예: `하단 인기상품 목록`, `장바구니 담기`) |

### .env (git 제외, 로컬 전용)

```env
ID=테스트계정아이디
PASSWORD=테스트계정비밀번호
DOORAY_WEBHOOK_URL=
```

| 키 | 용도 |
|----|------|
| `ID`, `PASSWORD` | 로그인이 필요한 모든 몰이 공용으로 쓰는 테스트 계정 |
| `DOORAY_WEBHOOK_URL` | 두레이 웹훅. 비워 두면 발송하지 않음 |

`.env` 값은 이미 설정된 시스템 환경변수보다 우선합니다.

---

## 실행 방법

```bash
python main.py                              # 전체 몰, 전체 시나리오 (headless)
python main.py --show                       # 브라우저 창을 띄워서 실행
python main.py --mall dream                 # 특정 몰만 (id 또는 이름 일부, 대소문자 무관)
python main.py --only 검색,cart             # 특정 시나리오만
python main.py --mall thek --only gnb --show
```

`--only`에는 시나리오 이름이나 별칭을 쓸 수 있습니다.

| 시나리오 | 별칭 |
|----------|------|
| 메인 화면 진입 | `main`, `메인` |
| 메인 팝업 노출 | `popup`, `팝업` |
| 검색 기능 | `search`, `검색` |
| 카테고리 상품 노출 | `category`, `카테고리` |
| GNB 메뉴 진입 | `gnb`, `메뉴` |
| 하단 인기상품 목록 | `popular`, `인기상품` |
| 장바구니 담기 | `cart`, `장바구니` |
| 배송지 등록 양식 | `shipping`, `배송지` |
| 기획전 오류 확인 | `exhibition`, `기획전` |

환경변수 `MAX_WORKERS=1`을 주면 몰을 순차 실행합니다. 실패 항목이 하나라도 있으면 종료 코드 `1`로 끝납니다.

---

## GitHub Actions

이 레포에는 워크플로가 두 개 있습니다.

| 워크플로 | 파일 | 실행 주기 | 대상 폴더 |
|----------|------|-----------|-----------|
| UI_Test scheduler | `.github/workflows/schedule.yml` | 6시간 간격 | 루트 (`main.py`) |
| 드림몰 Admin 통계 | `.github/workflows/admin_stat.yml` | 수동 실행만 (자동 실행은 주석 처리) | `admin_stat/` |

### UI_Test scheduler

워크플로 `UI_Test scheduler`가 6시간 간격(`7 */6 * * *`, UTC)으로 자동 실행됩니다. KST로는 03:07 · 09:07 · 15:07 · 21:07이며, GitHub 스케줄 특성상 실제 시작 시각은 늦어지거나 일부 건너뛸 수 있습니다. 수동 실행은 **Actions → UI_Test scheduler → Run workflow**입니다.

Repository Secrets에 아래 3개를 등록해야 합니다.

| Secret 이름 | 로컬 `.env` 키 | 설명 |
|-------------|----------------|------|
| `ID` | `ID` | 테스트 계정 아이디 |
| `PASSWORD` | `PASSWORD` | 테스트 계정 비밀번호 |
| `WEBHOOK_URL` | `DOORAY_WEBHOOK_URL` | 두레이 웹훅 URL (이름이 다릅니다) |

- Secrets와 `.env`에는 같은 값을 넣습니다. 값이 바뀌면 양쪽을 모두 고칩니다.
- 워크플로는 `ID`, `PASSWORD`, `DOORAY_WEBHOOK_URL`, `MAX_WORKERS=1`만 전달합니다.
- 실행이 끝나면 `test-reports`(reports/), `test-screenshots`(screenshots/)가 아티팩트로 30일간 보관됩니다.
- 실패 항목이 있으면 종료 코드 1로 끝나서 Actions 실행도 failure로 표시됩니다.

### 드림몰 Admin 통계

`admin_stat/`의 Selenium 프로그램이 드림몰 Admin 통계를 수집해 이메일(과 설정 시 카카오)로 전송합니다. 워크플로 `드림몰 Admin 통계`는 `admin_stat/` 안에서 `python main.py`를 실행합니다. 현재는 사용하지 않아 자동 실행(`schedule`)을 주석 처리했고 **Actions → 드림몰 Admin 통계 → Run workflow**로 수동 실행만 가능합니다. 다시 쓰려면 `admin_stat.yml`의 `schedule` 주석을 풉니다(기존 주기: 매일 23:02 UTC = 08:02 KST, 월요일이면 주간·매달 1일이면 월간 매출 통계 전송은 코드가 판단). 결과물은 `admin-stat-reports` 아티팩트(`admin_stat/reports/`)로 30일간 보관됩니다.

Secrets 이름은 로컬 `.env` 키와 **같습니다**. 같은 값을 양쪽에 넣습니다.

| Secret / `.env` 키 | 용도 |
|--------------------|------|
| `ADMIN_USER`, `ADMIN_PASS` | Admin 로그인 계정 |
| `EMAIL_FROM`, `EMAIL_PASSWORD`, `EMAIL_TO` | 보내는 메일 / 앱 비밀번호 / 받는 메일 |
| `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT` | SMTP 서버 / 포트 |
| `B2B_ADMIN_USER`, `B2B_ADMIN_PASS` | B2B Admin 로그인 계정 |
| `SALES_EMAIL_TO` | 매출 통계 수신자 (없으면 `EMAIL_TO` 사용) |
| `LOGIN_USER_FIELD`, `LOGIN_PASS_FIELD` | 로그인 입력칸 이름. 비워 두면 후보 이름을 자동 탐지 |
| `SOLAPI_API_KEY`, `SOLAPI_API_SECRET`, `SOLAPI_FROM_NUMBER`, `KAKAO_CHANNEL_ID`, `KAKAO_TO` | 카카오 발송용 |

마지막 두 줄은 이전에 Secrets에 등록하지 않고 운영하던 항목입니다. `UI_Test scheduler`의 Secrets(`ID`, `PASSWORD`, `WEBHOOK_URL`)와 이름이 겹치지 않습니다.

---

## 결과물 확인

| 경로 | 내용 |
|------|------|
| `reports/` | 마크다운 리포트 `report_YYYYMMDD_HHMMSS.md` (몰별 요약, 항목별 결과, 실패 상세) |
| `screenshots/` | 실패 시 자동 저장되는 화면 (팝업 테스트는 성공 시에도 저장). `YYYYMMDD_HHMMSS_몰 플랫폼_테스트명.png` |

두 폴더 모두 git에서 제외되며, 7일이 지난 파일은 다음 실행 때 삭제됩니다.

---

## 디렉터리 구조

```
UI_test/
├── main.py                  # 진입점: 설정 로드, 몰/플랫폼별 실행, 리포트 저장, 두레이 발송
├── config.yaml              # 몰 목록, 검색어, 카테고리, 두레이 봇 이름
├── requirements.txt         # Python 의존성
├── .env                     # 계정·웹훅 (git 제외, 로컬 전용)
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
└── admin_stat/              # 드림몰 Admin 통계 전송 프로젝트 (admin_stat.yml 로 실행)
```