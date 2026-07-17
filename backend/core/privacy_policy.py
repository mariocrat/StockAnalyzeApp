import html

from .env import env_value


POLICY_EFFECTIVE_DATE = "2026-07-17"


def privacy_policy_html() -> str:
    contact_email = html.escape(env_value("ALPHAMATE_PRIVACY_CONTACT_EMAIL").strip())
    contact = (
        f'<a href="mailto:{contact_email}">{contact_email}</a>'
        if contact_email
        else "Google Play 스토어에 표시된 개발자 연락처 또는 앱 내 계정/데이터 관리"
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>AlphaMate 개인정보처리방침</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #0b0f17; color: #d9dfeb; line-height: 1.7; }}
    main {{ width: min(100% - 32px, 760px); margin: 0 auto; padding: 36px 0 64px; }}
    h1 {{ margin: 0 0 8px; color: #fff; font-size: 28px; }}
    h2 {{ margin: 32px 0 10px; color: #f4f7ff; font-size: 19px; }}
    p, li {{ font-size: 15px; }}
    .meta {{ color: #8f99ad; }}
    .notice {{ margin: 24px 0; padding: 16px; border: 1px solid #2d5fd2; border-radius: 8px; background: #101b38; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 12px; border: 1px solid #293143; text-align: left; vertical-align: top; }}
    th {{ background: #151b28; color: #fff; }}
    a {{ color: #76a5ff; }}
  </style>
</head>
<body>
<main>
  <h1>AlphaMate 개인정보처리방침</h1>
  <p class="meta">시행일: {POLICY_EFFECTIVE_DATE}</p>
  <p class="notice">AlphaMate는 서비스 제공에 필요한 최소한의 정보만 처리하며, 사용자는 앱에서 저장된 매매 기록을 내보내거나 삭제하고 계정 데이터를 삭제할 수 있습니다.</p>

  <h2>1. 처리하는 정보와 이용 목적</h2>
  <table>
    <thead><tr><th>정보</th><th>이용 목적</th></tr></thead>
    <tbody>
      <tr><td>카카오·네이버 로그인 식별자와 표시 이름</td><td>로그인, 사용자 구분, 이용권 및 저장 기록 연결</td></tr>
      <tr><td>사용자가 입력한 종목, 매매일시, 가격, 수량, 수수료, 세금, 메모</td><td>손익 계산, 매매 차트 및 복기 제공</td></tr>
      <tr><td>매매 기록과 차트·기술지표 요약</td><td>사용자가 요청한 AI 복기 분석 제공</td></tr>
      <tr><td>구독·이용권·광고 보상 및 구매 검증 정보</td><td>유료 기능 제공, 중복 지급과 부정 이용 방지</td></tr>
      <tr><td>요청 시각, 처리 상태, 오류 코드, 비식별화된 요청 ID</td><td>서비스 안정성 확보와 장애 대응</td></tr>
    </tbody>
  </table>

  <h2>2. AI 분석과 외부 서비스 전송</h2>
  <p>AI 복기를 요청하면 입력한 매매 기록, 메모 및 차트 요약이 AlphaMate 서버를 거쳐 AI 분석 제공업체인 OpenAI에 전송될 수 있습니다. AI 복기는 사용자가 전송 동의 항목을 선택한 경우에만 실행됩니다.</p>

  <h2>3. 보관 기간과 삭제</h2>
  <ul>
    <li>매매 이력 저장을 끈 경우 분석 요청 데이터는 요청 처리 용도로만 사용합니다.</li>
    <li>매매 이력 저장을 켠 경우 매매 기록과 복기 결과는 사용자가 삭제하거나 계정을 삭제할 때까지 보관합니다.</li>
    <li>운영 오류 기록은 기본 90일 동안 보관한 뒤 삭제합니다.</li>
    <li>결제 및 광고 보상 검증 기록은 중복 지급·부정 이용 방지와 관련 법령상 의무를 위해 필요한 기간 동안 보관할 수 있습니다.</li>
  </ul>

  <h2>4. 이용하는 외부 서비스</h2>
  <p>서비스 운영 과정에서 Render(서버 호스팅), OpenAI(AI 분석), Kakao·NAVER(간편 로그인), Google Play(결제), Google AdMob(광고 및 보상 검증)을 이용합니다. 각 제공업체는 해당 서비스 제공에 필요한 범위에서 정보를 처리할 수 있습니다.</p>

  <h2>5. 사용자의 권리</h2>
  <p>사용자는 앱의 계정/데이터 관리에서 매매 이력 저장 여부를 변경하고, 저장된 데이터를 내보내거나 개별 기록·전체 저장 기록·계정 데이터를 삭제할 수 있습니다. 로그아웃하면 현재 기기의 로그인 세션이 종료됩니다.</p>

  <h2>6. 안전성 확보 조치</h2>
  <p>API 키와 로그인 비밀값은 앱에 포함하지 않고 서버 환경변수로 관리합니다. 전송 구간에는 HTTPS를 사용하고, 사용자별 데이터 접근을 로그인 세션으로 구분하며, 서버 로그에는 API 키나 인증 헤더 원문을 기록하지 않습니다.</p>

  <h2>7. 문의</h2>
  <p>개인정보 보호 및 데이터 삭제 관련 문의: {contact}</p>

  <h2>8. 방침 변경</h2>
  <p>처리 항목이나 이용 목적이 달라지는 경우 시행 전에 앱 또는 이 페이지를 통해 변경 내용을 안내합니다.</p>
</main>
</body>
</html>"""
