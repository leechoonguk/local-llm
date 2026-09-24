# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import re
from collections.abc import Container, Mapping


# ============================================================
# Constants
# ============================================================

# A printed label is a paragraph, and reading it is a process, not a portal's
# dialect - which is why this lives in `core` beside the other mechanics rather
# than in a schema (whose surface is its Pydantic classes) or in a service
# (which may not import another). Two derivations read the same paragraph - the
# label family and the ingredient split - and a second copy of these rules would
# be two answers to "what did this label say".

# What the 수입신고별 한글표시사항 feed publishes is the label as it is printed -
# one paragraph per declaration, 1,044,332 of 1,055,682 rows filled (98.9 %),
# up to 8,602 characters (2026-09-14). Nothing in it is a field: every value a
# reader wants is a heading followed by a colon.
#
# **The headings are measured, not guessed.** Every `text:` token of all
# 1,044,332 labels was counted (2026-09-14): 59,270 distinct forms, of which 289
# occur 3,000 times or more and are the table below. The first version of this
# module listed headings from memory and missed 원료명 (34,189 labels) and
# 원료및함량 (50,004) outright - 광동 소세지용 시즈닝 prints "원료명 :" and had no
# ingredients at all - which is what a measured table exists to prevent.
#
# A token is a heading when its **normalised** form - whitespace removed, a
# printed number ("7."), a bullet ("*", "※") stripped - is in this table, and
# never otherwise: 원료원산지 (1,442) and 성분(재질) (1,303) start with a heading
# and are not one, and a colon in prose ("12:30") ends nothing.
# The punctuation every joined list of this repository is written with, measured
# over all five lists (the table in `split_list`). Brackets are counted in pairs
# so a comma inside a compound ingredient is not a separator; a comma between
# digits is a thousands separator and not one either.
OPENING_BRACKETS = "([{<（［"
CLOSING_BRACKETS = ")]}>）］"
LIST_SEPARATORS = ",，"
THOUSANDS_DIGITS = 3

SECTIONS: dict[str, tuple[str, ...]] = {
    # 원재료 - the list this whole module exists for. Counts, 2026-09-14:
    # 원재료명 348,074 · 원재료명및함량 150,007 · 원료및함량 50,004 ·
    # 원료명및함량 47,649 · 원재료및함량 40,539 · 원료명 34,189 ·
    # 성분및함량 9,188 · 원재료 6,710 · 성분 3,858 · 성분명및함량 3,401.
    "ingredients": (
        "원재료명및함량",
        "원재료명및성분명",
        "원재료명또는성분명",
        "원재료명",
        "원재료및함량",
        "원재료명및함량",
        "원재료",
        "원료명및함량",
        "원료명및성분",
        "원료및함량",
        "원료명",
        "성분명및함량",
        "성분및함량",
        "성분명",
        "성분",
        "재료명",
    ),
    # 알레르기 유발물질 34,561 · 알레르기표시 6,509 · 알레르기 3,390.
    "allergen": (
        "알레르기유발물질",
        "알레르기유발성분",
        "알레르기표시",
        "알레르기성분",
        "알레르기",
    ),
    # 보관방법 628,771 · 보관및취급방법 17,225 · 보관조건 9,163 · 보존방법 3,003.
    "storage": (
        "보관방법",
        "보관및취급방법",
        "보관및취급",
        "보관조건",
        "보관기준",
        "보존방법",
        "보존기준",
        "보관",
    ),
    # 포장재질 543,636 · 재질 142,861 · 용기포장재질 69,238 · 용기재질 12,347.
    "packaging": (
        "포장재질",
        "용기포장재질",
        "용기(포장)재질",
        "용기·포장재질",
        "포장재질(내면)",
        "내포장재질",
        "용기재질",
        "재질명",
        "재질",
        "포장재",
    ),
    # 내용량 590,587 · 중량 137,578 · 총내용량 4,104 · 용량 10,463.
    "amount": ("내용량및알코올", "총내용량", "내용량", "중량", "용량"),
    # 소비기한 596,900 · 유통기한 10,976 · 품질유지기한 47,946.
    "shelf_life": ("소비기한", "유통기한", "품질유지기한", "품질보증기간"),
    # 식품유형 340,053 · 식품의유형 100,613 · 제품유형 59,364 · 유형 4,312.
    "product_type": (
        "축산물가공품의유형",
        "식품의유형",
        "제품의유형",
        "식품유형",
        "제품유형",
        "제품종류",
        "유형",
    ),
    # 주의사항 211,296 · 경고 47,572 · 보관상주의 28,729 · 섭취시주의사항 21,916.
    "caution": (
        "섭취시주의사항",
        "취급시주의사항",
        "사용상주의사항",
        "사용시주의사항",
        "조리시주의사항",
        "취급주의사항",
        "보관상주의사항",
        "보관상유의사항",
        "보관상주의",
        "주의사항",
        "주의",
        "경고",
    ),
    # 섭취방법 8,016 · 섭취량및섭취방법 13,362 · 1일섭취량 8,866 · 사용방법 18,852.
    "intake": ("섭취량및섭취방법", "1일섭취량", "섭취방법", "섭취량", "사용방법"),
    # 영양정보 186,052 · 영양성분 10,926 · 기능정보 8,119 · 기능성분 4,744.
    "nutrition": (
        "영양·기능정보",
        "영양정보",
        "영양성분",
        "기능정보",
        "기능성내용",
        "기능성분",
    ),
    # 제품명 935,819 · 품명 45,126 · 상품명 5,092.
    "product_name": ("제품명", "품명", "상품명"),
    # 원산지 890,571 · 제조국 40,589 · 가공국 3,933 · 수출국 4,219.
    "origin": ("생산국명(또는원산지)", "원산지", "제조국명", "제조국", "가공국", "수출국"),
}

# Every other heading the feed prints 3,000 times or more (2026-09-14). None of
# them is read; all of them **end** the section in front of them, which is the
# only job a heading has here.
OTHER_HEADINGS = (
    "반품및교환장소",
    "반품및교환처",
    "반품및교환",
    "반품또는교환장소",
    "반품또는교환",
    "반품교환업무소재지",
    "반품교환",
    "반품/교환",
    "반품처",
    "수입원및소재지",
    "수입원및판매원",
    "수입원/판매원",
    "수입원소재지",
    "수입/판매원",
    "수입및판매원",
    "수입판매업소의명칭",
    "수입판매업소의소재지",
    "수입판매업소의연락처",
    "수입판매업소의소재",
    "수입판매업소명및소재지",
    "수입판매업소명",
    "수입판매업소",
    "수입업소명및소재지",
    "수입업소및소재지",
    "수입업소소재지",
    "수입업소명",
    "수입업소",
    "수입업체명",
    "수입업자",
    "수입판매원",
    "수입회사",
    "수입처",
    "수입자",
    "수입사",
    "수입원",
    "제조년월일",
    "제조연월일",
    "제조일자",
    "제조일",
    "제조년월",
    "제조번호",
    "제조위탁자",
    "제조업소명",
    "제조업소",
    "제조업체",
    "제조공장명",
    "제조공장",
    "제조회사명",
    "제조회사",
    "제조자명",
    "제조자",
    "제조사명",
    "제조사",
    "제조원",
    "해외제조업소명",
    "해외제조업소",
    "영업자의명칭(상호)",
    "영업자의명칭(상호)소재지",
    "영업자의명칭",
    "영업자의소재지",
    "영업자의연락처",
    "영업장의명칭및소재지",
    "업소명및소재지",
    "업소명",
    "소재지",
    "소재",
    "주소",
    "연락처",
    "전화번호",
    "전화",
    "홈페이지",
    "고객상담실",
    "고객센터",
    "소비자상담실",
    "선하증권(b/l)번호",
    "선하증권번호",
    "이력번호",
    "식품이력추적관리번호",
    "수입유통식별번호",
    "위생허가번호",
    "위생등록번호",
    "공장등록번호",
    "등록공장번호",
    "등록공장명",
    "등록공장",
    "영업신고번호",
    "유기농인증번호",
    "인증번호",
    "인증기관",
    "허가번호",
    "등록번호",
    "제품번호",
    "로트번호",
    "품번",
    "모델명",
    "규격",
    "식육의종류와부위명",
    "식육의종류및부위명",
    "조리시의해동방법및조리또는가열처리법",
    "조리시의해동방법",
    "조리시해동방법",
    "조리또는가열처리방법",
    "해동및조리방법",
    "조리및해동방법",
    "해동방법",
    "조리방법",
    "관리방법",
    "사용또는보존기준",
    "사용및보존기준",
    "사용기준",
    "사용용도",
    "식품용도안",
    "식품용단어또는도안",
    "식품용",
    "용도",
    "도안",
    "생산년도",
    "생산연도",
    "생산일자",
    "생산년월일",
    "생산연월일",
    "포장일자",
    "포장년월일",
    "포장연월일",
    "포장일",
    "병입년월일",
    "내포장",
    "외포장",
    "겉포장",
    "뚜껑",
    "용기",
    "판매원",
    "기타",
    "함량",
    "감미료",
    "알콜분및용량",
    "알콜도수및용량",
    "1회분량",
    "1일섭취량당함량",
    "%영양성분기준치",
    "부정·불량식품신고표시",
    "부정불량식품신고표시",
    "부정불량식품신고",
    "부정,불량식품신고",
    "부정불량식품신고는국번없이1399",
    "tel",
    "tel.",
    "exp",
    "lot",
    "manufacturer",
    "productiondate",
    "productname",
    "expirydate",
    "netweight",
    "http",
)

# Every heading, in one set: what a section ends at.
ALL_HEADINGS = frozenset(
    token for tokens in (*SECTIONS.values(), OTHER_HEADINGS) for token in tokens
)

# How a heading is found: every colon is a candidate, and what precedes it is
# read back word by word - "정제수, 설탕 수입판매업소의 명칭 :" offers
# "설탕 수입판매업소의 명칭" first and "명칭" last, and the table answers
# 수입판매업소의명칭. Words are never cut in the middle, which is what keeps
# 원료원산지 from reading as 원산지.
_COLON = re.compile(r"[:：]")
_LOOKBACK = 24
_WORD = re.compile(r"\S+")
_TOKEN_NOISE = re.compile(r"^[\s*※・·\-]+|\s+")
_TOKEN_NUMBER = re.compile(r"^\d{1,2}\.")

# What a name is not: the printed amount (`41.66%`), the origin the publisher
# appends (`(국산)`), and the numbering of a compound ingredient (`① 가공치즈`).
_PERCENT = re.compile(r"\s*\d+(?:[.,]\d+)?\s*%")
_ORIGIN = re.compile(r"\((?:국산|수입산|[가-힣]{2,8}산)\)")
_LEADING = re.compile(r"^[①-⑳\d]+[.)]?\s*")

# The one section a label prints without a heading: the allergen sentence
# (`돼지고기, 우유 함유`), which 449,609 of 1,055,682 labels carry (2026-09-14).
# It ends whatever section it follows, or 내용량 swallows it.
#
# The names are joined by commas, never by spaces alone: a space-joined run
# swallowed the sentence in front of it - "주의사항 : 직사광선을 피해 보관 천일염
# 함유" lost its whole 주의사항 - because prose reads as a list of names when
# space is a separator. Only the last word before 함유 may stand alone.
_NAME = r"[가-힣][가-힣()\[\]]*"
_CONTAINS = re.compile(r"(?:(?<=\s)|^)(?:" + _NAME + r"\s*,\s*)*" + _NAME + r"\s*함유")

# A name this long, or with this many spaces in it, is a sentence the publisher
# ran into the list ("본제품은 이미 냉동된바 있으니…").
NAME_LIMIT = 40
NAME_SPACES = 3

# Whitespace, collapsed in a section's body once it has been cut out.
_SPACE = re.compile(r"\s+")


# ============================================================
# Functions
# ============================================================


def keep_newest(
    held: dict[str, tuple[str, Mapping[str, object]]],
    key: str,
    stamp: str,
    record: Mapping[str, object],
) -> None:
    """Keep, per key, the record with the newest stamp - the label a product is read from.

    A product is declared 3.6 times on average and 1,226 times at the widest,
    and 101,150 of the 142,370 products with more than one declaration print the
    **same** paragraph every time (measured 2026-09-14). One product has one
    printed label, so every import derivation of the label family reads the same
    declaration: the newest 처리일자 that printed anything. The rule lives here
    because four derivations need it and a service may not import another.
    """
    seen = held.get(key)
    if seen is not None and seen[0] >= stamp:
        return
    held[key] = (stamp, record)


def printed_section(text: str | None, section: str) -> str | None:
    """The printed section under one of `section`'s headings, or None.

    The label is one paragraph of `heading : value` runs, so a section is what
    sits between its own heading and the next heading **of the measured table**,
    or the allergen sentence, whichever comes first.

    **A newline is not an end.** The feed wraps a long list: 61,472 labels end
    the 원재료 line on a comma and continue on the next, 14,902 of them indented
    (measured 2026-09-14). Ending at the newline cut 광동 소세지용 시즈닝 at
    "향신료(계피가루,감초분말" - four ingredients lost and a bracket left open,
    which is what the 2,725 unbalanced `raw_material_text` rows were. A wrapped
    line is a continuation; a line that starts a heading ends the section at that
    heading anyway.

    Measured the same day: ending only at a heading this module knew by memory
    left 311,938 labels with no 원재료 section at all, and 82,412 of them print
    one under a heading the memory list never had.
    """
    if not text:
        return None
    wanted = SECTIONS[section]
    headings = _headings(text)
    for index, (_, end, token) in enumerate(headings):
        if token not in wanted:
            continue
        rest = text[end:]
        stops = [len(rest)]
        for other_start, _, _ in headings[index + 1 :]:
            stops.append(other_start - end)
            break
        contains = _CONTAINS.search(rest)
        if contains is not None:
            stops.append(contains.start())
        body = _SPACE.sub(" ", rest[: min(stops)])
        return body.strip(" ·-–—,") or None
    return None


def printed_names(text: str | None) -> list[str]:
    """A printed 원재료 section as a list of names, in the order the label prints them.

    Split on commas **outside brackets**, because a compound ingredient carries
    its own list (`치즈(우유, 유크림, 유산균)`) and splitting inside it turns one
    ingredient into three that name no product. Then the amount, the origin and
    the numbering are dropped, and what is left is a name unless it reads as a
    sentence.
    """
    if not text:
        return []
    found: list[str] = []
    for part in split_list(text):
        name = _LEADING.sub("", part)
        name = _ORIGIN.sub("", _PERCENT.sub("", name)).strip(" ·-–—:;,")
        if not _is_name(name) or name in found:
            continue
        found.append(name)
    return found


def printed_parts(text: str | None) -> list[str]:
    """A printed section as its comma-separated parts, whatever they read as.

    The sentences a label prints under 주의사항 are parts too - "어린이 손이 닿지
    않는 곳에 보관" is one of them - so the name rule that keeps an ingredient
    list clean would drop exactly the rows that table exists for. Numbering and
    the amount are still dropped, because those belong to the printing.
    """
    if not text:
        return []
    found: list[str] = []
    for part in split_list(text):
        cleaned = _PERCENT.sub("", _LEADING.sub("", part)).strip(" ·-–—:;,")
        if not cleaned or cleaned in found:
            continue
        found.append(cleaned)
    return found


def _headings(text: str) -> list[tuple[int, int, str]]:
    """Every measured heading in the paragraph, as (start, end of colon, token)."""
    found: list[tuple[int, int, str]] = []
    for match in _COLON.finditer(text):
        before = text[max(0, match.start() - _LOOKBACK) : match.start()]
        if "\n" in before:
            before = before[before.rindex("\n") + 1 :]
        words = [(word.start(), word.group()) for word in _WORD.finditer(before)]
        offset = match.start() - len(before)
        for index in range(len(words)):
            token = _normalised(" ".join(word for _, word in words[index:]))
            if token in ALL_HEADINGS:
                found.append((offset + words[index][0], match.end(), token))
                break
    return found


def _normalised(token: str) -> str:
    """A printed heading as the table spells it: no numbering, no bullet, no space."""
    return _TOKEN_NUMBER.sub("", _TOKEN_NOISE.sub("", token.strip())).lower()


def split_list(value: object, separators: Container[str] = LIST_SEPARATORS) -> list[str]:
    """A joined list as its items, in the order sent - the one splitter every list uses.

    Four registries punctuate a 원재료 list, and a splitter that knows one of
    them turns an ingredient into fragments that name nothing. Measured
    2026-09-15 over the five lists this repository reads (건기식 기능성 46,084
    filled / 기타 41,764 / 캡슐 12,482, C002 1,072,171, C006 567,643):

    | punctuation | 기능성 | 기타 | 캡슐 | C002 | C006 |
    | --- | --- | --- | --- | --- | --- |
    | `(` | 37,987 | 21,613 | 230 | 195,889 | 12,470 |
    | `[` | 137 | 193 | 3 | 84 | 0 |
    | `{` | 118 | 103 | 3 | 1 | 0 |
    | `<` | 22 | 71 | 0 | 1 | 0 |
    | `1,000` | 279 | 53 | 0 | 5 | 0 |

    So **every bracket pair counts depth** - `()`, `[]`, `{}`, `<>` and the
    full-width `（）`, `［］` - and a comma **between digits** is not a
    separator: 유산균{LACTOBACILLUS ..., 100,000,000,000개/g 이상, 희석제(옥수수전분)
    적량} is one 기능성 원재료, and counting only `()` cut it into four fragments
    that resolve to nothing.

    `separators` is the one thing a caller may say: a HACCP 알레르기 string is
    separated by `·`, `/` and a pasted newline as well as by a comma (measured
    2026-09-13 over its 14,664 values), and that is which characters end an
    item, not how the depth is counted. Both comma forms separate by default
    (`,` and the full-width `，`), each item is
    stripped at its ends, and the empty ones are dropped; inside, an item is
    kept as sent - a reading is not the place to decide what the portal meant.
    An empty or non-string value is an empty list, the same as no list.
    """
    if not isinstance(value, str):
        return []
    items: list[str] = []
    depth = 0
    start = 0
    for index, character in enumerate(value):
        if character in OPENING_BRACKETS:
            depth += 1
        elif character in CLOSING_BRACKETS:
            depth = max(depth - 1, 0)
        elif character in separators and depth == 0 and not _inside_number(value, index):
            items.append(value[start:index])
            start = index + 1
    items.append(value[start:])
    return [item for item in (part.strip() for part in items) if item]


def _inside_number(value: str, index: int) -> bool:
    """Whether the comma at this position groups a number rather than ending an item.

    `100,000,000,000개/g` is one quantity: a digit on the left and three digits
    on the right is the thousands separator every one of these registries uses,
    and no measured item ends in a digit and begins with exactly three
    (2026-09-15: 279 + 53 + 5 rows carry the form).
    """
    return (
        index > 0
        and value[index - 1].isdigit()
        and value[index + 1 : index + 4].isdigit()
        and len(value[index + 1 : index + 4]) == THOUSANDS_DIGITS
    )


def _is_name(name: str) -> bool:
    """Whether a part reads as an ingredient name rather than a sentence."""
    # One character is a name here: 밀, 콩, 쌀 and 물 are printed exactly like
    # that, and the allergen line of a wheat product is the single word 밀.
    return 0 < len(name) <= NAME_LIMIT and ":" not in name and name.count(" ") <= NAME_SPACES
