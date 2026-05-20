"""
건설안전기술사 기출문제 분석 프로그램
"""
import os
import json
import urllib.request
import yaml
from yaml.loader import SafeLoader
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────────────────────
EXCEL_PATH = "기출문제(106~138회까지).xlsx"
SIMILARITY_THRESHOLD = 0.30   # 유사 문제 표시 기준


def round_to_year(r: int) -> int:
    """회차 번호로부터 연도 계산 (90회=2010년, 3회씩 증가)"""
    return 2010 + (int(r) - 90) // 3

# 분야 표시명 매핑 (cat1 값 → 표시명)
CAT1_DISPLAY = {
    "산안법": "산업안전보건법",
    "건진법": "건설기술진흥법",
    "시설물안전법": "시설물안전법",
    "중대재해처벌법": "중대재해처벌법",
    "지특법": "지특법",
    "가설공사": "가설공사",
    "건설기계": "건설기계",
    "안전관리론": "안전관리론",
    "재해유형": "재해유형",
    "계절재해": "계절재해",
    "콘크리트": "콘크리트",
    "토공": "토공",
    "기초": "기초",
    "강재": "강재 및 철골",
    "철골": "강재 및 철골",
    "교량": "교량",
    "터널": "터널",
    "건축": "건축",
    "지진": "지진",
    "해체공사": "해체공사",
    "제방 댐 항만": "제방·댐·항만",
    "기타": "기타",
    "시사 이슈 문제": "시사·이슈",
}

# 분야 그룹 (집계 및 분석 시트 기준)
DASHBOARD_CATEGORIES = {
    "산업안전보건법": ["산안법"],
    "건설기술진흥법": ["건진법"],
    "시설물안전법": ["시설물안전법"],
    "중대재해처벌법": ["중대재해처벌법"],
    "지특법": ["지특법"],
    "가설공사": ["가설공사"],
    "건설기계": ["건설기계"],
    "안전관리론": ["안전관리론"],
    "재해유형": ["재해유형"],
    "계절재해": ["계절재해"],
    "콘크리트": ["콘크리트"],
    "토공": ["토공"],
    "기초": ["기초"],
    "강재·철골": ["강재", "철골"],
    "교량": ["교량"],
    "터널": ["터널"],
    "건축": ["건축"],
    "지진": ["지진"],
    "해체공사": ["해체공사"],
    "제방·댐·항만": ["제방 댐 항만"],
    "기타·이슈": ["기타", "시사 이슈 문제"],
}


# ─────────────────────────────────────────────────────────────────────────────
# 인증 설정 로딩
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # 5분 캐시 — Gist 변경 후 최대 5분 내 반영
def get_auth_config():
    """GitHub Gist → Streamlit Secrets → 로컬 config.yaml 순으로 인증 설정 로드"""

    # 1) GitHub Gist 자동 동기화 (gist_id + github_token이 secrets에 있을 때)
    try:
        gist_id = None
        github_token = None
        try:
            gist_id = st.secrets.get("gist_id")
            github_token = st.secrets.get("github_token")
        except Exception:
            pass
        if not gist_id:
            gist_id = os.environ.get("GIST_ID")
            github_token = os.environ.get("GITHUB_TOKEN")

        if gist_id and github_token:
            req = urllib.request.Request(
                f"https://api.github.com/gists/{gist_id}",
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "construction-safety-exam",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                content = data["files"]["config.yaml"]["content"]
                return yaml.safe_load(content)
    except Exception:
        pass

    # 2) Streamlit Cloud 직접 secrets (credentials 항목이 있는 경우)
    try:
        if "credentials" in st.secrets and "cookie" in st.secrets:
            credentials = {"usernames": {}}
            for uname, info in st.secrets["credentials"]["usernames"].items():
                credentials["usernames"][uname] = {
                    "name": info["name"],
                    "email": info.get("email", ""),
                    "password": info["password"],
                }
            return {
                "credentials": credentials,
                "cookie": {
                    "name": st.secrets["cookie"]["name"],
                    "key": st.secrets["cookie"]["key"],
                    "expiry_days": int(st.secrets["cookie"]["expiry_days"]),
                },
            }
    except Exception:
        pass

    # 3) 로컬 개발: config.yaml 파일
    if os.path.exists("config.yaml"):
        with open("config.yaml", encoding="utf-8-sig") as f:
            return yaml.load(f, Loader=SafeLoader)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 데이터 로딩
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_excel(EXCEL_PATH, sheet_name="과년도모음", header=0)
    df.columns = ["구분", "회차", "교시", "번호", "cat1", "cat2", "문제"] + list(df.columns[7:])
    df = df[["회차", "교시", "번호", "cat1", "cat2", "문제"]].dropna(subset=["회차", "문제"])
    df["회차"] = df["회차"].astype(int)
    df["교시"] = df["교시"].astype(int)
    df["번호"] = df["번호"].astype(int)
    df["문제"] = df["문제"].astype(str).str.strip()
    df["cat2"] = df["cat2"].fillna("").astype(str).str.strip()
    df["분야"] = df["cat1"].map(lambda x: CAT1_DISPLAY.get(str(x).strip(), str(x).strip()))
    df["위치"] = df.apply(lambda row: f"{round_to_year(row['회차'])}년 {row['회차']}회 {row['교시']}교시 {row['번호']}번", axis=1)
    df = df.reset_index(drop=True)
    return df


@st.cache_resource
def build_tfidf(df):
    texts = df["문제"].tolist()
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=1)
    matrix = vec.fit_transform(texts)
    return vec, matrix


def find_similar(df, matrix, idx, top_n=10, threshold=SIMILARITY_THRESHOLD):
    row_vec = matrix[idx]
    sims = cosine_similarity(row_vec, matrix).flatten()
    sims[idx] = 0  # 자기 자신 제외
    top_idx = np.argsort(sims)[::-1]
    results = []
    for i in top_idx:
        if sims[i] >= threshold:
            results.append((i, round(float(sims[i]) * 100, 1)))
        if len(results) >= top_n:
            break
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 대쉬보드 데이터 계산
# ─────────────────────────────────────────────────────────────────────────────
def build_dashboard_data(df):
    rounds = sorted(df["회차"].unique())
    records = []
    for label, cats in DASHBOARD_CATEGORIES.items():
        row = {"분야": label}
        total = 0
        for r in rounds:
            cnt = df[(df["회차"] == r) & (df["cat1"].isin(cats))].shape[0]
            row[str(r)] = cnt
            total += cnt
        row["합계"] = total
        records.append(row)
    return pd.DataFrame(records), rounds


# ─────────────────────────────────────────────────────────────────────────────
# UI 헬퍼
# ─────────────────────────────────────────────────────────────────────────────
def highlight_keyword(text, keyword):
    if not keyword:
        return text
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(f"**:red[{keyword}]**", text)


def question_card(row, keyword="", badge="", badge_color="blue"):
    with st.container(border=True):
        cols = st.columns([3, 1])
        with cols[0]:
            st.markdown(f"**{row['위치']}** &nbsp;|&nbsp; {row['분야']} &nbsp;|&nbsp; `{row['cat2']}`")
        with cols[1]:
            if badge:
                st.markdown(f":{badge_color}[{badge}]")
        body = highlight_keyword(row["문제"], keyword)
        st.markdown(body)


# ─────────────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="건설안전기술사 기출문제 분석",
        page_icon="🏗️",
        layout="centered",
    )

    # ── 인증 ──────────────────────────────────────────────────────────────────
    auth_config = get_auth_config()

    if auth_config is None:
        st.error("⚠️ 인증 설정 파일(config.yaml)이 없습니다.")
        st.info("터미널에서 `python setup_users.py`를 실행하여 사용자를 등록하세요.")
        st.stop()

    authenticator = stauth.Authenticate(
        auth_config["credentials"],
        auth_config["cookie"]["name"],
        auth_config["cookie"]["key"],
        auth_config["cookie"]["expiry_days"],
    )

    authenticator.login(location="main", fields={
        "Form name": "건설안전기술사 기출문제 분석 — 로그인",
        "Username": "아이디",
        "Password": "비밀번호",
        "Login": "로그인",
    })

    status = st.session_state.get("authentication_status")

    if status is False:
        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        st.stop()
    elif status is None:
        st.stop()

    # ── 로그인 성공 ────────────────────────────────────────────────────────────
    st.markdown("""
<style>
@media screen and (max-width: 768px) {
    [data-testid="column"] {
        width: 100% !important;
        flex: none !important;
        min-width: 100% !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 13px;
        padding: 8px 6px;
    }
    .stButton > button {
        min-height: 44px;
    }
    .stSelectbox > div, .stTextInput > div > div > input {
        font-size: 16px;
    }
}
</style>
""", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(f"**{st.session_state.get('name', '')}** 님 환영합니다")
        authenticator.logout("로그아웃", location="sidebar")
        st.markdown("---")
        st.caption("📱 홈 화면 추가: 브라우저 메뉴 → '홈 화면에 추가'")

    df = load_data()
    _, matrix = build_tfidf(df)
    min_round = int(df["회차"].min())
    max_round = int(df["회차"].max())

    st.title("🏗️ 건설안전기술사 기출문제 분석 프로그램")
    st.caption(f"{min_round}회 ~ {max_round}회 기출문제 | 유사도 기준: {SIMILARITY_THRESHOLD * 100:.0f}%")

    tab1, tab2, tab3 = st.tabs(["🔍 문제 검색 & 유사 문제", "📋 회차별 문제 목록", "📊 대쉬보드"])

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 1: 검색 & 유사 문제
    # ──────────────────────────────────────────────────────────────────────────
    with tab1:
        st.subheader("문제 검색")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            keyword = st.text_input("키워드 입력", placeholder="예: 비계, 안전난간, TBM, 거푸집...")
        with col2:
            field_options = ["전체"] + sorted(df["분야"].unique().tolist())
            sel_field = st.selectbox("분야 필터", field_options)
        with col3:
            sim_threshold = st.slider("유사도 기준(%)", 20, 90, int(SIMILARITY_THRESHOLD * 100), 5)

        if keyword:
            mask = df["문제"].str.contains(keyword, case=False, na=False) | \
                   df["cat2"].str.contains(keyword, case=False, na=False)
            if sel_field != "전체":
                mask &= df["분야"] == sel_field
            results = df[mask].copy()

            st.markdown(f"---\n**검색 결과: {len(results)}건**")

            if results.empty:
                st.info("검색 결과가 없습니다.")
            else:
                for _, row in results.iterrows():
                    question_card(row, keyword=keyword)

                    idx = row.name
                    sim_results = find_similar(df, matrix, idx, top_n=5, threshold=sim_threshold / 100)

                    if sim_results:
                        with st.expander(f"🔗 유사 문제 {len(sim_results)}건"):
                            for sim_idx, sim_pct in sim_results:
                                sim_row = df.iloc[sim_idx]
                                question_card(sim_row, badge=f"유사도 {sim_pct}%",
                                              badge_color="orange" if sim_pct >= 70 else "blue")
        else:
            st.info("키워드를 입력하면 관련 기출문제와 유사 문제를 함께 보여줍니다.")

            st.markdown("---")
            st.subheader("특정 문제의 유사 문제 탐색")
            col_r, col_p, col_n = st.columns(3)
            with col_r:
                sel_round = st.selectbox("회차", sorted(df["회차"].unique(), reverse=True))
            with col_p:
                periods = sorted(df[df["회차"] == sel_round]["교시"].unique())
                sel_period = st.selectbox("교시", periods)
            with col_n:
                nums = sorted(df[(df["회차"] == sel_round) & (df["교시"] == sel_period)]["번호"].unique())
                sel_num = st.selectbox("번호", nums)

            mask = (df["회차"] == sel_round) & (df["교시"] == sel_period) & (df["번호"] == sel_num)
            target = df[mask]
            if not target.empty:
                row = target.iloc[0]
                st.markdown("#### 선택된 문제")
                question_card(row)

                idx = row.name
                sim_results = find_similar(df, matrix, idx, top_n=10, threshold=sim_threshold / 100)

                st.markdown(f"#### 유사 문제 ({len(sim_results)}건, 유사도 ≥ {sim_threshold}%)")
                if sim_results:
                    for sim_idx, sim_pct in sim_results:
                        sim_row = df.iloc[sim_idx]
                        badge_color = "red" if sim_pct >= 70 else "orange" if sim_pct >= 50 else "blue"
                        question_card(sim_row, badge=f"유사도 {sim_pct}%", badge_color=badge_color)
                else:
                    st.info("유사 문제가 없습니다.")

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2: 회차별 문제 목록
    # ──────────────────────────────────────────────────────────────────────────
    with tab2:
        st.subheader("회차별 문제 전체 목록")
        col1, col2 = st.columns(2)
        with col1:
            sel_round2 = st.selectbox("회차 선택", sorted(df["회차"].unique(), reverse=True), key="tab2_round")
        with col2:
            period_opts = ["전체"] + [f"{p}교시" for p in sorted(df[df["회차"] == sel_round2]["교시"].unique())]
            sel_period2 = st.selectbox("교시", period_opts, key="tab2_period")

        filtered = df[df["회차"] == sel_round2]
        if sel_period2 != "전체":
            p_num = int(sel_period2[0])
            filtered = filtered[filtered["교시"] == p_num]

        filtered = filtered.sort_values(["교시", "번호"])

        st.markdown(f"**{sel_round2}회 — {len(filtered)}문제**")

        show_df = filtered[["위치", "분야", "cat2", "문제"]].rename(
            columns={"위치": "출제위치", "cat2": "세부주제"})
        st.dataframe(show_df, use_container_width=True, hide_index=True,
                     column_config={
                         "문제": st.column_config.TextColumn("문제", width="large"),
                         "세부주제": st.column_config.TextColumn("세부주제", width="medium"),
                     })

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 3: 대쉬보드
    # ──────────────────────────────────────────────────────────────────────────
    with tab3:
        st.subheader("분야별 출제 현황 대쉬보드")

        dash_df, rounds = build_dashboard_data(df)
        round_strs = [str(r) for r in rounds]

        st.markdown(f"### 분야별 누적 출제 문항 수 ({min_round}~{max_round}회)")
        total_sorted = dash_df.sort_values("합계", ascending=True)
        fig_total = px.bar(
            total_sorted, x="합계", y="분야", orientation="h",
            text="합계", color="합계",
            color_continuous_scale="Blues",
            labels={"합계": "출제 문항 수", "분야": ""},
        )
        fig_total.update_traces(textposition="outside")
        fig_total.update_layout(height=600, coloraxis_showscale=False, margin=dict(l=10, r=80))
        st.plotly_chart(fig_total, use_container_width=True)

        st.markdown("### 회차 × 분야 출제 히트맵")

        recent_n = st.slider("최근 N회 표시", 5, len(rounds), min(20, len(rounds)), 5)
        recent_rounds = [str(r) for r in sorted(rounds, reverse=True)[:recent_n]]
        heat_data = dash_df.set_index("분야")[recent_rounds[::-1]]

        fig_heat = px.imshow(
            heat_data.values,
            x=heat_data.columns.tolist(),
            y=heat_data.index.tolist(),
            color_continuous_scale="YlOrRd",
            aspect="auto",
            labels=dict(x="회차", y="분야", color="문항 수"),
            text_auto=True,
        )
        fig_heat.update_layout(height=600, margin=dict(l=10, r=10))
        st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("### 분야별 출제 추이 (회차별 라인 차트)")
        sel_fields = st.multiselect(
            "분야 선택 (복수 선택 가능)",
            dash_df["분야"].tolist(),
            default=["산업안전보건법", "안전관리론", "콘크리트", "토공", "가설공사"],
        )
        if sel_fields:
            trend_data = []
            for _, row in dash_df[dash_df["분야"].isin(sel_fields)].iterrows():
                for r in round_strs:
                    trend_data.append({"회차": int(r), "분야": row["분야"], "문항 수": row[r]})
            trend_df = pd.DataFrame(trend_data)
            fig_trend = px.line(trend_df, x="회차", y="문항 수", color="분야",
                                markers=True, labels={"회차": "회차", "문항 수": "출제 문항 수"})
            fig_trend.update_layout(height=450)
            st.plotly_chart(fig_trend, use_container_width=True)

        st.markdown("---")
        col_pie1, col_pie2 = st.columns(2)

        with col_pie1:
            st.markdown("### 교시별 출제 비율")
            period_counts = df["교시"].value_counts().sort_index()
            fig_pie = px.pie(
                values=period_counts.values,
                names=[f"{p}교시" for p in period_counts.index],
                hole=0.4,
            )
            fig_pie.update_layout(height=350)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_pie2:
            st.markdown("### 분야별 출제 비율 (전체)")
            field_counts = df["분야"].value_counts()
            fig_pie2 = px.pie(
                values=field_counts.values,
                names=field_counts.index,
                hole=0.4,
            )
            fig_pie2.update_layout(height=350)
            st.plotly_chart(fig_pie2, use_container_width=True)

        with st.expander("📋 원본 집계 테이블 보기"):
            show_cols = ["분야", "합계"] + round_strs[-10:][::-1]
            st.dataframe(
                dash_df[show_cols].sort_values("합계", ascending=False),
                use_container_width=True,
                hide_index=True,
            )


if __name__ == "__main__":
    main()
