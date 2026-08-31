"""replace mfds integration fields: every response column is configuration

Revision ID: 62
Revises: 61
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "62"
down_revision: str | Sequence[str] | None = "61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

# REQUEST — (key, wire_path, value_source, value, value_type, required, description, sensitive, ordinal)
#
# Shared columns carry the same key as their RESPONSE row: MAKER_NM is
# `maker_name` on the way out and on the way back, so one concept has one name in
# this operation's contract.
REQUEST_ROWS = [
    ('service_key', 'serviceKey', 'SECRET', None, 'STRING', True,
     '인증키 (URL Encode) — 공공데이터포털에서 발급 받은 인증키', True, 0),
    ('page_no', 'pageNo', 'CALLER', None, 'INTEGER', True,
     '페이지 번호 (예: 1) — 호출자가 반드시 전달한다', False, 1),
    ('num_of_rows', 'numOfRows', 'CALLER', None, 'INTEGER', True,
     '한 페이지 결과수 (예: 3) — 호출자가 반드시 전달한다', False, 2),
    ('type', 'type', 'LITERAL', 'json', 'STRING', False,
     '응답데이터 형식(xml/json) default : xml', False, 3),
    ('food_name', 'FOOD_NM_KR', 'CALLER', None, 'STRING', False,
     '식품명 (예: 국밥_돼지머리)', False, 4),
    ('research_ymd', 'RESEARCH_YMD', 'CALLER', None, 'STRING', False,
     '데이터생성일자 (예: 2017-12-31)', False, 5),
    ('maker_name', 'MAKER_NM', 'CALLER', None, 'STRING', False,
     '업체명', False, 6),
    ('category_major_name', 'FOOD_CAT1_NM', 'CALLER', None, 'STRING', False,
     '식품대분류명 (예: 밥류)', False, 7),
    ('item_report_no', 'ITEM_REPORT_NO', 'CALLER', None, 'STRING', False,
     '품목제조보고번호 (예: 19760342001155)', False, 8),
    ('update_date', 'UPDATE_DATE', 'CALLER', None, 'STRING', False,
     '데이터수정일자 (예: 2025-01-23)', False, 9),
    ('item_class_name', 'DB_CLASS_NM', 'CALLER', None, 'STRING', False,
     '품목대표/상용제품 (예: 품목대표)', False, 10),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# One row per provider column, from the response contract sheet
# (출력메세지_식품영양성분DB정보.xlsx: paramtrNm / paramtrDc / paramtrTy). The
# operation maps a page, so `wire_path` is a pointer **relative to one element**
# of /body/items — the page position is the operation's `response_root`, not part
# of every row.
#
# The key is derived from `paramtrDc`, not from the wire name: 157 of these columns
# are `AMT_NUM<n>`, which names nothing. The unit the sheet prints becomes the
# suffix (kcal, g, mg, ug, pct), which is what makes the pairs distinguishable —
# 리놀레산 ships in both (g) and (mg), and 비타민 A in both (μg RAE) and (μg).
#
# `food_name` is the one required row: every record the provider calls a food has a
# name, so a page whose elements lack it is not the page this operation contracted
# for. An empty page maps to an empty list and is a valid answer.
RESPONSE_ROWS = [
    ('row_no', '/NUM', '번호', False, 0),
    ('food_code', '/FOOD_CD', '식품코드', False, 1),
    ('food_name', '/FOOD_NM_KR', '식품명', True, 2),
    ('data_group_code', '/DB_GRP_CM', '데이터구분코드', False, 3),
    ('data_group_name', '/DB_GRP_NM', '데이터구분명', False, 4),
    ('item_class_code', '/DB_CLASS_CM', '품목대표/상용제품 코드', False, 5),
    ('item_class_name', '/DB_CLASS_NM', '품목대표/상용제품', False, 6),
    ('food_origin_code', '/FOOD_OR_CD', '식품기원코드', False, 7),
    ('food_origin_name', '/FOOD_OR_NM', '식품기원명', False, 8),
    ('category_major_code', '/FOOD_CAT1_CD', '식품대분류코드', False, 9),
    ('category_major_name', '/FOOD_CAT1_NM', '식품대분류명', False, 10),
    ('reference_food_code', '/FOOD_REF_CD', '대표식품코드', False, 11),
    ('reference_food_name', '/FOOD_REF_NM', '대표식품명', False, 12),
    ('category_medium_code', '/FOOD_CAT2_CD', '식품중분류코드', False, 13),
    ('category_medium_name', '/FOOD_CAT2_NM', '식품중분류명', False, 14),
    ('category_minor_code', '/FOOD_CAT3_CD', '식품소분류코드', False, 15),
    ('category_minor_name', '/FOOD_CAT3_NM', '식품소분류명', False, 16),
    ('category_detail_code', '/FOOD_CAT4_CD', '식품세분류코드', False, 17),
    ('category_detail_name', '/FOOD_CAT4_NM', '식품세분류명', False, 18),
    ('nutrient_basis_amount', '/SERVING_SIZE', '영양성분함량기준량', False, 19),
    ('energy_kcal', '/AMT_NUM1', '에너지(kcal)', False, 20),
    ('moisture_g', '/AMT_NUM2', '수분(g)', False, 21),
    ('protein_g', '/AMT_NUM3', '단백질(g)', False, 22),
    ('fat_g', '/AMT_NUM4', '지방(g)', False, 23),
    ('ash_g', '/AMT_NUM5', '회분(g)', False, 24),
    ('carbohydrate_g', '/AMT_NUM6', '탄수화물(g)', False, 25),
    ('sugar_g', '/AMT_NUM7', '당류(g)', False, 26),
    ('dietary_fiber_g', '/AMT_NUM8', '식이섬유(g)', False, 27),
    ('calcium_mg', '/AMT_NUM9', '칼슘(mg)', False, 28),
    ('iron_mg', '/AMT_NUM10', '철(mg)', False, 29),
    ('phosphorus_mg', '/AMT_NUM11', '인(mg)', False, 30),
    ('potassium_mg', '/AMT_NUM12', '칼륨(mg)', False, 31),
    ('sodium_mg', '/AMT_NUM13', '나트륨(mg)', False, 32),
    ('vitamin_a_ug_rae', '/AMT_NUM14', '비타민 A(μg RAE)', False, 33),
    ('vitamin_a_ug', '/AMT_NUM15', '비타민 A(μg)', False, 34),
    ('retinol_ug', '/AMT_NUM16', '레티놀(μg)', False, 35),
    ('beta_carotene_ug', '/AMT_NUM17', '베타카로틴(μg)', False, 36),
    ('vitamin_b1_mg', '/AMT_NUM18', '비타민 B1(mg)', False, 37),
    ('vitamin_b2_mg', '/AMT_NUM19', '비타민 B2(mg)', False, 38),
    ('niacin_mg', '/AMT_NUM20', '니아신(mg)', False, 39),
    ('vitamin_c_mg', '/AMT_NUM21', '비타민 C(mg)', False, 40),
    ('vitamin_d_ug', '/AMT_NUM22', '비타민 D(μg)', False, 41),
    ('cholesterol_mg', '/AMT_NUM23', '콜레스테롤(mg)', False, 42),
    ('saturated_fat_g', '/AMT_NUM24', '포화지방산(g)', False, 43),
    ('trans_fat_g', '/AMT_NUM25', '트랜스지방산(g)', False, 44),
    ('nicotinic_acid_mg', '/AMT_NUM26', '니코틴산 (mg)', False, 45),
    ('nicotinamide_mg', '/AMT_NUM27', '니코틴아마이드(mg)', False, 46),
    ('biotin_ug', '/AMT_NUM28', '비오틴(μg)', False, 47),
    ('vitamin_b6_mg', '/AMT_NUM29', '비타민 B6 (mg)', False, 48),
    ('vitamin_b12_ug', '/AMT_NUM30', '비타민 B12(μg)', False, 49),
    ('folate_dfe_ug', '/AMT_NUM31', '엽산(DFE)(㎍)', False, 50),
    ('choline_mg', '/AMT_NUM32', '콜린(mg)', False, 51),
    ('pantothenic_acid_mg', '/AMT_NUM33', '판토텐산(mg)', False, 52),
    ('vitamin_d2_ug', '/AMT_NUM34', '비타민 D2(μg)', False, 53),
    ('vitamin_d3_ug', '/AMT_NUM35', '비타민 D3(μg)', False, 54),
    ('vitamin_e_mg_ate', '/AMT_NUM36', '비타민 E(mg α-TE)', False, 55),
    ('vitamin_e_mg', '/AMT_NUM37', '비타민 E(mg)', False, 56),
    ('tocopherol_mg', '/AMT_NUM38', '토코페롤(㎎)', False, 57),
    ('alpha_tocopherol_mg', '/AMT_NUM39', '알파 토코페롤(mg)', False, 58),
    ('beta_tocopherol_mg', '/AMT_NUM40', '베타 토코페롤(mg)', False, 59),
    ('gamma_tocopherol_mg', '/AMT_NUM41', '감마 토코페롤(mg)', False, 60),
    ('delta_tocopherol_mg', '/AMT_NUM42', '델타 토코페롤(mg)', False, 61),
    ('tocotrienol_mg', '/AMT_NUM43', '토코트리에놀(㎎)', False, 62),
    ('alpha_tocotrienol_mg', '/AMT_NUM44', '알파 토코트리에놀(mg)', False, 63),
    ('beta_tocotrienol_mg', '/AMT_NUM45', '베타 토코트리에놀(mg)', False, 64),
    ('gamma_tocotrienol_mg', '/AMT_NUM46', '감마 토코트리에놀(mg)', False, 65),
    ('delta_tocotrienol_mg', '/AMT_NUM47', '델타 토코트리에놀(mg)', False, 66),
    ('vitamin_k_ug', '/AMT_NUM48', '비타민 K(μg)', False, 67),
    ('vitamin_k1_ug', '/AMT_NUM49', '비타민 K1(μg)', False, 68),
    ('vitamin_k2_ug', '/AMT_NUM50', '비타민 K2(μg)', False, 69),
    ('galactose_g', '/AMT_NUM51', '갈락토오스(g)', False, 70),
    ('fructose_g', '/AMT_NUM52', '과당(g)', False, 71),
    ('sugar_alcohol_g', '/AMT_NUM53', '당알콜(g)', False, 72),
    ('maltose_g', '/AMT_NUM54', '맥아당(g)', False, 73),
    ('allulose_g', '/AMT_NUM55', '알룰로오스(g)', False, 74),
    ('erythritol_g', '/AMT_NUM56', '에리스리톨(g)', False, 75),
    ('lactose_g', '/AMT_NUM57', '유당(g)', False, 76),
    ('sucrose_g', '/AMT_NUM58', '자당(g)', False, 77),
    ('tagatose_g', '/AMT_NUM59', '타가토스(g)', False, 78),
    ('glucose_g', '/AMT_NUM60', '포도당(g)', False, 79),
    ('total_unsaturated_fat_g', '/AMT_NUM61', '총 불포화지방산(g)', False, 80),
    ('epa_dha_sum_mg', '/AMT_NUM62', 'EPA와 DHA의 합(mg)', False, 81),
    ('gadoleic_acid_mg', '/AMT_NUM63', '가돌레산/에이코센산(mg)', False, 82),
    ('gamma_linolenic_acid_mg', '/AMT_NUM64', '감마 리놀렌산(18:3 n-6)(mg)', False, 83),
    ('nervonic_acid_mg', '/AMT_NUM65', '네르본산(24:1)(mg)', False, 84),
    ('docosadienoic_acid_mg', '/AMT_NUM66', '도코사디에노산(22:2)(mg)', False, 85),
    ('docosapentaenoic_acid_n3_mg', '/AMT_NUM67', '도코사펜타에노산(22:5(n-3))(mg)', False, 86),
    ('docosapentaenoic_acid_n6_mg', '/AMT_NUM68', '도코사펜타엔산(n-6) (22:5,n-6)(mg)', False, 87),
    ('docosahexaenoic_acid_mg', '/AMT_NUM69', '도코사헥사에노산(22:6(n-3))(mg)', False, 88),
    ('dihomo_linolenic_acid_mg', '/AMT_NUM70', '디호모리놀렌산(20:3(n-3))(mg)', False, 89),
    ('dihomo_gamma_linolenic_acid_mg', '/AMT_NUM71', '디호모감마리놀렌산(20:3,n-6))(mg)', False, 90),
    ('lauric_acid_mg', '/AMT_NUM72', '라우르산(12:0)(mg)', False, 91),
    ('lignoceric_acid_mg', '/AMT_NUM73', '리그노세르산(24:0)(mg)', False, 92),
    ('linoleic_acid_g', '/AMT_NUM74', '리놀레산(18:2(n-6)c)(g)', False, 93),
    ('linoleic_acid_mg', '/AMT_NUM75', '리놀레산(18:2(n-6)c)(mg)', False, 94),
    ('myristoleic_acid_mg', '/AMT_NUM76', '미리스톨레산(14:1)(mg)', False, 95),
    ('myristic_acid_mg', '/AMT_NUM77', '미리스트산(14:0)(mg)', False, 96),
    ('vaccenic_acid_mg', '/AMT_NUM78', '박센산(18:1(n-7))(mg)', False, 97),
    ('behenic_acid_mg', '/AMT_NUM79', '베헨산(22:0)(mg)', False, 98),
    ('butyric_acid_mg', '/AMT_NUM80', '부티르산(4:0)(mg)', False, 99),
    ('stearic_acid_mg', '/AMT_NUM81', '스테아르산(18:0)(mg)', False, 100),
    ('stearidonic_acid_mg', '/AMT_NUM82', '스테아리돈산(18:4)(mg)', False, 101),
    ('arachidonic_acid_mg', '/AMT_NUM83', '아라키돈산(20:4 n-6)(mg)', False, 102),
    ('arachidic_acid_mg', '/AMT_NUM84', '아라키드산(20:0)(mg)', False, 103),
    ('alpha_linolenic_acid_g', '/AMT_NUM85', '알파 리놀렌산(18:3(n-3))(g)', False, 104),
    ('alpha_linolenic_acid_mg', '/AMT_NUM86', '알파 리놀렌산(18:3(n-3))(mg)', False, 105),
    ('erucic_acid_mg', '/AMT_NUM87', '에루크산(22:1)(mg)', False, 106),
    ('eicosadienoic_acid_mg', '/AMT_NUM88', '에이코사디에노산(20:2(n-6))(mg)', False, 107),
    ('eicosatrienoic_acid_mg', '/AMT_NUM89', '에이코사트리에노산(20:3(n-6))(mg)', False, 108),
    ('eicosapentaenoic_acid_mg', '/AMT_NUM90', '에이코사펜타에노산(20:5(n-3))(mg)', False, 109),
    ('omega3_fat_g', '/AMT_NUM91', '오메가3 지방산(g)', False, 110),
    ('omega6_fat_g', '/AMT_NUM92', '오메가6 지방산(g)', False, 111),
    ('oleic_acid_mg', '/AMT_NUM93', '올레산(18:1 n-9)(mg)', False, 112),
    ('caproic_acid_mg', '/AMT_NUM94', '카프로산(6:0)(mg)', False, 113),
    ('capric_acid_mg', '/AMT_NUM95', '카프르산(10:0)(mg)', False, 114),
    ('caprylic_acid_mg', '/AMT_NUM96', '카프릴산(8:0)(mg)', False, 115),
    ('tridecanoic_acid_mg', '/AMT_NUM97', '트라이데칸산(13:0)(mg)', False, 116),
    ('trans_linoleic_acid_mg', '/AMT_NUM98', '트랜스 리놀레산(18:2t)(mg)', False, 117),
    ('trans_linolenic_acid_mg', '/AMT_NUM99', '트랜스 리놀렌산(18:3t)(mg)', False, 118),
    ('caffeine_mg', '/AMT_NUM100', '카페인(㎎)', False, 119),
    ('trans_oleic_acid_mg', '/AMT_NUM101', '트랜스 올레산(18:1(n-9)t)(mg)', False, 120),
    ('tricosanoic_acid_mg', '/AMT_NUM102', '트리코산산(23:0)(mg)', False, 121),
    ('palmitoleic_acid_mg', '/AMT_NUM103', '팔미톨레산(16:1)(mg)', False, 122),
    ('palmitic_acid_mg', '/AMT_NUM104', '팔미트산(16:0)(mg)', False, 123),
    ('pentadecanoic_acid_mg', '/AMT_NUM105', '펜타데칸산(15:0)(mg)', False, 124),
    ('heneicosanoic_acid_mg', '/AMT_NUM106', '헨에이코산산(21:0)(mg)', False, 125),
    ('heptadecenoic_acid_mg', '/AMT_NUM107', '헵타데센산(17:1)(mg)', False, 126),
    ('heptadecanoic_acid_mg', '/AMT_NUM108', '헵타데칸산(17:0)(mg)', False, 127),
    ('copper_mg', '/AMT_NUM109', '구리(㎎)', False, 128),
    ('copper_ug', '/AMT_NUM110', '구리(μg)', False, 129),
    ('magnesium_mg', '/AMT_NUM111', '마그네슘(mg)', False, 130),
    ('manganese_mg', '/AMT_NUM112', '망간(mg)', False, 131),
    ('molybdenum_ug', '/AMT_NUM113', '몰리브덴(μg)', False, 132),
    ('fluorine_mg', '/AMT_NUM114', '불소(mg)', False, 133),
    ('selenium_ug', '/AMT_NUM115', '셀레늄(μg)', False, 134),
    ('zinc_mg', '/AMT_NUM116', '아연(mg)', False, 135),
    ('chlorine_mg', '/AMT_NUM117', '염소(mg)', False, 136),
    ('iodine_ug', '/AMT_NUM118', '요오드(μg)', False, 137),
    ('chromium_ug', '/AMT_NUM119', '크롬(μg)', False, 138),
    ('total_amino_acid_mg', '/AMT_NUM120', '총 아미노산(mg)', False, 139),
    ('essential_amino_acid_mg', '/AMT_NUM121', '필수아미노산(mg)', False, 140),
    ('nonessential_amino_acid_mg', '/AMT_NUM122', '비필수아미노산(mg)', False, 141),
    ('glutamic_acid_mg', '/AMT_NUM123', '글루탐산(mg)', False, 142),
    ('glycine_mg', '/AMT_NUM124', '글리신(mg)', False, 143),
    ('lysine_mg', '/AMT_NUM125', '라이신(mg)', False, 144),
    ('leucine_mg', '/AMT_NUM126', '루신(mg)', False, 145),
    ('methionine_mg', '/AMT_NUM127', '메티오닌(mg)', False, 146),
    ('valine_mg', '/AMT_NUM128', '발린(mg)', False, 147),
    ('serine_mg', '/AMT_NUM129', '세린(mg)', False, 148),
    ('cysteine_mg', '/AMT_NUM130', '시스테인(mg)', False, 149),
    ('arginine_mg', '/AMT_NUM131', '아르기닌(mg)', False, 150),
    ('aspartic_acid_mg', '/AMT_NUM132', '아스파르트산(mg)', False, 151),
    ('alanine_mg', '/AMT_NUM133', '알라닌(mg)', False, 152),
    ('isoleucine_mg', '/AMT_NUM134', '이소루신(mg)', False, 153),
    ('taurine_mg', '/AMT_NUM135', '타우린(mg)', False, 154),
    ('threonine_mg', '/AMT_NUM136', '트레오닌(mg)', False, 155),
    ('tryptophan_mg', '/AMT_NUM137', '트립토판(mg)', False, 156),
    ('tyrosine_mg', '/AMT_NUM138', '티로신(mg)', False, 157),
    ('phenylalanine_mg', '/AMT_NUM139', '페닐알라닌(mg)', False, 158),
    ('proline_mg', '/AMT_NUM140', '프롤린(mg)', False, 159),
    ('histidine_mg', '/AMT_NUM141', '히스티딘(mg)', False, 160),
    ('pentadecenoic_acid_mg', '/AMT_NUM142', '펜타데센산(15:1,n-5)(mg)', False, 161),
    ('eicosatetraenoic_acid', '/AMT_NUM143', '에이코사테트라에노산(20:4(n-3))', False, 162),
    ('heneicosapentaenoic_acid_mg', '/AMT_NUM144', '헤니코사펜타엔산(21:5,n-3)(mg)', False, 163),
    ('niacin_equivalent_ne', '/AMT_NUM145', '니아신당량(NE)', False, 164),
    ('soluble_dietary_fiber_g', '/AMT_NUM146', '수용성 식이섬유(g)', False, 165),
    ('insoluble_dietary_fiber_g', '/AMT_NUM147', '불용성 식이섬유(g)', False, 166),
    ('pyridoxine_mg', '/AMT_NUM148', '피리독신(mg)', False, 167),
    ('food_folate_ug', '/AMT_NUM149', '엽산_식품 엽산(μg)', False, 168),
    ('folic_acid_ug', '/AMT_NUM150', '엽산_합성 엽산(μg)', False, 169),
    ('total_essential_fat_g', '/AMT_NUM151', '총 필수지방산(g)', False, 170),
    ('total_monounsaturated_fat_g', '/AMT_NUM152', '총 단일불포화지방산(g)', False, 171),
    ('total_polyunsaturated_fat_g', '/AMT_NUM153', '총 다중불포화지방산(g)', False, 172),
    ('total_fatty_acid_g', '/AMT_NUM154', '총 지방산(g)', False, 173),
    ('fatty_acid_sum_g', '/AMT_NUM155', '지방산의 합(g)', False, 174),
    ('salt_equivalent_g', '/AMT_NUM156', '식염상당량(g)', False, 175),
    ('refuse_rate_pct', '/AMT_NUM157', '폐기율(%)', False, 176),
    ('source_code', '/SUB_REF_CM', '출처코드', False, 177),
    ('source_name', '/SUB_REF_NAME', '출처명', False, 178),
    ('nutrient_reference_serving', '/NUTRI_AMOUNT_SERVING', '1회 섭취참고량', False, 179),
    ('food_weight', '/Z10500', '식품중량', False, 180),
    ('dish_reference_serving', '/DISH_ONE_SERVING', '1회분량 참고량', False, 181),
    ('item_report_no', '/ITEM_REPORT_NO', '품목제조보고번호', False, 182),
    ('maker_name', '/MAKER_NM', '업체명', False, 183),
    ('importer_name', '/IMP_MANUFAC_NM', '수입업체명', False, 184),
    ('seller_name', '/SELLER_MANUFAC_NM', '유통업체명', False, 185),
    ('imported_yn', '/IMP_YN', '수입여부', False, 186),
    ('origin_country_code', '/NATION_CM', '원산지국코드', False, 187),
    ('origin_country_name', '/NATION_NM', '원산지국명', False, 188),
    ('creation_method_code', '/CRT_MTH_CD', '데이터생성방법코드', False, 189),
    ('creation_method_name', '/CRT_MTH_NM', '데이터생성방법명', False, 190),
    ('research_ymd', '/RESEARCH_YMD', '데이터생성일자', False, 191),
    ('update_date', '/UPDATE_DATE', '데이터수정일자', False, 192),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


def _field_table():
    return table(
        "integration_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("direction", sa.String()),
        column("location", sa.String()),
        column("key", sa.String()),
        column("wire_path", sa.String()),
        column("value_source", sa.String()),
        column("value", sa.JSON(none_as_null=True)),
        column("secret_id", sa.Uuid()),
        column("value_type", sa.String()),
        column("format", sa.String()),
        column("required", sa.Boolean()),
        column("description", sa.String()),
        column("sensitive", sa.Boolean()),
        column("ordinal", sa.Integer()),
        column("enabled", sa.Boolean()),
        column("match_mode", sa.String()),
        column("expected_values", sa.JSON(none_as_null=True)),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "id": _id(f"field:REQUEST:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "REQUEST",
            "location": "QUERY",
            "key": key,
            "wire_path": wire_path,
            "value_source": value_source,
            "value": value,
            "secret_id": _id("secret:service-key") if value_source == "SECRET" else None,
            "value_type": value_type,
            "format": None,
            "required": required,
            "description": description,
            "sensitive": sensitive,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": None,
            "expected_values": None,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, value_source, value, value_type, required, description, sensitive, ordinal in REQUEST_ROWS
    ]
    rows.extend(
        {
            "id": _id(f"field:RESPONSE:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "RESPONSE",
            "location": "BODY",
            "key": key,
            "wire_path": wire_path,
            "value_source": None,
            "value": None,
            "secret_id": None,
            "value_type": "STRING",
            "format": None,
            "required": required,
            "description": description,
            "sensitive": False,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": None,
            "expected_values": None,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, description, required, ordinal in RESPONSE_ROWS
    )
    return rows


def upgrade() -> None:
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
    op.bulk_insert(field, _rows())


def downgrade() -> None:
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
