# Smart-Cart-5 검증 범위

검증일: 2026-09-21. 소프트웨어·CAD 형상 검증과 실제 조립/통전 승인을 구분한다. 아래 수치는 가공품 개수나 BOM 구매 수량이 아니다.

## 형상과 데이터

현재 모델은 **116개 선택 참조, 782개 솔리드 구성요소, 209개 재질/참조별 BREP 피처, 50개 케이블·하네스, 555,512개 렌더 삼각형**으로 구성된다. 웹과 CAD는 같은 mm 기준 형상에서 생성한다. 렌더러 내부에서만 m로 변환한다.

| 검사 | 결과 | 근거 |
|---|---|---|
| 209개 BREP 유효성·재읽기 | 통과 | [CAD 컨테이너 검사](cad-container-qa.json) |
| FCStd ZIP CRC·XML·순차 복원 순서 | 통과 | Document.xml → 실제 BREP → GuiDocument.xml 순서 |
| 과거 D4 형상 혼입 | 0개 | 새 D5 피처만 패키징 |
| STEP 재가져오기 | 유효한 768개 솔리드 | [STEP 검사](step-qa.json). 외장품 14개 솔리드 제외 |
| STEP 왕복 체적 상대 오차 | 1.263e-09 | 동일 BREP 집계와 비교 |
| 원본 SCMB 본체 | 0.615083kg/개 | [생성 요약](build-summary.json). 밀도 기반 값, 하중 승인 아님 |
| 데이터·끝단·CSV·메시 일관성 | 별도 자동 검사 | [정적 검사](static-qa.json) |

FCStd의 이전 빈 화면 문제를 피하기 위해 실제 BREP를 올바른 파일 순서로 저장하고 각 피처를 재읽었다. **이는 FreeCAD/SolidWorks 애플리케이션을 직접 실행한 열기 시험이 아니다.** 네이티브 GUI 열기·저장, Sketcher/PartDesign 이력 편집은 미실행이다. STEP 중립 솔리드와 BREP 가져오기 매크로를 대체 경로로 포함한다.

## 배선과 물리 공간

[라우팅 검사](routing-review.json)는 50개 전선의 실제 원형 단면 스윕과 등록된 **116개 장애물 솔리드**를 Open CASCADE로 교차 검사했다. 차체 상판, 주요 프레임, 배터리, 주요 부품, PCB, 보호 커버를 포함한다. 판재 통과부는 실제로 뚫은 홀·부싱·커버 개구부를 사용한다.

교차 체적 0.001mm³ 초과 검출 건수는 0개였다. 모든 케이블이 이 모델에 설정한 임시 최소 굴곡 규칙인 **외경의 4배**를 만족했다. 이 기준은 공급 케이블의 공식 최소 굴곡반경으로 대체해야 한다. 검사에 포함하지 않은 작은 장식 부품·전체 볼트·케이블 상호 이격, 공차, 실제 케이블 쳐짐과 끌림까지 모두 검증했다고 해석하면 안 된다. 펼친 손잡이 기준이며 접힘 운동과 캐스터 전체 동작 영역은 별도 검증 대상이다.

`data/cover-cutouts.json`에는 배선을 피하도록 만든 제어 커버 개구부를 기록했다. 50개 연결 중 USB·논리 하네스는 묶음 경로이다. 개별 구매 PCB의 모든 핀 번호와 전선 가닥 수를 확정한 결선표가 아니다.

## 렌더링

프로덕션 `js/renderer.js`의 **동일 VS/FS 셰이더 문자열**, 동일 `geometry.bin` 및 재질을 Mesa EGL/OpenGL ES 3.2 오프스크린 환경에서 실행했다. 두 셰이더 컴파일, 프로그램 링크, 깊이 프레임버퍼와 5개 시점 렌더를 통과했으며 GL 오류는 0이었다. [실행 기록](offscreen-render.json)

이는 브라우저의 WebGL 전체 초기화·프레젠테이션 검사가 아니라 별도의 실제 GL 실행이다. 첨부 `render-*.png`는 이 경로에서 만든 모델 렌더이며 제품 사진이나 이미지 생성 결과가 아니다. 금속·고무·PCB·피복의 시각적 표현은 제품 실제 재질/공정 인증이 아니다.

## 브라우저와 조작

[브라우저 실행 기록](browser-fixture-qa.json)은 실제 배포 HTML/CSS/JS를 Chromium에 넣고 동일 로컬 JSON/바이너리를 공급하는 fixture 방식의 검사이다. 이 환경에서는 네이티브 브라우저 WebGL 2 대신 동일 메시의 **Canvas CPU 호환 렌더러**를 사용했다. 이 경로의 속도·조명·그림자 품질은 GPU 경로와 다르다.

브라우저 fixture의 42개 검사를 통과했다. 시점 버튼, 실제 마우스 드래그에 따른 하부 진입·바닥 숨김·복원, 방향키, 검색, 픽셀 부품 선택, 선택 부품 확대, 레이어 전환, 모바일 탐색과 시야 보정, 2D 배선 투영·검색·표 선택을 검사한다. PNG와 SVG의 Blob 다운로드는 브라우저 다운로드 경로에서 파일 시그니처/내용을 확인한다. 브라우저별 **네이티브 HTTP URL 탐색이나 file:// 실행, GitHub Pages 실제 게시, localStorage 영속성**을 검증한 것은 아니다. 본 앱은 localStorage 저장 기능을 요구하지 않는다.

## 미실행·미해결

실물 실측과 조립, 토크·전류 실측, 모터축 반경방향 허용하중, 체결·진동·피로, 구조 FEA, 적재/승차, 제동·경사면 정지, 충전·화재·방수·EMI, 전장 정격·안전 성능 인증은 수행하지 않았다. 본체 형상과 전선 경로가 존재한다는 이유로 이 항목을 통과한 것으로 표시하지 않는다. [치수](DIMENSIONS-KR.md)와 [통전 보류 조건](ELECTRICAL-HOLD-KR.md)을 먼저 해소한다.

## 재실행

```sh
python -m pip install -r requirements-cad.txt
python tools/build_release.py
python tools/package_fcstd.py
python tests/static_regression.py
```

`tests/browser_fixture.py`는 Python Playwright와 설치된 Chromium이 추가로 필요하다. `CHROMIUM_PATH`로 실행 파일을 지정할 수 있다. `tools/render_egl.py`는 Linux Mesa EGL/OpenGL ES 및 Pillow가 추가로 필요하다. 렌더와 시험 도구는 웹앱 실행 의존성이 아니다. 형상 수정 뒤 이전 QA JSON만 남겨두지 말고 해당 검사를 다시 실행한다.
