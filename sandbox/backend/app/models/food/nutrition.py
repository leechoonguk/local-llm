# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


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

# `2025-01-23`, with room for the undashed form the publisher's other services
# answer with for the same concept.
DATE_LENGTH = 20

# A measurement, not a code: 13 characters at the widest over the whole feed,
# thousands separators included (`1,000.000`). 12 integer digits and 6 decimals
# is far past that, and unlike a name a nutrient amount has no reason to grow -
# the unit is in the column's own name.
AMOUNT_PRECISION = 18

AMOUNT_SCALE = 6


# ============================================================
# Classes
# ============================================================


class FoodNutrition(Base, AuditMixin):
    """식품 영양성분 원장 - our own copy of the I2790 records, one row per food.

    **Wide on purpose, and this is the one place the 1NF rule is argued rather
    than followed.** The provider numbers its measurements (`AMT_NUM1..157`),
    which reads like the repeating group `backend-table-design.md` sends to a
    child table. Two things decide against it here:

    - Each column is a *different* quantity with its own unit - `energy_kcal`,
      `protein_g`, `calcium_mg` - not one meaning repeated. The numbering is the
      wire's, and the operation's field seed already gives every one of them a
      name; the ledger stores the names.
    - Measured (2026-09-05): 319,060 foods, ~70 measurements filled each. As
      rows that is ~22M records, upserted one by one through a `SELECT` per
      record on every nightly pass. The ledger's whole increment - match on the
      natural key, compare, leave unchanged rows alone - stops being affordable.

    155 of the 157 are ever filled, and the fill rate spans four orders of
    magnitude (`energy_kcal` 318,957, `choline_mg` 29), so most cells are NULL -
    which costs a bit in the null bitmap and nothing in a row.

    `food_code` is the natural key: unique across all 319,060 records, with zero
    duplicates in the measured feed. `row_no` is deliberately **not** stored -
    it is the position inside the page the record arrived in, so keeping it would
    make every re-read compare unequal the moment the feed shifts by one row.
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
    item_report_no: Mapped[str | None] = mapped_column(Text, default=None)
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

    # The publisher's own `update_date`, parsed - this is what makes the table
    # its own sync cursor, the same way the sibling ledgers are.
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
