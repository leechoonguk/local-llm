"""replace mfds integration operation: nullable types in response_schema

Revision ID: 32
Revises: 31
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "32"
down_revision: str | Sequence[str] | None = "31"
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
                    "type": [
                        "integer",
                        "null"
                    ]
                },
                "numOfRows": {
                    "type": [
                        "integer",
                        "null"
                    ]
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "NUM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_NM_KR": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "DB_GRP_CM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "DB_GRP_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "DB_CLASS_CM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "DB_CLASS_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_OR_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_OR_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT1_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT1_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_REF_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_REF_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT2_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT2_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT3_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT3_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT4_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "FOOD_CAT4_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "SERVING_SIZE": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM1": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM2": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM3": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM4": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM5": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM6": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM7": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM8": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM9": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM10": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM11": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM12": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM13": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM14": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM15": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM16": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM17": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM18": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM19": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM20": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM21": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM22": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM23": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM24": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM25": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM26": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM27": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM28": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM29": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM30": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM31": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM32": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM33": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM34": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM35": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM36": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM37": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM38": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM39": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM40": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM41": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM42": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM43": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM44": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM45": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM46": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM47": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM48": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM49": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM50": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM51": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM52": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM53": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM54": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM55": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM56": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM57": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM58": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM59": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM60": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM61": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM62": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM63": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM64": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM65": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM66": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM67": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM68": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM69": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM70": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM71": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM72": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM73": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM74": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM75": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM76": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM77": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM78": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM79": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM80": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM81": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM82": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM83": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM84": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM85": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM86": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM87": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM88": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM89": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM90": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM91": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM92": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM93": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM94": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM95": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM96": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM97": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM98": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM99": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM100": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM101": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM102": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM103": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM104": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM105": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM106": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM107": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM108": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM109": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM110": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM111": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM112": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM113": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM114": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM115": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM116": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM117": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM118": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM119": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM120": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM121": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM122": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM123": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM124": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM125": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM126": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM127": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM128": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM129": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM130": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM131": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM132": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM133": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM134": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM135": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM136": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM137": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM138": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM139": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM140": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM141": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM142": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM143": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM144": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM145": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM146": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM147": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM148": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM149": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM150": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM151": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM152": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM153": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM154": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM155": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM156": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "AMT_NUM157": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "SUB_REF_CM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "SUB_REF_NAME": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "NUTRI_AMOUNT_SERVING": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "Z10500": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "DISH_ONE_SERVING": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "ITEM_REPORT_NO": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "MAKER_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "IMP_MANUFAC_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "SELLER_MANUFAC_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "IMP_YN": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "NATION_CM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "NATION_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "CRT_MTH_CD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "CRT_MTH_NM": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "RESEARCH_YMD": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "UPDATE_DATE": {
                                "type": [
                                    "string",
                                    "null"
                                ]
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
