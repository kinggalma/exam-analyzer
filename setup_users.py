"""
사용자 관리 스크립트 — 변경 시 GitHub Gist 자동 동기화
실행: python setup_users.py
"""
import yaml
import os
import secrets
import json
import urllib.request
import urllib.error
from streamlit_authenticator.utilities.hasher import Hasher

CONFIG_FILE = "config.yaml"
TOKEN_FILE = ".github_token"
GIST_FILE = ".gist_id"


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8-sig") as f:
            return yaml.safe_load(f)
    return {
        "credentials": {"usernames": {}},
        "cookie": {
            "name": "construction_safety_exam",
            "key": secrets.token_hex(32),
            "expiry_days": 30,
        },
    }


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    print("  → config.yaml 저장 완료")
    sync_to_gist(config)


def sync_to_gist(config):
    """변경된 config를 GitHub Gist에 자동 동기화"""
    if not os.path.exists(TOKEN_FILE) or not os.path.exists(GIST_FILE):
        return

    with open(TOKEN_FILE) as f:
        token = f.read().strip()
    with open(GIST_FILE) as f:
        gist_id = f.read().strip()

    content = yaml.dump(config, allow_unicode=True, default_flow_style=False)
    data = json.dumps({
        "files": {"config.yaml": {"content": content}}
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/gists/{gist_id}",
        data=data,
        method="PATCH",
        headers={
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
            "User-Agent": "construction-safety-exam",
        },
    )
    try:
        urllib.request.urlopen(req)
        print("  → GitHub Gist 동기화 완료 (클라우드에 즉시 반영)")
    except urllib.error.HTTPError as e:
        print(f"  [경고] Gist 동기화 실패: {e.code}. Gist초기설정.bat을 다시 실행하세요.")


def hash_password(plain):
    return Hasher([plain]).generate()[0]


def add_user(config):
    print("\n[사용자 추가]")
    username = input("  아이디: ").strip()
    if not username:
        print("  아이디를 입력하세요.")
        return
    if username in config["credentials"]["usernames"]:
        print(f"  이미 존재하는 아이디: {username}")
        return
    name = input("  이름(표시명): ").strip()
    email = input("  이메일 (선택): ").strip()
    password = input("  비밀번호: ").strip()
    if not password:
        print("  비밀번호를 입력하세요.")
        return
    config["credentials"]["usernames"][username] = {
        "name": name,
        "email": email,
        "password": hash_password(password),
    }
    save_config(config)
    print(f"  사용자 '{username}' ({name}) 추가 완료!")


def list_users(config):
    users = config["credentials"]["usernames"]
    print("\n[등록된 사용자 목록]")
    if not users:
        print("  등록된 사용자가 없습니다.")
        return
    for uname, info in users.items():
        print(f"  - {uname:15s} | {info.get('name',''):10s} | {info.get('email','')}")


def delete_user(config):
    list_users(config)
    print("\n[사용자 삭제]")
    username = input("  삭제할 아이디: ").strip()
    if username not in config["credentials"]["usernames"]:
        print(f"  존재하지 않는 아이디: {username}")
        return
    confirm = input(f"  '{username}'을(를) 삭제하시겠습니까? (y/N): ").strip().lower()
    if confirm == "y":
        del config["credentials"]["usernames"][username]
        save_config(config)
        print(f"  사용자 '{username}' 삭제 완료!")
    else:
        print("  취소했습니다.")


def change_password(config):
    print("\n[비밀번호 변경]")
    username = input("  아이디: ").strip()
    if username not in config["credentials"]["usernames"]:
        print(f"  존재하지 않는 아이디: {username}")
        return
    new_password = input("  새 비밀번호: ").strip()
    if not new_password:
        print("  비밀번호를 입력하세요.")
        return
    config["credentials"]["usernames"][username]["password"] = hash_password(new_password)
    save_config(config)
    print(f"  '{username}' 비밀번호 변경 완료!")


def main():
    print("=" * 50)
    print("  건설안전기술사 기출문제 프로그램 — 사용자 관리")
    gist_ready = os.path.exists(TOKEN_FILE) and os.path.exists(GIST_FILE)
    if gist_ready:
        print("  [자동 동기화 활성화 — 변경 즉시 클라우드 반영]")
    else:
        print("  [Gist 미설정 — Gist초기설정.bat 실행 시 자동화 가능]")
    print("=" * 50)

    config = load_config()

    while True:
        print("\n1. 사용자 추가")
        print("2. 사용자 목록 보기")
        print("3. 사용자 삭제")
        print("4. 비밀번호 변경")
        print("5. 종료")

        choice = input("\n선택 (1~5): ").strip()

        if choice == "1":
            add_user(config)
        elif choice == "2":
            list_users(config)
        elif choice == "3":
            delete_user(config)
        elif choice == "4":
            change_password(config)
        elif choice == "5":
            print("\n종료합니다.")
            break
        else:
            print("  1~5 중에서 선택하세요.")


if __name__ == "__main__":
    main()
