"""replace mfds integration response fields with all 193 API spec fields

Revision ID: 30
Revises: 29
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "30"
down_revision: str | Sequence[str] | None = "29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


def upgrade() -> None:
    response_field_table = table(
        "integration_response_field",
        column("operation_id", sa.Uuid()),
    )
    op.get_bind().execute(
        response_field_table.delete().where(
            response_field_table.c.operation_id == OPERATION_ID
        )
    )
    response_field = table(
        "integration_response_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("source_pointer", sa.String()),
        column("result_key", sa.String()),
        column("value_type", sa.String()),
        column("required", sa.Boolean()),
        column("description", sa.String()),
        column("default_value", sa.JSON(none_as_null=True)),
        column("ordinal", sa.Integer()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    # (source_pointer, result_key, value_type, required, description)
    response_rows = [
        ("/body/items/0/NUM", "num", "STRING", False, "번호"),
        ("/body/items/0/FOOD_CD", "food_cd", "STRING", False, "식품코드"),
        ("/body/items/0/FOOD_NM_KR", "food_nm_kr", "STRING", False, "식품명"),
        ("/body/items/0/DB_GRP_CM", "db_grp_cm", "STRING", False, "데이터구분코드"),
        ("/body/items/0/DB_GRP_NM", "db_grp_nm", "STRING", False, "데이터구분명"),
        ("/body/items/0/DB_CLASS_CM", "db_class_cm", "STRING", False, "품목대표/상용제품 코드"),
        ("/body/items/0/DB_CLASS_NM", "db_class_nm", "STRING", False, "품목대표/상용제품"),
        ("/body/items/0/FOOD_OR_CD", "food_or_cd", "STRING", False, "식품기원코드"),
        ("/body/items/0/FOOD_OR_NM", "food_or_nm", "STRING", False, "식품기원명"),
        ("/body/items/0/FOOD_CAT1_CD", "food_cat1_cd", "STRING", False, "식품대분류코드"),
        ("/body/items/0/FOOD_CAT1_NM", "food_cat1_nm", "STRING", False, "식품대분류명"),
        ("/body/items/0/FOOD_REF_CD", "food_ref_cd", "STRING", False, "대표식품코드"),
        ("/body/items/0/FOOD_REF_NM", "food_ref_nm", "STRING", False, "대표식품명"),
        ("/body/items/0/FOOD_CAT2_CD", "food_cat2_cd", "STRING", False, "식품중분류코드"),
        ("/body/items/0/FOOD_CAT2_NM", "food_cat2_nm", "STRING", False, "식품중분류명"),
        ("/body/items/0/FOOD_CAT3_CD", "food_cat3_cd", "STRING", False, "식품소분류코드"),
        ("/body/items/0/FOOD_CAT3_NM", "food_cat3_nm", "STRING", False, "식품소분류명"),
        ("/body/items/0/FOOD_CAT4_CD", "food_cat4_cd", "STRING", False, "식품세분류코드"),
        ("/body/items/0/FOOD_CAT4_NM", "food_cat4_nm", "STRING", False, "식품세분류명"),
        ("/body/items/0/SERVING_SIZE", "serving_size", "STRING", False, "영양성분함량기준량"),
        ("/body/items/0/AMT_NUM1", "amt_num1", "STRING", False, "에너지(kcal)"),
        ("/body/items/0/AMT_NUM2", "amt_num2", "STRING", False, "수분(g)"),
        ("/body/items/0/AMT_NUM3", "amt_num3", "STRING", False, "단백질(g)"),
        ("/body/items/0/AMT_NUM4", "amt_num4", "STRING", False, "지방(g)"),
        ("/body/items/0/AMT_NUM5", "amt_num5", "STRING", False, "회분(g)"),
        ("/body/items/0/AMT_NUM6", "amt_num6", "STRING", False, "탄수화물(g)"),
        ("/body/items/0/AMT_NUM7", "amt_num7", "STRING", False, "당류(g)"),
        ("/body/items/0/AMT_NUM8", "amt_num8", "STRING", False, "식이섬유(g)"),
        ("/body/items/0/AMT_NUM9", "amt_num9", "STRING", False, "칼슘(mg)"),
        ("/body/items/0/AMT_NUM10", "amt_num10", "STRING", False, "철(mg)"),
        ("/body/items/0/AMT_NUM11", "amt_num11", "STRING", False, "인(mg)"),
        ("/body/items/0/AMT_NUM12", "amt_num12", "STRING", False, "칼륨(mg)"),
        ("/body/items/0/AMT_NUM13", "amt_num13", "STRING", False, "나트륨(mg)"),
        ("/body/items/0/AMT_NUM14", "amt_num14", "STRING", False, "비타민 A(μg RAE)"),
        ("/body/items/0/AMT_NUM15", "amt_num15", "STRING", False, "비타민 A(μg)"),
        ("/body/items/0/AMT_NUM16", "amt_num16", "STRING", False, "레티놀(μg)"),
        ("/body/items/0/AMT_NUM17", "amt_num17", "STRING", False, "베타카로틴(μg)"),
        ("/body/items/0/AMT_NUM18", "amt_num18", "STRING", False, "비타민 B1(mg)"),
        ("/body/items/0/AMT_NUM19", "amt_num19", "STRING", False, "비타민 B2(mg)"),
        ("/body/items/0/AMT_NUM20", "amt_num20", "STRING", False, "니아신(mg)"),
        ("/body/items/0/AMT_NUM21", "amt_num21", "STRING", False, "비타민 C(mg)"),
        ("/body/items/0/AMT_NUM22", "amt_num22", "STRING", False, "비타민 D(μg)"),
        ("/body/items/0/AMT_NUM23", "amt_num23", "STRING", False, "콜레스테롤(mg)"),
        ("/body/items/0/AMT_NUM24", "amt_num24", "STRING", False, "포화지방산(g)"),
        ("/body/items/0/AMT_NUM25", "amt_num25", "STRING", False, "트랜스지방산(g)"),
        ("/body/items/0/AMT_NUM26", "amt_num26", "STRING", False, "니코틴산 (mg)"),
        ("/body/items/0/AMT_NUM27", "amt_num27", "STRING", False, "니코틴아마이드(mg)"),
        ("/body/items/0/AMT_NUM28", "amt_num28", "STRING", False, "비오틴(μg)"),
        ("/body/items/0/AMT_NUM29", "amt_num29", "STRING", False, "비타민 B6 (mg)"),
        ("/body/items/0/AMT_NUM30", "amt_num30", "STRING", False, "비타민 B12(μg)"),
        ("/body/items/0/AMT_NUM31", "amt_num31", "STRING", False, "엽산(DFE)(㎍)"),
        ("/body/items/0/AMT_NUM32", "amt_num32", "STRING", False, "콜린(mg)"),
        ("/body/items/0/AMT_NUM33", "amt_num33", "STRING", False, "판토텐산(mg)"),
        ("/body/items/0/AMT_NUM34", "amt_num34", "STRING", False, "비타민 D2(μg)"),
        ("/body/items/0/AMT_NUM35", "amt_num35", "STRING", False, "비타민 D3(μg)"),
        ("/body/items/0/AMT_NUM36", "amt_num36", "STRING", False, "비타민 E(mg α-TE)"),
        ("/body/items/0/AMT_NUM37", "amt_num37", "STRING", False, "비타민 E(mg)"),
        ("/body/items/0/AMT_NUM38", "amt_num38", "STRING", False, "토코페롤(㎎)"),
        ("/body/items/0/AMT_NUM39", "amt_num39", "STRING", False, "알파 토코페롤(mg)"),
        ("/body/items/0/AMT_NUM40", "amt_num40", "STRING", False, "베타 토코페롤(mg)"),
        ("/body/items/0/AMT_NUM41", "amt_num41", "STRING", False, "감마 토코페롤(mg)"),
        ("/body/items/0/AMT_NUM42", "amt_num42", "STRING", False, "델타 토코페롤(mg)"),
        ("/body/items/0/AMT_NUM43", "amt_num43", "STRING", False, "토코트리에놀(㎎)"),
        ("/body/items/0/AMT_NUM44", "amt_num44", "STRING", False, "알파 토코트리에놀(mg)"),
        ("/body/items/0/AMT_NUM45", "amt_num45", "STRING", False, "베타 토코트리에놀(mg)"),
        ("/body/items/0/AMT_NUM46", "amt_num46", "STRING", False, "감마 토코트리에놀(mg)"),
        ("/body/items/0/AMT_NUM47", "amt_num47", "STRING", False, "델타 토코트리에놀(mg)"),
        ("/body/items/0/AMT_NUM48", "amt_num48", "STRING", False, "비타민 K(μg)"),
        ("/body/items/0/AMT_NUM49", "amt_num49", "STRING", False, "비타민 K1(μg)"),
        ("/body/items/0/AMT_NUM50", "amt_num50", "STRING", False, "비타민 K2(μg)"),
        ("/body/items/0/AMT_NUM51", "amt_num51", "STRING", False, "갈락토오스(g)"),
        ("/body/items/0/AMT_NUM52", "amt_num52", "STRING", False, "과당(g)"),
        ("/body/items/0/AMT_NUM53", "amt_num53", "STRING", False, "당알콜(g)"),
        ("/body/items/0/AMT_NUM54", "amt_num54", "STRING", False, "맥아당(g)"),
        ("/body/items/0/AMT_NUM55", "amt_num55", "STRING", False, "알룰로오스(g)"),
        ("/body/items/0/AMT_NUM56", "amt_num56", "STRING", False, "에리스리톨(g)"),
        ("/body/items/0/AMT_NUM57", "amt_num57", "STRING", False, "유당(g)"),
        ("/body/items/0/AMT_NUM58", "amt_num58", "STRING", False, "자당(g)"),
        ("/body/items/0/AMT_NUM59", "amt_num59", "STRING", False, "타가토스(g)"),
        ("/body/items/0/AMT_NUM60", "amt_num60", "STRING", False, "포도당(g)"),
        ("/body/items/0/AMT_NUM61", "amt_num61", "STRING", False, "총 불포화지방산(g)"),
        ("/body/items/0/AMT_NUM62", "amt_num62", "STRING", False, "EPA와 DHA의 합(mg)"),
        ("/body/items/0/AMT_NUM63", "amt_num63", "STRING", False, "가돌레산/에이코센산(mg)"),
        ("/body/items/0/AMT_NUM64", "amt_num64", "STRING", False, "감마 리놀렌산(18:3 n-6)(mg)"),
        ("/body/items/0/AMT_NUM65", "amt_num65", "STRING", False, "네르본산(24:1)(mg)"),
        ("/body/items/0/AMT_NUM66", "amt_num66", "STRING", False, "도코사디에노산(22:2)(mg)"),
        ("/body/items/0/AMT_NUM67", "amt_num67", "STRING", False, "도코사펜타에노산(22:5(n-3))(mg)"),
        ("/body/items/0/AMT_NUM68", "amt_num68", "STRING", False, "도코사펜타엔산(n-6) (22:5,n-6)(mg)"),
        ("/body/items/0/AMT_NUM69", "amt_num69", "STRING", False, "도코사헥사에노산(22:6(n-3))(mg)"),
        ("/body/items/0/AMT_NUM70", "amt_num70", "STRING", False, "디호모리놀렌산(20:3(n-3))(mg)"),
        ("/body/items/0/AMT_NUM71", "amt_num71", "STRING", False, "디호모감마리놀렌산(20:3,n-6))(mg)"),
        ("/body/items/0/AMT_NUM72", "amt_num72", "STRING", False, "라우르산(12:0)(mg)"),
        ("/body/items/0/AMT_NUM73", "amt_num73", "STRING", False, "리그노세르산(24:0)(mg)"),
        ("/body/items/0/AMT_NUM74", "amt_num74", "STRING", False, "리놀레산(18:2(n-6)c)(g)"),
        ("/body/items/0/AMT_NUM75", "amt_num75", "STRING", False, "리놀레산(18:2(n-6)c)(mg)"),
        ("/body/items/0/AMT_NUM76", "amt_num76", "STRING", False, "미리스톨레산(14:1)(mg)"),
        ("/body/items/0/AMT_NUM77", "amt_num77", "STRING", False, "미리스트산(14:0)(mg)"),
        ("/body/items/0/AMT_NUM78", "amt_num78", "STRING", False, "박센산(18:1(n-7))(mg)"),
        ("/body/items/0/AMT_NUM79", "amt_num79", "STRING", False, "베헨산(22:0)(mg)"),
        ("/body/items/0/AMT_NUM80", "amt_num80", "STRING", False, "부티르산(4:0)(mg)"),
        ("/body/items/0/AMT_NUM81", "amt_num81", "STRING", False, "스테아르산(18:0)(mg)"),
        ("/body/items/0/AMT_NUM82", "amt_num82", "STRING", False, "스테아리돈산(18:4)(mg)"),
        ("/body/items/0/AMT_NUM83", "amt_num83", "STRING", False, "아라키돈산(20:4 n-6)(mg)"),
        ("/body/items/0/AMT_NUM84", "amt_num84", "STRING", False, "아라키드산(20:0)(mg)"),
        ("/body/items/0/AMT_NUM85", "amt_num85", "STRING", False, "알파 리놀렌산(18:3(n-3))(g)"),
        ("/body/items/0/AMT_NUM86", "amt_num86", "STRING", False, "알파 리놀렌산(18:3(n-3))(mg)"),
        ("/body/items/0/AMT_NUM87", "amt_num87", "STRING", False, "에루크산(22:1)(mg)"),
        ("/body/items/0/AMT_NUM88", "amt_num88", "STRING", False, "에이코사디에노산(20:2(n-6))(mg)"),
        ("/body/items/0/AMT_NUM89", "amt_num89", "STRING", False, "에이코사트리에노산(20:3(n-6))(mg)"),
        ("/body/items/0/AMT_NUM90", "amt_num90", "STRING", False, "에이코사펜타에노산(20:5(n-3))(mg)"),
        ("/body/items/0/AMT_NUM91", "amt_num91", "STRING", False, "오메가3 지방산(g)"),
        ("/body/items/0/AMT_NUM92", "amt_num92", "STRING", False, "오메가6 지방산(g)"),
        ("/body/items/0/AMT_NUM93", "amt_num93", "STRING", False, "올레산(18:1 n-9)(mg)"),
        ("/body/items/0/AMT_NUM94", "amt_num94", "STRING", False, "카프로산(6:0)(mg)"),
        ("/body/items/0/AMT_NUM95", "amt_num95", "STRING", False, "카프르산(10:0)(mg)"),
        ("/body/items/0/AMT_NUM96", "amt_num96", "STRING", False, "카프릴산(8:0)(mg)"),
        ("/body/items/0/AMT_NUM97", "amt_num97", "STRING", False, "트라이데칸산(13:0)(mg)"),
        ("/body/items/0/AMT_NUM98", "amt_num98", "STRING", False, "트랜스 리놀레산(18:2t)(mg)"),
        ("/body/items/0/AMT_NUM99", "amt_num99", "STRING", False, "트랜스 리놀렌산(18:3t)(mg)"),
        ("/body/items/0/AMT_NUM100", "amt_num100", "STRING", False, "카페인(㎎)"),
        ("/body/items/0/AMT_NUM101", "amt_num101", "STRING", False, "트랜스 올레산(18:1(n-9)t)(mg)"),
        ("/body/items/0/AMT_NUM102", "amt_num102", "STRING", False, "트리코산산(23:0)(mg)"),
        ("/body/items/0/AMT_NUM103", "amt_num103", "STRING", False, "팔미톨레산(16:1)(mg)"),
        ("/body/items/0/AMT_NUM104", "amt_num104", "STRING", False, "팔미트산(16:0)(mg)"),
        ("/body/items/0/AMT_NUM105", "amt_num105", "STRING", False, "펜타데칸산(15:0)(mg)"),
        ("/body/items/0/AMT_NUM106", "amt_num106", "STRING", False, "헨에이코산산(21:0)(mg)"),
        ("/body/items/0/AMT_NUM107", "amt_num107", "STRING", False, "헵타데센산(17:1)(mg)"),
        ("/body/items/0/AMT_NUM108", "amt_num108", "STRING", False, "헵타데칸산(17:0)(mg)"),
        ("/body/items/0/AMT_NUM109", "amt_num109", "STRING", False, "구리(㎎)"),
        ("/body/items/0/AMT_NUM110", "amt_num110", "STRING", False, "구리(μg)"),
        ("/body/items/0/AMT_NUM111", "amt_num111", "STRING", False, "마그네슘(mg)"),
        ("/body/items/0/AMT_NUM112", "amt_num112", "STRING", False, "망간(mg)"),
        ("/body/items/0/AMT_NUM113", "amt_num113", "STRING", False, "몰리브덴(μg)"),
        ("/body/items/0/AMT_NUM114", "amt_num114", "STRING", False, "불소(mg)"),
        ("/body/items/0/AMT_NUM115", "amt_num115", "STRING", False, "셀레늄(μg)"),
        ("/body/items/0/AMT_NUM116", "amt_num116", "STRING", False, "아연(mg)"),
        ("/body/items/0/AMT_NUM117", "amt_num117", "STRING", False, "염소(mg)"),
        ("/body/items/0/AMT_NUM118", "amt_num118", "STRING", False, "요오드(μg)"),
        ("/body/items/0/AMT_NUM119", "amt_num119", "STRING", False, "크롬(μg)"),
        ("/body/items/0/AMT_NUM120", "amt_num120", "STRING", False, "총 아미노산(mg)"),
        ("/body/items/0/AMT_NUM121", "amt_num121", "STRING", False, "필수아미노산(mg)"),
        ("/body/items/0/AMT_NUM122", "amt_num122", "STRING", False, "비필수아미노산(mg)"),
        ("/body/items/0/AMT_NUM123", "amt_num123", "STRING", False, "글루탐산(mg)"),
        ("/body/items/0/AMT_NUM124", "amt_num124", "STRING", False, "글리신(mg)"),
        ("/body/items/0/AMT_NUM125", "amt_num125", "STRING", False, "라이신(mg)"),
        ("/body/items/0/AMT_NUM126", "amt_num126", "STRING", False, "루신(mg)"),
        ("/body/items/0/AMT_NUM127", "amt_num127", "STRING", False, "메티오닌(mg)"),
        ("/body/items/0/AMT_NUM128", "amt_num128", "STRING", False, "발린(mg)"),
        ("/body/items/0/AMT_NUM129", "amt_num129", "STRING", False, "세린(mg)"),
        ("/body/items/0/AMT_NUM130", "amt_num130", "STRING", False, "시스테인(mg)"),
        ("/body/items/0/AMT_NUM131", "amt_num131", "STRING", False, "아르기닌(mg)"),
        ("/body/items/0/AMT_NUM132", "amt_num132", "STRING", False, "아스파르트산(mg)"),
        ("/body/items/0/AMT_NUM133", "amt_num133", "STRING", False, "알라닌(mg)"),
        ("/body/items/0/AMT_NUM134", "amt_num134", "STRING", False, "이소루신(mg)"),
        ("/body/items/0/AMT_NUM135", "amt_num135", "STRING", False, "타우린(mg)"),
        ("/body/items/0/AMT_NUM136", "amt_num136", "STRING", False, "트레오닌(mg)"),
        ("/body/items/0/AMT_NUM137", "amt_num137", "STRING", False, "트립토판(mg)"),
        ("/body/items/0/AMT_NUM138", "amt_num138", "STRING", False, "티로신(mg)"),
        ("/body/items/0/AMT_NUM139", "amt_num139", "STRING", False, "페닐알라닌(mg)"),
        ("/body/items/0/AMT_NUM140", "amt_num140", "STRING", False, "프롤린(mg)"),
        ("/body/items/0/AMT_NUM141", "amt_num141", "STRING", False, "히스티딘(mg)"),
        ("/body/items/0/AMT_NUM142", "amt_num142", "STRING", False, "펜타데센산(15:1,n-5)(mg)"),
        ("/body/items/0/AMT_NUM143", "amt_num143", "STRING", False, "에이코사테트라에노산(20:4(n-3))"),
        ("/body/items/0/AMT_NUM144", "amt_num144", "STRING", False, "헤니코사펜타엔산(21:5,n-3)(mg)"),
        ("/body/items/0/AMT_NUM145", "amt_num145", "STRING", False, "니아신당량(NE)"),
        ("/body/items/0/AMT_NUM146", "amt_num146", "STRING", False, "수용성 식이섬유(g)"),
        ("/body/items/0/AMT_NUM147", "amt_num147", "STRING", False, "불용성 식이섬유(g)"),
        ("/body/items/0/AMT_NUM148", "amt_num148", "STRING", False, "피리독신(mg)"),
        ("/body/items/0/AMT_NUM149", "amt_num149", "STRING", False, "엽산_식품 엽산(μg)"),
        ("/body/items/0/AMT_NUM150", "amt_num150", "STRING", False, "엽산_합성 엽산(μg)"),
        ("/body/items/0/AMT_NUM151", "amt_num151", "STRING", False, "총 필수지방산(g)"),
        ("/body/items/0/AMT_NUM152", "amt_num152", "STRING", False, "총 단일불포화지방산(g)"),
        ("/body/items/0/AMT_NUM153", "amt_num153", "STRING", False, "총 다중불포화지방산(g)"),
        ("/body/items/0/AMT_NUM154", "amt_num154", "STRING", False, "총 지방산(g)"),
        ("/body/items/0/AMT_NUM155", "amt_num155", "STRING", False, "지방산의 합(g)"),
        ("/body/items/0/AMT_NUM156", "amt_num156", "STRING", False, "식염상당량(g)"),
        ("/body/items/0/AMT_NUM157", "amt_num157", "STRING", False, "폐기율(%)"),
        ("/body/items/0/SUB_REF_CM", "sub_ref_cm", "STRING", False, "출처코드"),
        ("/body/items/0/SUB_REF_NAME", "sub_ref_name", "STRING", False, "출처명"),
        ("/body/items/0/NUTRI_AMOUNT_SERVING", "nutri_amount_serving", "STRING", False, "1회 섭취참고량"),
        ("/body/items/0/Z10500", "z10500", "STRING", False, "식품중량"),
        ("/body/items/0/DISH_ONE_SERVING", "dish_one_serving", "STRING", False, "1회분량 참고량"),
        ("/body/items/0/ITEM_REPORT_NO", "item_report_no", "STRING", False, "품목제조보고번호"),
        ("/body/items/0/MAKER_NM", "maker_nm", "STRING", False, "업체명"),
        ("/body/items/0/IMP_MANUFAC_NM", "imp_manufac_nm", "STRING", False, "수입업체명"),
        ("/body/items/0/SELLER_MANUFAC_NM", "seller_manufac_nm", "STRING", False, "유통업체명"),
        ("/body/items/0/IMP_YN", "imp_yn", "STRING", False, "수입여부"),
        ("/body/items/0/NATION_CM", "nation_cm", "STRING", False, "원산지국코드"),
        ("/body/items/0/NATION_NM", "nation_nm", "STRING", False, "원산지국명"),
        ("/body/items/0/CRT_MTH_CD", "crt_mth_cd", "STRING", False, "데이터생성방법코드"),
        ("/body/items/0/CRT_MTH_NM", "crt_mth_nm", "STRING", False, "데이터생성방법명"),
        ("/body/items/0/RESEARCH_YMD", "research_ymd", "STRING", False, "데이터생성일자"),
        ("/body/items/0/UPDATE_DATE", "update_date", "STRING", False, "데이터수정일자"),
    ]
    op.bulk_insert(
        response_field,
        [
            {
                "id": _id(f"response:{result_key}"),
                "operation_id": OPERATION_ID,
                "source_pointer": source_pointer,
                "result_key": result_key,
                "value_type": value_type,
                "required": required,
                "description": description,
                "default_value": None,
                "ordinal": ordinal,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
            for ordinal, (source_pointer, result_key, value_type, required, description) in enumerate(response_rows)
        ],
    )


def downgrade() -> None:
    response_field_table = table(
        "integration_response_field",
        column("operation_id", sa.Uuid()),
    )
    op.get_bind().execute(
        response_field_table.delete().where(
            response_field_table.c.operation_id == OPERATION_ID
        )
    )
