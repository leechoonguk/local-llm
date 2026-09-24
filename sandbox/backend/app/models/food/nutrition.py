# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food.item_report import FoodItemReport


# ============================================================
# Constants
# ============================================================

# `D101-004160000-0001` - a fixed 19-character composite, measured over the whole
# feed (2026-09-05, 319,060 records). The other codes are shorter classification
# keys of the same family, so one bound serves them.
CODE_LENGTH = 32

# Classification names the portal closes over (`밥류`, `품목대표`): 33 characters
# at the widest. Free text - product, maker, importer - is `Text` instead, and
# the reason is beside those columns.
NAME_LENGTH = 120

# `health_functional` (17) is the widest kind `food_item_report` keys by.
KIND_LENGTH = 32

# `2025-01-23`, with room for the undashed form the publisher's other services
# answer with for the same concept.
DATE_LENGTH = 20

# A measurement, not a code: 13 characters at the widest over the whole feed,
# thousands separators included (`1,000.000`). 12 integer digits and 6 decimals
# is far past that, and unlike a name a nutrient amount has no reason to grow -
# the unit is in the column's own name.
AMOUNT_PRECISION = 18

AMOUNT_SCALE = 6

# What identifies a row across passes, and the columns the derivation fills
# beside it - the ledger's own, one for one. Listed on the model because nothing
# but the derive job writes this table.
NATURAL_KEY = ("food_code",)


# ============================================================
# Classes
# ============================================================


class FoodNutrition(Base, AuditMixin):
    """One 영양성분 record - a food's measured nutrients, the I2790 row as it stands.

    Derived, not fed: no portal operation answers this table. The derive job
    rebuilds it off the I2790 ledger whole - the width is the ledger's, argued
    there. The table exists so that the edge to the report it names can be
    declared on it and not on the ledger (rule://backend-relations).

    Measured 2026-09-09 over 319,060 rows: 172,476 (54.1 %) name a report in
    `food_item_report` - 149,666 food, 22,810 livestock, none both. The rest
    are 65,883 수입신고 numbers (`20IT02X00D9`, not a report), 55,158 numbers
    re-issued since (`20170275036137` -> `202600540541`), and 25,543 with no
    number at all (음식, 원재료성 - no report exists for them).

    **The columns here are I2790's own reading of the food.** 식품명, 업체명 and
    the amounts are what the 영양성분 database published for the sample it
    measured, and the product row a record names may spell them otherwise: this
    registry analysed a food, the other registered a report. `report_kind` is
    not published at all - it is resolved at derive time from the number, so the
    edge to a product can carry both of the product's key columns.
    """

    __tablename__ = "food_nutrition"
    __table_args__ = (Index("ix_food_nutrition_source_updated_at", "source_updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    food_code: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    food_name: Mapped[str | None] = mapped_column(Text, default=None)
    data_group_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    data_group_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    item_class_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    item_class_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    food_origin_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    food_origin_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    category_major_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    category_major_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    reference_food_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    reference_food_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    category_medium_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    category_medium_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    category_minor_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    category_minor_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    category_detail_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    category_detail_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    nutrient_basis_amount: Mapped[str | None] = mapped_column(Text, default=None)
    source_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    source_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    nutrient_reference_serving: Mapped[str | None] = mapped_column(Text, default=None)
    food_weight: Mapped[str | None] = mapped_column(Text, default=None)
    dish_reference_serving: Mapped[str | None] = mapped_column(Text, default=None)
    # Which registry the number belongs to, resolved at derive time against the
    # numbered report ledgers - NULL when none carries it. I2790 publishes the
    # 품목제조보고번호 and never says whose it is.
    report_kind: Mapped[str | None] = mapped_column(String(KIND_LENGTH), default=None, index=True)
    item_report_no: Mapped[str | None] = mapped_column(Text, default=None, index=True)
    maker_name: Mapped[str | None] = mapped_column(Text, default=None)
    importer_name: Mapped[str | None] = mapped_column(Text, default=None)
    seller_name: Mapped[str | None] = mapped_column(Text, default=None)
    imported_yn: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    origin_country_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    origin_country_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    creation_method_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    creation_method_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    research_ymd: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    update_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)

    # --- Measurements, in the operation's canonical keys ---
    energy_kcal: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    moisture_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    protein_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    ash_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    carbohydrate_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    sugar_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    dietary_fiber_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    calcium_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    iron_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    phosphorus_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    potassium_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    sodium_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_a_ug_rae: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_a_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    retinol_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    beta_carotene_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_b1_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_b2_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    niacin_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_c_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_d_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    cholesterol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    saturated_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    trans_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    nicotinic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    nicotinamide_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    biotin_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_b6_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_b12_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    folate_dfe_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    choline_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    pantothenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_d2_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_d3_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_e_mg_ate: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_e_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    tocopherol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    alpha_tocopherol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    beta_tocopherol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    gamma_tocopherol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    delta_tocopherol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    tocotrienol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    alpha_tocotrienol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    beta_tocotrienol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    gamma_tocotrienol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    delta_tocotrienol_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_k_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_k1_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vitamin_k2_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    galactose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    fructose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    sugar_alcohol_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    maltose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    allulose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    erythritol_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    lactose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    sucrose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    tagatose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    glucose_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    total_unsaturated_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    epa_dha_sum_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    gadoleic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    gamma_linolenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    nervonic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    docosadienoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    docosapentaenoic_acid_n3_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    docosapentaenoic_acid_n6_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    docosahexaenoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    dihomo_linolenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    dihomo_gamma_linolenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    lauric_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    lignoceric_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    linoleic_acid_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    linoleic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    myristoleic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    myristic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    vaccenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    behenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    butyric_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    stearic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    stearidonic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    arachidonic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    arachidic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    alpha_linolenic_acid_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    alpha_linolenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    erucic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    eicosadienoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    eicosatrienoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    eicosapentaenoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    omega3_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    omega6_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    oleic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    caproic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    capric_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    caprylic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    tridecanoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    trans_linoleic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    trans_linolenic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    caffeine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    trans_oleic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    tricosanoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    palmitoleic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    palmitic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    pentadecanoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    heneicosanoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    heptadecenoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    heptadecanoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    copper_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    copper_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    magnesium_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    manganese_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    molybdenum_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    fluorine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    selenium_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    zinc_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    chlorine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    iodine_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    chromium_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    total_amino_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    essential_amino_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    nonessential_amino_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    glutamic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    glycine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    lysine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    leucine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    methionine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    valine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    serine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    cysteine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    arginine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    aspartic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    alanine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    isoleucine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    taurine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    threonine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    tryptophan_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    tyrosine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    phenylalanine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    proline_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    histidine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    pentadecenoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    eicosatetraenoic_acid: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    heneicosapentaenoic_acid_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    niacin_equivalent_ne: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    soluble_dietary_fiber_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    insoluble_dietary_fiber_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    pyridoxine_mg: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    food_folate_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    folic_acid_ug: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    total_essential_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    total_monounsaturated_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    total_polyunsaturated_fat_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    total_fatty_acid_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    fatty_acid_sum_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    salt_equivalent_g: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )
    refuse_rate_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), default=None
    )

    # The publisher's own `update_date`, parsed - a reading of when the
    # publisher last touched the row; the pass walks the whole feed.
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # The report this record names: 149,666 + 22,810 of 319,060 (2026-09-09).
    # Seen from the report: 13.95 % of food and 4.01 % of livestock reports
    # carry one - 4-7 % of those permitted before 2023, 32-34 % of 2024-2025,
    # which is the nutrition database's reach, not a key problem.
    #
    # Both columns, because that is the product's key: I2790 publishes the
    # number and not the registry, so `report_kind` is resolved at derive time
    # (rule://backend-relations).
    item_report: Mapped[FoodItemReport | None] = relationship(
        primaryjoin=lambda: (
            (foreign(FoodNutrition.report_kind) == FoodItemReport.report_kind)
            & (foreign(FoodNutrition.item_report_no) == FoodItemReport.item_report_no)
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
