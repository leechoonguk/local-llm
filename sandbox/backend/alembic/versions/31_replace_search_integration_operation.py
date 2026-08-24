"""replace mfds integration operation: full 193-field response_schema

Revision ID: 31
Revises: 30
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "31"
down_revision: str | Sequence[str] | None = "30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "header": {
            "type": "object",
            "properties": {
                "resultCode": {
                    "type": "string"
                },
                "resultMsg": {
                    "type": "string"
                }
            },
            "required": [
                "resultCode",
                "resultMsg"
            ]
        },
        "body": {
            "type": "object",
            "properties": {
                "pageNo": {
                    "type": "integer"
                },
                "numOfRows": {
                    "type": "integer"
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "NUM": {
                                "type": "string"
                            },
                            "FOOD_CD": {
                                "type": "string"
                            },
                            "FOOD_NM_KR": {
                                "type": "string"
                            },
                            "DB_GRP_CM": {
                                "type": "string"
                            },
                            "DB_GRP_NM": {
                                "type": "string"
                            },
                            "DB_CLASS_CM": {
                                "type": "string"
                            },
                            "DB_CLASS_NM": {
                                "type": "string"
                            },
                            "FOOD_OR_CD": {
                                "type": "string"
                            },
                            "FOOD_OR_NM": {
                                "type": "string"
                            },
                            "FOOD_CAT1_CD": {
                                "type": "string"
                            },
                            "FOOD_CAT1_NM": {
                                "type": "string"
                            },
                            "FOOD_REF_CD": {
                                "type": "string"
                            },
                            "FOOD_REF_NM": {
                                "type": "string"
                            },
                            "FOOD_CAT2_CD": {
                                "type": "string"
                            },
                            "FOOD_CAT2_NM": {
                                "type": "string"
                            },
                            "FOOD_CAT3_CD": {
                                "type": "string"
                            },
                            "FOOD_CAT3_NM": {
                                "type": "string"
                            },
                            "FOOD_CAT4_CD": {
                                "type": "string"
                            },
                            "FOOD_CAT4_NM": {
                                "type": "string"
                            },
                            "SERVING_SIZE": {
                                "type": "string"
                            },
                            "AMT_NUM1": {
                                "type": "string"
                            },
                            "AMT_NUM2": {
                                "type": "string"
                            },
                            "AMT_NUM3": {
                                "type": "string"
                            },
                            "AMT_NUM4": {
                                "type": "string"
                            },
                            "AMT_NUM5": {
                                "type": "string"
                            },
                            "AMT_NUM6": {
                                "type": "string"
                            },
                            "AMT_NUM7": {
                                "type": "string"
                            },
                            "AMT_NUM8": {
                                "type": "string"
                            },
                            "AMT_NUM9": {
                                "type": "string"
                            },
                            "AMT_NUM10": {
                                "type": "string"
                            },
                            "AMT_NUM11": {
                                "type": "string"
                            },
                            "AMT_NUM12": {
                                "type": "string"
                            },
                            "AMT_NUM13": {
                                "type": "string"
                            },
                            "AMT_NUM14": {
                                "type": "string"
                            },
                            "AMT_NUM15": {
                                "type": "string"
                            },
                            "AMT_NUM16": {
                                "type": "string"
                            },
                            "AMT_NUM17": {
                                "type": "string"
                            },
                            "AMT_NUM18": {
                                "type": "string"
                            },
                            "AMT_NUM19": {
                                "type": "string"
                            },
                            "AMT_NUM20": {
                                "type": "string"
                            },
                            "AMT_NUM21": {
                                "type": "string"
                            },
                            "AMT_NUM22": {
                                "type": "string"
                            },
                            "AMT_NUM23": {
                                "type": "string"
                            },
                            "AMT_NUM24": {
                                "type": "string"
                            },
                            "AMT_NUM25": {
                                "type": "string"
                            },
                            "AMT_NUM26": {
                                "type": "string"
                            },
                            "AMT_NUM27": {
                                "type": "string"
                            },
                            "AMT_NUM28": {
                                "type": "string"
                            },
                            "AMT_NUM29": {
                                "type": "string"
                            },
                            "AMT_NUM30": {
                                "type": "string"
                            },
                            "AMT_NUM31": {
                                "type": "string"
                            },
                            "AMT_NUM32": {
                                "type": "string"
                            },
                            "AMT_NUM33": {
                                "type": "string"
                            },
                            "AMT_NUM34": {
                                "type": "string"
                            },
                            "AMT_NUM35": {
                                "type": "string"
                            },
                            "AMT_NUM36": {
                                "type": "string"
                            },
                            "AMT_NUM37": {
                                "type": "string"
                            },
                            "AMT_NUM38": {
                                "type": "string"
                            },
                            "AMT_NUM39": {
                                "type": "string"
                            },
                            "AMT_NUM40": {
                                "type": "string"
                            },
                            "AMT_NUM41": {
                                "type": "string"
                            },
                            "AMT_NUM42": {
                                "type": "string"
                            },
                            "AMT_NUM43": {
                                "type": "string"
                            },
                            "AMT_NUM44": {
                                "type": "string"
                            },
                            "AMT_NUM45": {
                                "type": "string"
                            },
                            "AMT_NUM46": {
                                "type": "string"
                            },
                            "AMT_NUM47": {
                                "type": "string"
                            },
                            "AMT_NUM48": {
                                "type": "string"
                            },
                            "AMT_NUM49": {
                                "type": "string"
                            },
                            "AMT_NUM50": {
                                "type": "string"
                            },
                            "AMT_NUM51": {
                                "type": "string"
                            },
                            "AMT_NUM52": {
                                "type": "string"
                            },
                            "AMT_NUM53": {
                                "type": "string"
                            },
                            "AMT_NUM54": {
                                "type": "string"
                            },
                            "AMT_NUM55": {
                                "type": "string"
                            },
                            "AMT_NUM56": {
                                "type": "string"
                            },
                            "AMT_NUM57": {
                                "type": "string"
                            },
                            "AMT_NUM58": {
                                "type": "string"
                            },
                            "AMT_NUM59": {
                                "type": "string"
                            },
                            "AMT_NUM60": {
                                "type": "string"
                            },
                            "AMT_NUM61": {
                                "type": "string"
                            },
                            "AMT_NUM62": {
                                "type": "string"
                            },
                            "AMT_NUM63": {
                                "type": "string"
                            },
                            "AMT_NUM64": {
                                "type": "string"
                            },
                            "AMT_NUM65": {
                                "type": "string"
                            },
                            "AMT_NUM66": {
                                "type": "string"
                            },
                            "AMT_NUM67": {
                                "type": "string"
                            },
                            "AMT_NUM68": {
                                "type": "string"
                            },
                            "AMT_NUM69": {
                                "type": "string"
                            },
                            "AMT_NUM70": {
                                "type": "string"
                            },
                            "AMT_NUM71": {
                                "type": "string"
                            },
                            "AMT_NUM72": {
                                "type": "string"
                            },
                            "AMT_NUM73": {
                                "type": "string"
                            },
                            "AMT_NUM74": {
                                "type": "string"
                            },
                            "AMT_NUM75": {
                                "type": "string"
                            },
                            "AMT_NUM76": {
                                "type": "string"
                            },
                            "AMT_NUM77": {
                                "type": "string"
                            },
                            "AMT_NUM78": {
                                "type": "string"
                            },
                            "AMT_NUM79": {
                                "type": "string"
                            },
                            "AMT_NUM80": {
                                "type": "string"
                            },
                            "AMT_NUM81": {
                                "type": "string"
                            },
                            "AMT_NUM82": {
                                "type": "string"
                            },
                            "AMT_NUM83": {
                                "type": "string"
                            },
                            "AMT_NUM84": {
                                "type": "string"
                            },
                            "AMT_NUM85": {
                                "type": "string"
                            },
                            "AMT_NUM86": {
                                "type": "string"
                            },
                            "AMT_NUM87": {
                                "type": "string"
                            },
                            "AMT_NUM88": {
                                "type": "string"
                            },
                            "AMT_NUM89": {
                                "type": "string"
                            },
                            "AMT_NUM90": {
                                "type": "string"
                            },
                            "AMT_NUM91": {
                                "type": "string"
                            },
                            "AMT_NUM92": {
                                "type": "string"
                            },
                            "AMT_NUM93": {
                                "type": "string"
                            },
                            "AMT_NUM94": {
                                "type": "string"
                            },
                            "AMT_NUM95": {
                                "type": "string"
                            },
                            "AMT_NUM96": {
                                "type": "string"
                            },
                            "AMT_NUM97": {
                                "type": "string"
                            },
                            "AMT_NUM98": {
                                "type": "string"
                            },
                            "AMT_NUM99": {
                                "type": "string"
                            },
                            "AMT_NUM100": {
                                "type": "string"
                            },
                            "AMT_NUM101": {
                                "type": "string"
                            },
                            "AMT_NUM102": {
                                "type": "string"
                            },
                            "AMT_NUM103": {
                                "type": "string"
                            },
                            "AMT_NUM104": {
                                "type": "string"
                            },
                            "AMT_NUM105": {
                                "type": "string"
                            },
                            "AMT_NUM106": {
                                "type": "string"
                            },
                            "AMT_NUM107": {
                                "type": "string"
                            },
                            "AMT_NUM108": {
                                "type": "string"
                            },
                            "AMT_NUM109": {
                                "type": "string"
                            },
                            "AMT_NUM110": {
                                "type": "string"
                            },
                            "AMT_NUM111": {
                                "type": "string"
                            },
                            "AMT_NUM112": {
                                "type": "string"
                            },
                            "AMT_NUM113": {
                                "type": "string"
                            },
                            "AMT_NUM114": {
                                "type": "string"
                            },
                            "AMT_NUM115": {
                                "type": "string"
                            },
                            "AMT_NUM116": {
                                "type": "string"
                            },
                            "AMT_NUM117": {
                                "type": "string"
                            },
                            "AMT_NUM118": {
                                "type": "string"
                            },
                            "AMT_NUM119": {
                                "type": "string"
                            },
                            "AMT_NUM120": {
                                "type": "string"
                            },
                            "AMT_NUM121": {
                                "type": "string"
                            },
                            "AMT_NUM122": {
                                "type": "string"
                            },
                            "AMT_NUM123": {
                                "type": "string"
                            },
                            "AMT_NUM124": {
                                "type": "string"
                            },
                            "AMT_NUM125": {
                                "type": "string"
                            },
                            "AMT_NUM126": {
                                "type": "string"
                            },
                            "AMT_NUM127": {
                                "type": "string"
                            },
                            "AMT_NUM128": {
                                "type": "string"
                            },
                            "AMT_NUM129": {
                                "type": "string"
                            },
                            "AMT_NUM130": {
                                "type": "string"
                            },
                            "AMT_NUM131": {
                                "type": "string"
                            },
                            "AMT_NUM132": {
                                "type": "string"
                            },
                            "AMT_NUM133": {
                                "type": "string"
                            },
                            "AMT_NUM134": {
                                "type": "string"
                            },
                            "AMT_NUM135": {
                                "type": "string"
                            },
                            "AMT_NUM136": {
                                "type": "string"
                            },
                            "AMT_NUM137": {
                                "type": "string"
                            },
                            "AMT_NUM138": {
                                "type": "string"
                            },
                            "AMT_NUM139": {
                                "type": "string"
                            },
                            "AMT_NUM140": {
                                "type": "string"
                            },
                            "AMT_NUM141": {
                                "type": "string"
                            },
                            "AMT_NUM142": {
                                "type": "string"
                            },
                            "AMT_NUM143": {
                                "type": "string"
                            },
                            "AMT_NUM144": {
                                "type": "string"
                            },
                            "AMT_NUM145": {
                                "type": "string"
                            },
                            "AMT_NUM146": {
                                "type": "string"
                            },
                            "AMT_NUM147": {
                                "type": "string"
                            },
                            "AMT_NUM148": {
                                "type": "string"
                            },
                            "AMT_NUM149": {
                                "type": "string"
                            },
                            "AMT_NUM150": {
                                "type": "string"
                            },
                            "AMT_NUM151": {
                                "type": "string"
                            },
                            "AMT_NUM152": {
                                "type": "string"
                            },
                            "AMT_NUM153": {
                                "type": "string"
                            },
                            "AMT_NUM154": {
                                "type": "string"
                            },
                            "AMT_NUM155": {
                                "type": "string"
                            },
                            "AMT_NUM156": {
                                "type": "string"
                            },
                            "AMT_NUM157": {
                                "type": "string"
                            },
                            "SUB_REF_CM": {
                                "type": "string"
                            },
                            "SUB_REF_NAME": {
                                "type": "string"
                            },
                            "NUTRI_AMOUNT_SERVING": {
                                "type": "string"
                            },
                            "Z10500": {
                                "type": "string"
                            },
                            "DISH_ONE_SERVING": {
                                "type": "string"
                            },
                            "ITEM_REPORT_NO": {
                                "type": "string"
                            },
                            "MAKER_NM": {
                                "type": "string"
                            },
                            "IMP_MANUFAC_NM": {
                                "type": "string"
                            },
                            "SELLER_MANUFAC_NM": {
                                "type": "string"
                            },
                            "IMP_YN": {
                                "type": "string"
                            },
                            "NATION_CM": {
                                "type": "string"
                            },
                            "NATION_NM": {
                                "type": "string"
                            },
                            "CRT_MTH_CD": {
                                "type": "string"
                            },
                            "CRT_MTH_NM": {
                                "type": "string"
                            },
                            "RESEARCH_YMD": {
                                "type": "string"
                            },
                            "UPDATE_DATE": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "FOOD_NM_KR",
                            "AMT_NUM6",
                            "AMT_NUM3",
                            "AMT_NUM4",
                            "AMT_NUM13"
                        ]
                    }
                }
            },
            "required": [
                "pageNo",
                "numOfRows",
                "items"
            ]
        }
    },
    "required": [
        "header",
        "body"
    ]
}


def upgrade() -> None:
    operation_table = table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("response_schema", sa.JSON()),
    )
    op.get_bind().execute(
        operation_table.update()
        .where(operation_table.c.id == OPERATION_ID)
        .values(response_schema=RESPONSE_SCHEMA)
    )


def downgrade() -> None:
    raise NotImplementedError("seed replacement is not reversible")
