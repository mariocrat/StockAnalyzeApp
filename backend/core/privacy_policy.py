import html

from .env import env_value


POLICY_EFFECTIVE_DATE = "2026-07-18"


def _operator_name() -> str:
    return html.escape(env_value("ALPHAMATE_PRIVACY_OPERATOR_NAME").strip() or "AlphaMate 운영자")


def _contact_html() -> str:
    contact_email = html.escape(env_value("ALPHAMATE_PRIVACY_CONTACT_EMAIL").strip())
    if contact_email:
        return f'<a href="mailto:{contact_email}">{contact_email}</a>'
    return "Google Play 스토어에 표시된 개발자 연락처 또는 앱 내 계정/데이터 관리"


def _page_style() -> str:
    return """
    :root { color-scheme: dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #0b0f17; color: #d9dfeb; line-height: 1.7; }
    main { width: min(100% - 32px, 860px); margin: 0 auto; padding: 36px 0 64px; }
    h1 { margin: 0 0 8px; color: #fff; font-size: 28px; }
    h2 { margin: 32px 0 10px; color: #f4f7ff; font-size: 19px; }
    h3 { margin: 20px 0 8px; color: #eef3ff; font-size: 16px; }
    p, li { font-size: 15px; }
    .meta { color: #8f99ad; }
    .notice { margin: 24px 0; padding: 16px; border: 1px solid #2d5fd2; border-radius: 8px; background: #101b38; }
    .warning { border-color: #8a6420; background: #2a2112; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0; }
    .button { display: inline-block; padding: 11px 16px; border-radius: 6px; background: #2962ff; color: #fff; font-weight: 700; text-decoration: none; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { padding: 12px; border: 1px solid #293143; text-align: left; vertical-align: top; }
    th { background: #151b28; color: #fff; }
    a { color: #76a5ff; }
    code { color: #bcd0ff; }
    @media (max-width: 640px) {
      main { width: min(100% - 24px, 860px); padding-top: 24px; }
      h1 { font-size: 24px; }
      table { display: block; overflow-x: auto; white-space: normal; }
      th, td { min-width: 150px; }
    }
    """


def privacy_policy_html() -> str:
    operator = _operator_name()
    contact = _contact_html()
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>AlphaMate 개인정보처리방침</title>
  <style>{_page_style()}</style>
</head>
<body>
<main>
  <h1>AlphaMate 개인정보처리방침</h1>
  <p class="meta">시행일: {POLICY_EFFECTIVE_DATE} · 개인정보처리자: {operator}</p>
  <p class="notice">AlphaMate는 매매 기록과 AI 복기 데이터를 사용자가 선택한 기능을 제공하는 범위에서만 처리합니다. AI 복기는 투자 판단을 대신하지 않으며, 사용자는 계정/데이터 관리에서 저장 기록을 확인·내보내기·삭제할 수 있습니다.</p>

  <h2>1. 처리하는 개인정보와 수집 방법</h2>
  <table>
    <thead><tr><th>구분</th><th>처리 항목</th><th>수집 방법</th></tr></thead>
    <tbody>
      <tr><td>간편 로그인</td><td>로그인 제공자, 제공자가 발급한 사용자 식별자, 표시 이름 또는 별명, 앱 로그인 세션</td><td>카카오·네이버 로그인 과정</td></tr>
      <tr><td>매매복기</td><td>종목명·코드, 매매 일시, 매수·매도 구분, 가격, 수량, 수수료, 세금, 사용자가 입력한 메모</td><td>사용자 직접 입력</td></tr>
      <tr><td>AI 복기</td><td>선택한 매매 기록, 메모, 계산된 손익, 차트·기술지표 요약, 최근 매매 요약(심화 복기)</td><td>사용자가 동의 후 AI 복기를 요청할 때</td></tr>
      <tr><td>이용권·결제·광고 보상</td><td>상품 ID, 구매 토큰과 주문 상태, 이용권 잔여량, 광고 보상 확인값과 지급 이력</td><td>Google Play 및 Google AdMob</td></tr>
      <tr><td>서비스 운영</td><td>접속 시각, 요청 경로·상태, 비식별 요청 ID, 오류 종류, IP 주소, 기기·앱 환경 정보</td><td>서비스 이용 중 자동 생성</td></tr>
      <tr><td>광고</td><td>광고 식별자, 기기 정보, 대략적 위치 등 Google Mobile Ads SDK가 광고 제공·측정을 위해 처리하는 정보</td><td>무료 사용자에게 광고가 표시될 때</td></tr>
    </tbody>
  </table>
  <p>AlphaMate는 카카오·네이버 비밀번호와 신용카드 번호를 직접 수집하거나 저장하지 않습니다. 사용자가 메모에 민감정보나 불필요한 개인정보를 적지 않도록 권장합니다.</p>

  <h2>2. 처리 목적</h2>
  <ul>
    <li>사용자 구분, 로그인 유지, 계정 보호와 부정 이용 방지</li>
    <li>실현손익·수익률·승률 계산, 매매 차트와 복기 보관함 제공</li>
    <li>사용자가 요청한 일반·심화 AI 복기 제공</li>
    <li>구독·소모성 이용권 검증, 중복 지급 방지, 광고 보상 확인</li>
    <li>장애 분석, 보안 모니터링, 고객 문의 대응과 서비스 개선</li>
  </ul>

  <h2>3. 처리 및 보유 기간</h2>
  <table>
    <thead><tr><th>정보</th><th>보유 기간</th></tr></thead>
    <tbody>
      <tr><td>계정·로그인 연결 정보</td><td>회원 탈퇴 또는 계정 데이터 삭제 완료 시까지</td></tr>
      <tr><td>저장을 켠 매매 기록과 복기 결과</td><td>사용자가 해당 기록을 삭제하거나 계정 데이터를 삭제할 때까지</td></tr>
      <tr><td>저장을 끈 상태의 1회성 매매 입력</td><td>현재 복기 요청 처리와 화면 표시가 끝날 때까지. 서버 복기 보관함에는 저장하지 않음</td></tr>
      <tr><td>운영·오류 로그</td><td>원칙적으로 90일 후 자동 삭제</td></tr>
      <tr><td>결제·이용권·광고 보상 기록</td><td>계정 삭제 시까지. 다만 관련 법령 준수, 결제 분쟁 또는 부정 이용 방지를 위해 필요한 항목은 해당 목적 달성 시까지 분리 보관할 수 있음</td></tr>
      <tr><td>OpenAI API 전송 데이터</td><td>AlphaMate는 Responses API 요청에 <code>store=false</code>를 설정합니다. OpenAI의 안전·오용 방지 로그는 해당 업체 정책에 따라 최대 30일 보관될 수 있음</td></tr>
    </tbody>
  </table>

  <h2>4. 제3자 제공, 처리위탁 및 국외 이전</h2>
  <p>AlphaMate는 개인정보를 판매하지 않으며, 사용자의 별도 동의 또는 법령상 근거 없이 아래 목적과 무관한 제3자에게 제공하지 않습니다. 서비스 제공을 위해 아래 업체에 처리를 위탁하거나 국외에서 처리할 수 있습니다. 업체·국가·처리 내용이 바뀌는 경우 이 방침을 갱신합니다.</p>
  <table>
    <thead><tr><th>수탁자·처리 국가·연락처</th><th>이전 항목과 시점·방법</th><th>목적과 보유 기간</th></tr></thead>
    <tbody>
      <tr><td>Render Services, Inc. · 미국(사업자 운영), 싱가포르(서버 리전)<br><a href="mailto:privacy@render.com">privacy@render.com</a></td><td>계정, 저장 매매 기록, 이용권·운영 정보가 서비스 이용 시 HTTPS로 전송</td><td>백엔드·데이터베이스 호스팅. 위 3항의 AlphaMate 보유 기간 적용</td></tr>
      <tr><td>OpenAI, L.L.C. · 미국 및 서비스 처리 지역<br><a href="mailto:privacy@openai.com">privacy@openai.com</a></td><td>사용자가 동의하고 AI 복기를 누를 때 매매 기록·메모·차트 요약을 HTTPS로 전송</td><td>AI 복기 생성. API 데이터는 별도 동의 없이는 모델 학습에 사용되지 않으며, 안전·오용 방지 로그는 최대 30일 보관될 수 있음</td></tr>
      <tr><td>Google LLC · 미국 등 Google 처리 지역<br><a href="mailto:googlekrsupport@google.com">googlekrsupport@google.com</a></td><td>광고 식별자·기기 정보, 광고 보상값, 구매 토큰·상품 상태가 광고 표시 또는 결제 시 HTTPS로 전송</td><td>AdMob 광고·보상 확인 및 Google Play 결제 검증. Google 정책과 법정 보유 기간 적용</td></tr>
      <tr><td>카카오·네이버 · 대한민국</td><td>로그인 요청 시 OAuth 인증 정보와 제공자 사용자 식별자가 HTTPS로 전송</td><td>간편 로그인과 계정 연결. 연결 해제 또는 계정 삭제 시까지</td></tr>
    </tbody>
  </table>
  <p>국외 처리에 동의하지 않는 경우 AI 복기 동의를 하지 않거나 계정·저장 기능을 사용하지 않을 수 있습니다. AI 전송을 거부하면 AI 복기는 제공되지 않지만 직접 입력한 매매 기록의 손익 계산은 계속 사용할 수 있습니다. 호스팅 처리를 거부하려면 계정/데이터 관리에서 서버 저장을 끄거나 계정 데이터를 삭제할 수 있습니다. 광고·결제 처리를 거부하면 광고 보상 또는 Google Play 결제 기능이 제한될 수 있습니다.</p>
  <p>AI 복기는 별도 동의 후에만 실행됩니다. OpenAI API로 전송된 데이터는 사용자가 명시적으로 공유에 동의하지 않는 한 OpenAI 모델 학습에 사용되지 않습니다.</p>

  <h2>5. 자동 수집 장치와 광고</h2>
  <p>무료 사용자에게 Google AdMob 광고가 표시될 수 있으며, Google Mobile Ads SDK는 광고 제공·빈도 제한·성과 측정·부정 이용 방지를 위해 광고 식별자와 기기 정보를 처리할 수 있습니다. 앱은 현재 비개인 맞춤 광고 요청 옵션을 사용합니다. 운영체제 설정에서 광고 ID를 재설정하거나 맞춤 광고 설정을 변경할 수 있습니다.</p>

  <h2 id="account-deletion">6. 파기 절차와 방법</h2>
  <p>보유 기간이 끝나거나 처리 목적이 달성된 개인정보는 복구하기 어려운 방식으로 삭제합니다. 전자 파일은 데이터베이스에서 삭제하고 이후 백업 교체 주기에 따라 제거합니다. 법령상 보존이 필요한 정보는 다른 정보와 분리해 정해진 기간만 보관한 뒤 삭제합니다.</p>
  <div class="actions"><a class="button" href="/account-deletion">계정 및 데이터 삭제 안내</a></div>

  <h2>7. 정보주체의 권리와 행사 방법</h2>
  <ul>
    <li>앱의 계정/데이터 관리에서 매매 이력 저장을 끄고, 저장 기록을 삭제하거나 JSON 파일로 내보낼 수 있습니다.</li>
    <li>같은 화면의 계정 데이터 삭제로 계정과 연결된 매매 기록·복기 기록·이용 상태의 삭제를 요청할 수 있습니다.</li>
    <li>앱을 사용할 수 없는 경우 <a href="/account-deletion">웹 삭제 안내</a>의 연락 경로를 이용할 수 있습니다.</li>
    <li>법령상 제한 사유가 없는 한 열람·정정·삭제·처리정지 요구를 처리하고 결과를 안내합니다.</li>
  </ul>

  <h2>8. 안전성 확보 조치</h2>
  <p>API 키와 로그인 비밀값은 앱에 포함하지 않고 서버 환경변수로 관리합니다. 전송 구간은 HTTPS를 사용하고, 사용자별 데이터는 로그인 세션으로 구분합니다. 접근 권한 최소화, 요청 횟수 제한, 중요 작업 감사 로그, 비밀정보 마스킹과 정기적인 의존성·배포 점검을 적용합니다.</p>

  <h2>9. 만 14세 미만 아동</h2>
  <p>AlphaMate는 만 14세 미만 아동을 대상으로 하지 않으며, 해당 아동의 개인정보를 고의로 수집하지 않습니다. 관련 사실을 확인하면 법정대리인 확인 등 필요한 절차 후 삭제합니다.</p>

  <h2>10. AI 복기와 투자정보 고지</h2>
  <p>AI 복기와 차트 분석은 과거 기록을 정리하는 참고 정보이며 투자 권유, 수익 보장 또는 전문 금융 자문이 아닙니다. AI 결과에는 오류가 있을 수 있으므로 최종 투자 판단과 책임은 사용자에게 있습니다.</p>

  <h2>11. 개인정보 보호 문의</h2>
  <p>개인정보 보호책임자: {operator}<br>개인정보 열람·정정·삭제·처리정지 및 고충 처리 연락처: {contact}</p>

  <h2>12. 방침 변경</h2>
  <p>처리 항목, 외부 업체 또는 보유 기간이 달라지는 경우 시행 전에 앱 또는 이 페이지를 통해 변경 내용을 알립니다. 중요한 변경은 필요한 경우 다시 동의를 받습니다.</p>
</main>
</body>
</html>"""


def account_deletion_html() -> str:
    operator = _operator_name()
    contact = _contact_html()
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>AlphaMate 계정 및 데이터 삭제</title>
  <style>{_page_style()}</style>
</head>
<body>
<main>
  <h1>AlphaMate 계정 및 데이터 삭제</h1>
  <p class="meta">운영자: {operator}</p>
  <p class="notice">계정 삭제를 요청하면 로그인 연결 정보와 계정에 저장된 매매 기록·AI 복기 기록을 삭제합니다. 삭제가 끝난 데이터는 복구할 수 없습니다.</p>

  <h2>앱에서 즉시 삭제</h2>
  <ol>
    <li>AlphaMate를 열고 오른쪽 위 계정 아이콘을 누릅니다.</li>
    <li><strong>계정/데이터 관리</strong>에서 <strong>계정 데이터 삭제</strong>를 누릅니다.</li>
    <li>확인 절차를 완료하면 현재 로그인 계정과 연결 데이터가 삭제됩니다.</li>
  </ol>

  <h2>앱을 사용할 수 없는 경우</h2>
  <p>아래 연락처로 제목을 <strong>AlphaMate 계정 삭제 요청</strong>으로 작성하고, 카카오 또는 네이버 중 사용한 로그인 방법과 본인 확인에 필요한 최소 정보만 보내 주세요. 비밀번호, API 키, 결제카드 번호는 보내지 마세요.</p>
  <p class="notice">삭제 요청 연락처: {contact}</p>

  <h2>삭제되는 정보</h2>
  <ul>
    <li>카카오·네이버 로그인 연결과 AlphaMate 계정 식별 정보</li>
    <li>서버에 저장된 매매 기록과 AI 복기 보관함</li>
    <li>복기 이용권·광고 보상·구매 상태 등 계정 연결 정보</li>
  </ul>
  <p>결제 분쟁, 부정 이용 방지 또는 법령상 보존 의무가 있는 최소 정보는 해당 목적과 기간 동안 분리 보관한 뒤 삭제할 수 있습니다.</p>

  <div class="actions"><a class="button" href="/privacy">개인정보처리방침 보기</a></div>
</main>
</body>
</html>"""
