"""The printed label grammar - what a 수입신고's paragraph is read as.

Every case here is a shape the live feed prints (1,044,332 labels, 2026-09-14);
the numbers behind the rules are in `core/printed_label.py`.
"""

from app.core.printed_label import printed_names, printed_parts, printed_section, split_list


LABEL = (
    "식품위생법에 의한 한글표시사항\n"
    "제품명: 살라미 엑스트라\n"
    "원재료명 및 함량: 돼지고기39.328%, 돼지지방35.114%, 정제수, 유당(우유), "
    "양념(오레가노, 파프리카, 백후추), 정제소금\n"
    "보관방법 : 냉장보관(0℃~10℃)\n"
    "포장재질 : 저밀도폴리에틸렌\n"
    "내용량: 100g(522kcal)\n"
    "돼지고기, 우유 함유\n"
)


def test_a_section_runs_to_the_next_heading() -> None:
    """A value ends where the label's next heading begins, not at the newline."""
    assert printed_section(LABEL, "storage") == "냉장보관(0℃~10℃)"
    assert printed_section(LABEL, "amount") == "100g(522kcal)"
    assert printed_section(LABEL, "shelf_life") is None
    assert printed_section(None, "amount") is None


def test_a_compound_ingredient_is_one_name() -> None:
    """A comma inside brackets belongs to the ingredient, not to the list.

    `양념(오레가노, 파프리카, 백후추)` is one ingredient; split on every comma it
    becomes three that name no product. The printed amount and the leading
    numbering are dropped, and a name is kept once.
    """
    assert printed_names(printed_section(LABEL, "ingredients")) == [
        "돼지고기",
        "돼지지방",
        "정제수",
        "유당(우유)",
        "양념(오레가노, 파프리카, 백후추)",
        "정제소금",
    ]


def test_a_sentence_in_the_list_is_not_a_name() -> None:
    """Publishers run prose into the list; a part that reads as prose is dropped."""
    printed = (
        "원재료명 : 컬리플라워, 브로콜리, "
        "본제품은 이미 냉동된바 있으니 해동 후 다시 냉동하지 마십시오"
    )
    section = printed_section(printed, "ingredients")
    assert printed_names(section) == ["컬리플라워", "브로콜리"]


def test_origin_and_amount_are_not_part_of_a_name() -> None:
    """`밀가루(미국산) 12%` is 밀가루: the origin and the share are the label's, not the name's."""
    assert printed_names("밀가루(미국산) 12%, ① 설탕(국산), 정제소금") == [
        "밀가루",
        "설탕",
        "정제소금",
    ]


def test_parts_keep_sentences_and_drop_repeats() -> None:
    """주의사항 are sentences, not names - and a label that prints one twice gets one row."""
    assert printed_parts("어린이 손이 닿지 않는 곳에 보관, 개봉 후 빨리, 개봉 후 빨리") == [
        "어린이 손이 닿지 않는 곳에 보관",
        "개봉 후 빨리",
    ]
    assert printed_parts(None) == []
    assert printed_parts(" , , ") == []


def test_every_measured_spelling_of_the_ingredient_heading_is_read() -> None:
    """The heading table is the frequency table, not a memory of it.

    Measured 2026-09-14 over 1,044,332 labels: 원재료명 348,074 · 원재료명및함량
    150,007 · 원료및함량 50,004 · 원료명및함량 47,649 · 원재료및함량 40,539 ·
    원료명 34,189 · 성분및함량 9,188 · 원재료 6,710. The first version of this
    module knew the 원재료 family and not the 원료 one, so 광동 소세지용 시즈닝
    ("원료명 : 제삼인산나트륨,…") had no ingredients at all.
    """
    for heading in (
        "원재료명",
        "원재료명 및 함량",
        "원재료명및함량",
        "원재료 명 및 함량",
        "원재료",
        "원료명",
        "원료 및 함량",
        "원료명및함량",
        "성분 및 함량",
        "7. 원료 및 함량",
        "* 원재료명",
    ):
        printed = f"{heading} : 제삼인산나트륨, 정제소금 보관방법 : 실온"
        assert printed_names(printed_section(printed, "ingredients")) == [
            "제삼인산나트륨",
            "정제소금",
        ], heading


def test_a_word_that_starts_like_a_heading_is_not_one() -> None:
    """원료원산지 (1,442 labels) and 성분(재질) (1,303) are not the ingredient list.

    A token is a heading when its normalised form is in the measured table and
    never because it starts with one - the prefix rule read 원료원산지 as the
    ingredient section and returned a country.
    """
    printed = "원료원산지 : 중국산 원재료명 : 정제수, 설탕"
    assert printed_section(printed, "ingredients") == "정제수, 설탕"
    assert printed_section("성분(재질) : 폴리프로필렌", "ingredients") is None


def test_a_section_ends_at_a_heading_the_table_measured() -> None:
    """Ending only at a remembered heading ran the next section into the list."""
    printed = (
        "원료명 : 정제수, 설탕 수입판매업소의 명칭 : (주)수입사 "
        "선하증권(B/L)번호 : ABC123 반품 및 교환장소 : 구입처"
    )
    assert printed_section(printed, "ingredients") == "정제수, 설탕"


def test_every_bracket_pair_holds_a_list_together() -> None:
    """A comma inside any bracket the registries use belongs to the name, not to the list.

    Measured 2026-09-15: 건기식 원재료 lists carry `{` on 224 rows, `[` on 333
    and `<` on 93, and a splitter that counted only `()` cut
    유산균{...100,000,000,000개/g 이상, 희석제(옥수수전분) 적량} into four fragments
    that name no material.
    """
    value = (
        "유산균{LACTOBACILLUS PLANTARUM, 100,000,000,000개/g 이상, 희석제(옥수수전분) 적량},"
        "혼합 유산균분말[비피도박테리움, 락토바실러스],"
        "<비타민C 100%>,"
        "혼합제제(밀가루, 정제수)"
    )
    assert split_list(value) == [
        "유산균{LACTOBACILLUS PLANTARUM, 100,000,000,000개/g 이상, 희석제(옥수수전분) 적량}",
        "혼합 유산균분말[비피도박테리움, 락토바실러스]",
        "<비타민C 100%>",
        "혼합제제(밀가루, 정제수)",
    ]


def test_a_thousands_comma_is_not_a_separator() -> None:
    """`100,000,000,000개/g` is one quantity, wherever it sits.

    A digit on the left and exactly three on the right is the thousands
    separator all five lists use (279 + 53 + 5 rows, 2026-09-15); a comma
    between a digit and anything else still ends an item.
    """
    assert split_list("생균 100,000,000개/g 이상,희석제") == ["생균 100,000,000개/g 이상", "희석제"]
    assert split_list("비타민A 1,대두유") == ["비타민A 1", "대두유"]


def test_the_full_width_punctuation_reads_the_same() -> None:
    """The portals print the full-width forms too - one list, whichever keyboard wrote it."""
    assert split_list("치즈（우유，유산균），밀가루") == ["치즈（우유，유산균）", "밀가루"]


def test_a_value_that_is_no_list_is_no_items() -> None:
    """A non-string or empty value is an empty list, the same as no list at all."""
    assert split_list(None) == []
    assert split_list("") == []
    assert split_list("  ,  ,") == []
