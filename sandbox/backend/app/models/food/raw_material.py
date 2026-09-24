# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship, remote

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# `A1000911010001` - 14 characters on every I2520 record. Not a tree: a
# composition, read left to right (measured 2026-09-08 on 밀, 71 codes):
#
#   A       대분류   A 식품원료 / B 첨가물 / U 복합원료 / C 건강기능식품 /
#                    P 식품유형 (a finished food used as an ingredient) /
#                    D 기구·용기포장 / E 위생용품
#   1       중분류   A: 1 식물 / 2 축산물 / 3 수산물 / 4 기타동물 / 5 미생물 /
#                    6 기타 / 9 한시적인정
#   000911  기본원료 밀 - the unit of the 식품공전's "식품에 사용할 수 있는 원료"
#   01      부위     01 전체 / 07 어린싹 / 28 씨앗껍질 ...
#   00      가공     19 발효 / 22 볶은 / 45 추출 / 99 호화 ...
#   01      상태     01 가루 / 38 전분 / 08 단백 / 14 액 ...
#
# so 밀가루 is 밀 + 전체 + 가루, and the 19,329 A codes are 7,751 base materials
# with their parts, processes and states spelled out.
CODE_LENGTH = 32

# The first eight characters: class, subclass and base material - the code
# with its part, process and state stripped. A label names an ingredient
# loosely enough that two variants of one base share a name (가공밀가루 is
# process 01 and process 23), and it is at this level that a name resolves:
# measured 2026-09-08 over 10,135,735 ingredient rows, 85.7 % to one base
# against 84.4 % to one code.
BASE_CODE_LENGTH = 8

# The two classes nothing eaten is made of. They are I2520 rows because the
# portal's raw material registry serves 기구·용기포장 and 위생용품 reports
# too; 75 names collide between B and E (348,583 ingredient rows) and vanish
# the moment E is out.
NOT_AN_INGREDIENT = ("D", "E")

# 이명·영문명·학명 are synonym *lists* joined by the portal into one string
# of a length nobody publishes (measured 2026-09-05: alias 1,130, scientific
# 311, english 272), so `Text`.
NAME_LENGTH = 120

# What identifies a material across passes, and the columns a pass fills
# beside it. Listed here and not on a request schema because nothing but the
# I2520 pass writes this table.
NATURAL_KEY = ("raw_material_code",)
SYNCED_COLUMNS = (
    "base_code",
    "representative_raw_material_name",
    "raw_material_alias",
    "english_name",
    "scientific_name",
    "raw_material_large_class",
    "raw_material_medium_class",
    "region_code_name",
    "process_code_name",
    "raw_material_status_code_name",
    "use_yn",
    "source_updated_at",
)


# ============================================================
# Classes
# ============================================================


class FoodRawMaterial(Base, AuditMixin):
    """A raw material an ingredient can name - I2520 read down to what food is made of.

    Derived, not fed: no portal operation answers this table. The I2520 pass
    writes it whole in the same transaction as its ledger (`LedgerStage`), and
    what it writes is the ledger minus the two classes no food contains
    (`NOT_AN_INGREDIENT`), with the composition's base spelled out as a column
    (`base_code`). Measured 2026-09-08: 42,431 of the ledger's 43,609 codes.

    **Nothing else is filtered, on purpose.** A retired code (`use_yn` = `N`,
    18,737 of them) is still what a 2009 report meant by the name it wrote, and
    the reports are the reason this table exists: measured 2026-09-08 by
    report year, an ingredient name misses this table on 10-16 % of rows filed
    before 2015, 2 % of 2016-2021, and 0.1 % of 2022 on - the portal started
    taking the name from this registry, and the old rows are what they are.
    Dropping retired codes would turn 617,955 matched rows into misses and
    resolve 17 names.

    No foreign key to the ledger: both are deleted and refilled by that pass in
    one transaction, and a constraint between them would only dictate the order
    of two statements.
    """

    __tablename__ = "food_raw_material"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    raw_material_code: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    # Indexed because it is the level an ingredient name resolves at, and the
    # column a query groups the variants of one material under.
    base_code: Mapped[str] = mapped_column(String(BASE_CODE_LENGTH), index=True)
    # Indexed because the name is the only key a 품목제조보고 carries for an
    # ingredient (`RAWMTRL_NM`), so "which material is this name" is asked here.
    representative_raw_material_name: Mapped[str | None] = mapped_column(
        Text, default=None, index=True
    )
    raw_material_alias: Mapped[str | None] = mapped_column(Text, default=None)
    english_name: Mapped[str | None] = mapped_column(Text, default=None)
    scientific_name: Mapped[str | None] = mapped_column(Text, default=None)
    raw_material_large_class: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    raw_material_medium_class: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    region_code_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    process_code_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    raw_material_status_code_name: Mapped[str | None] = mapped_column(
        String(NAME_LENGTH), default=None
    )
    use_yn: Mapped[str | None] = mapped_column(String(4), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # The composition's siblings: every code of the same base, this one
    # included (밀 -> 밀, 밀가루, 밀배아 ...), so a reader of one variant sees the
    # material it is a form of. Measured 2026-09-09: 42,431 codes over 30,339
    # bases; 2,476 bases carry more than one code (14,568 codes), 173 at the
    # widest. A self-join on a non-key column, so `remote()` marks the far side.
    variants: Mapped[list[FoodRawMaterial]] = relationship(
        primaryjoin=lambda: foreign(FoodRawMaterial.base_code) == remote(FoodRawMaterial.base_code),
        order_by=lambda: FoodRawMaterial.raw_material_code,
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
