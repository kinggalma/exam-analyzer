"""
기출문제지 PDF 파싱 공용 모듈
- add_exam_ui.py(로컬 관리 도구)와 app.py(클라우드 앱) 양쪽에서 공용으로 사용
- 국가기술자격 기술사 시험문제 표준 양식(1페이지 = 1교시)을 파싱
"""
import re

import pandas as pd
import pdfplumber

CAT1_OPTIONS = [
    "산안법", "건진법", "시설물안전법", "중대재해처벌법", "지특법",
    "가설공사", "건설기계", "안전관리론", "재해유형", "계절재해",
    "콘크리트", "토공", "기초", "강재", "철골",
    "교량", "터널", "건축", "지진", "해체공사",
    "제방 댐 항만", "기타", "시사 이슈 문제",
]

# 키워드 → cat1 자동 매핑 (구체적인 것 먼저, 순서 중요)
_CAT1_RULES = [
    # 법령류
    ("중대재해처벌법",   "중대재해처벌법"),
    ("시설물안전법",     "시설물안전법"),
    ("시설물통합정보",   "시설물안전법"),
    ("시설물의 안전",    "시설물안전법"),
    ("건설기술진흥법",   "건진법"),
    ("건진법",           "건진법"),
    ("지특법",           "지특법"),
    ("산업안전보건법",   "산안법"),
    ("안전보건대장",     "산안법"),
    ("안전관리비",       "산안법"),
    ("휴게시설",         "산안법"),
    ("안전보건관리비",   "산안법"),
    ("화재감시자",       "산안법"),
    ("임시소방",         "산안법"),
    ("위험물질",         "산안법"),
    ("작업중지",         "산안법"),
    # 계절재해
    ("폭염",     "계절재해"),
    ("온열질환", "계절재해"),
    ("동절기",   "계절재해"),
    ("한파",     "계절재해"),
    ("동해",     "계절재해"),
    # 재해유형
    ("밀폐공간",   "재해유형"),
    ("근골격계",   "재해유형"),
    ("건강장해",   "재해유형"),
    ("고령근로",   "재해유형"),
    ("직업병",     "재해유형"),
    ("추락",       "재해유형"),
    ("감전",       "재해유형"),
    # 안전관리론
    ("색채관리",    "안전관리론"),
    ("파지와",      "안전관리론"),
    ("망각",        "안전관리론"),
    ("RMR",         "안전관리론"),
    ("에너지대사율","안전관리론"),
    ("에너지 대사율","안전관리론"),
    ("작업강도",    "안전관리론"),
    ("피로",        "안전관리론"),
    ("하세이",      "안전관리론"),
    ("하인리히",    "안전관리론"),
    ("JSA",         "안전관리론"),
    ("작업안전분석","안전관리론"),
    ("위험성평가",  "안전관리론"),
    ("페일세이프",  "안전관리론"),
    ("풀프루프",    "안전관리론"),
    ("Fail Safe",   "안전관리론"),
    ("Fool Proof",  "안전관리론"),
    ("자기규율",    "안전관리론"),
    ("TBM",         "안전관리론"),
    ("안전관리론",  "안전관리론"),
    # 건설기계
    ("이동식 크레인", "건설기계"),
    ("크레인",        "건설기계"),
    ("굴착기",        "건설기계"),
    ("건설기계",      "건설기계"),
    ("건설장비",      "건설기계"),
    ("펌프카",        "건설기계"),
    # 가설공사
    ("강관비계", "가설공사"),
    ("시스템비계","가설공사"),
    ("비계",     "가설공사"),
    ("동바리",   "가설공사"),
    ("거푸집",   "가설공사"),
    ("가설",     "가설공사"),
    # 터널
    ("NATM",   "터널"),
    ("터널",   "터널"),
    # 해체공사
    ("해체공사", "해체공사"),
    ("해체",     "해체공사"),
    # 철골
    ("철골",     "철골"),
    # 콘크리트
    ("배치 플랜트", "콘크리트"),
    ("배치플랜트",  "콘크리트"),
    ("콘크리트",    "콘크리트"),
    # 토공
    ("보강토",   "토공"),
    ("옹벽",     "토공"),
    ("굴착면",   "토공"),
    ("굴착작업", "토공"),
    ("흙막이",   "토공"),
    ("절토",     "토공"),
    ("성토",     "토공"),
    # 기초
    ("말뚝",  "기초"),
    ("파일",  "기초"),
    # 교량
    ("교량",  "교량"),
    ("교각",  "교량"),
    # 건축
    ("건축",  "건축"),
    # 지진
    ("지진",  "지진"),
    # 제방·댐·항만
    ("댐",    "제방 댐 항만"),
    ("제방",  "제방 댐 항만"),
    ("항만",  "제방 댐 항만"),
    # 시사
    ("시사",  "시사 이슈 문제"),
]


def auto_assign_cat1(text: str) -> str:
    """키워드 매칭으로 cat1 자동 추정. 매칭 실패 시 '기타' 반환."""
    t = str(text)
    for keyword, cat1 in _CAT1_RULES:
        if keyword.lower() in t.lower():
            return cat1
    return "기타"


# ── 문제지 PDF 파서 ───────────────────────────────────────────────────────────
# 국가기술자격 기술사 시험문제 표준 양식: 1페이지 = 1교시, 상단에
# "총 N문제 중 M문제를 선택하여 설명하시오" 안내문, 그 아래 "번호. 문제" 목록.

ROUND_PAT = re.compile(r"제\s*(\d+)\s*회")
SELECT_LINE_PAT = re.compile(r"총\s*\d+\s*문제")
FOOTER_PAGENUM_PAT = re.compile(r"^\d+\s*-\s*\d+$")
QUESTION_START_PAT = re.compile(r"^(\d{1,2})[.\s](.*)$")
PERIOD_HEADER_PAT = re.compile(r"^[\[(]?\s*(\d)\s*교시\s*[\])]?\s*$")


def parse_exam_pdf(source) -> pd.DataFrame:
    """기술사 시험문제지 PDF(교시별 1페이지 형식) → 표준 컬럼 DataFrame."""
    with pdfplumber.open(source) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        round_match = ROUND_PAT.search(full_text)
        if not round_match:
            raise ValueError("PDF에서 회차 번호를 찾을 수 없습니다. (예: '제140회')")
        round_num = int(round_match.group(1))

        rows = []
        for page_idx, page in enumerate(pdf.pages, start=1):
            lines = (page.extract_text() or "").splitlines()

            start = next(
                (i for i, ln in enumerate(lines) if SELECT_LINE_PAT.search(ln)),
                None,
            )
            if start is None:
                continue

            expected_num = 1
            cur_num = None
            cur_parts: list[str] = []

            def flush():
                if cur_num is not None:
                    text = " ".join(cur_parts).strip()
                    rows.append({
                        "회차": round_num,
                        "교시": page_idx,
                        "번호": cur_num,
                        "cat1": auto_assign_cat1(text),
                        "cat2": "",
                        "문제": f"{cur_num}. {text}",
                    })

            for ln in lines[start + 1:]:
                ln = ln.strip()
                if not ln:
                    continue
                if FOOTER_PAGENUM_PAT.match(ln) or ln.startswith(("“채점기준", '"채점기준')):
                    break
                m = QUESTION_START_PAT.match(ln)
                if m and int(m.group(1)) == expected_num:
                    flush()
                    cur_num = expected_num
                    cur_parts = [m.group(2).strip()]
                    expected_num += 1
                elif cur_num is not None:
                    cur_parts.append(ln)
            flush()

    if not rows:
        raise ValueError(
            "문제를 추출하지 못했습니다. 텍스트 기반 PDF(복사 가능한 문제지)인지 확인하세요."
        )

    return pd.DataFrame(rows)


def parse_exam_text(text: str, round_num: int) -> pd.DataFrame:
    """붙여넣은 문제 텍스트 → 표준 컬럼 DataFrame.

    이미지 스캔 PDF처럼 텍스트 추출이 불가능한 자료용 대체 경로.
    OCR 앱 등으로 얻은 텍스트를 그대로 붙여넣으면 됨. 형식:
        1교시
        1. 문제 내용
        2. 문제 내용
           (줄바꿈된 문제는 이어서 적어도 됨)

        2교시
        1. 문제 내용
        ...
    "N교시" 줄로 교시 구분, "번호. 내용" 형식으로 문제 인식.
    """
    rows = []
    period = None
    expected_num = 1
    cur_num = None
    cur_parts: list[str] = []

    def flush():
        if cur_num is not None and period is not None:
            content = " ".join(cur_parts).strip()
            rows.append({
                "회차": round_num,
                "교시": period,
                "번호": cur_num,
                "cat1": auto_assign_cat1(content),
                "cat2": "",
                "문제": f"{cur_num}. {content}",
            })

    for raw_line in text.splitlines():
        ln = raw_line.replace("﻿", "").strip()
        if not ln:
            continue

        pm = PERIOD_HEADER_PAT.match(ln)
        if pm:
            flush()
            period = int(pm.group(1))
            expected_num = 1
            cur_num = None
            cur_parts = []
            continue

        if period is None:
            continue  # 첫 "N교시" 줄이 나오기 전 내용은 무시

        m = QUESTION_START_PAT.match(ln)
        if m and int(m.group(1)) == expected_num:
            flush()
            cur_num = expected_num
            cur_parts = [m.group(2).strip()]
            expected_num += 1
        elif cur_num is not None:
            cur_parts.append(ln)
    flush()

    if not rows:
        raise ValueError(
            "문제를 인식하지 못했습니다. 'N교시' 줄로 구분하고 "
            "각 문제는 '번호. 내용' 형식인지 확인하세요."
        )

    return pd.DataFrame(rows)
