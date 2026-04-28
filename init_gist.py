"""
최초 1회 실행: GitHub Gist 생성 및 로컬 설정 저장
실행: python init_gist.py
"""
import json
import urllib.request
import urllib.error
import yaml
import os


def main():
    print("=" * 55)
    print("  GitHub Gist 초기 설정 (최초 1회만 실행)")
    print("=" * 55)
    print()

    if not os.path.exists("config.yaml"):
        print("[오류] config.yaml이 없습니다. 먼저 사용자관리.bat을 실행하세요.")
        return

    print("GitHub Personal Access Token이 필요합니다.")
    print()
    print("발급 방법:")
    print("  1. GitHub 로그인 → 오른쪽 상단 프로필 → Settings")
    print("  2. 왼쪽 하단 Developer settings → Personal access tokens → Tokens (classic)")
    print("  3. Generate new token (classic) → Note 입력 → gist 체크 → Generate")
    print()
    token = input("GitHub Token 입력: ").strip()
    if not token:
        print("토큰을 입력하세요.")
        return

    with open("config.yaml", encoding="utf-8-sig") as f:
        content = f.read()

    data = json.dumps({
        "description": "건설안전기술사 기출문제 프로그램 인증 설정 (자동 관리)",
        "public": False,
        "files": {"config.yaml": {"content": content}},
    }).encode()

    req = urllib.request.Request(
        "https://api.github.com/gists",
        data=data,
        method="POST",
        headers={
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
            "User-Agent": "construction-safety-exam",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            gist_id = result["id"]
    except urllib.error.HTTPError as e:
        print(f"[오류] Gist 생성 실패: {e.code} {e.reason}")
        print("토큰 권한(gist)을 확인하세요.")
        return

    with open(".github_token", "w") as f:
        f.write(token)
    with open(".gist_id", "w") as f:
        f.write(gist_id)

    print()
    print(f"Gist 생성 완료! (비공개)")
    print()
    print("=" * 55)
    print("  Streamlit Cloud Secrets에 아래 두 줄을 추가하세요")
    print("  (기존 credentials/cookie 내용은 그대로 유지)")
    print("=" * 55)
    print()
    print(f'gist_id = "{gist_id}"')
    print(f'github_token = "{token}"')
    print()
    print("추가 후 저장하면 설정 완료!")
    print("이후 사용자관리.bat으로 사용자를 추가/변경하면 자동으로 반영됩니다.")


if __name__ == "__main__":
    main()
