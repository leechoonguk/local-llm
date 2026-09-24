# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from pydantic import Field

from app.schemas.mfds import MfdsDatetime, MfdsRecord, MfdsText


# ============================================================
# Constants
# ============================================================

CODE_LENGTH = 32

NAME_LENGTH = 120

DATE_LENGTH = 20

# Keys the operation answers that this ledger declines on purpose. `row_no` is
# the record's position inside the page it arrived in, not a fact about the
# food: stored, it would differ the moment the feed shifts by one row and every
# later run would rewrite the whole ledger to record a new position.
# `check-backend-batch` reads this set, so a decline is a decision it can tell
# from a column that was forgotten.
UNSTORED_KEYS = frozenset({"row_no"})


# ============================================================
# Classes
# ============================================================


class FoodLedgerNutritionMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, because 191 fields written out in two
    places is 191 chances to add a column to one list and not the other, and the
    day one is missed the sync stops refreshing it silently.

    The field names are the operation's canonical response keys, so a record the
    client returns maps into this model without a translation table.
    """

    food_name: MfdsText = None
    data_group_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    data_group_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    item_class_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    item_class_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    food_origin_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    food_origin_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    category_major_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    category_major_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    reference_food_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    reference_food_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    category_medium_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    category_medium_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    category_minor_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    category_minor_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    category_detail_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    category_detail_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    nutrient_basis_amount: MfdsText = None
    source_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    source_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    nutrient_reference_serving: MfdsText = None
    food_weight: MfdsText = None
    dish_reference_serving: MfdsText = None
    item_report_no: MfdsText = None
    maker_name: MfdsText = None
    importer_name: MfdsText = None
    seller_name: MfdsText = None
    imported_yn: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    origin_country_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    origin_country_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    creation_method_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    creation_method_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    research_ymd: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    update_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)

    # --- Measurements, in the operation's canonical keys ---
    energy_kcal: Decimal | None = None
    moisture_g: Decimal | None = None
    protein_g: Decimal | None = None
    fat_g: Decimal | None = None
    ash_g: Decimal | None = None
    carbohydrate_g: Decimal | None = None
    sugar_g: Decimal | None = None
    dietary_fiber_g: Decimal | None = None
    calcium_mg: Decimal | None = None
    iron_mg: Decimal | None = None
    phosphorus_mg: Decimal | None = None
    potassium_mg: Decimal | None = None
    sodium_mg: Decimal | None = None
    vitamin_a_ug_rae: Decimal | None = None
    vitamin_a_ug: Decimal | None = None
    retinol_ug: Decimal | None = None
    beta_carotene_ug: Decimal | None = None
    vitamin_b1_mg: Decimal | None = None
    vitamin_b2_mg: Decimal | None = None
    niacin_mg: Decimal | None = None
    vitamin_c_mg: Decimal | None = None
    vitamin_d_ug: Decimal | None = None
    cholesterol_mg: Decimal | None = None
    saturated_fat_g: Decimal | None = None
    trans_fat_g: Decimal | None = None
    nicotinic_acid_mg: Decimal | None = None
    nicotinamide_mg: Decimal | None = None
    biotin_ug: Decimal | None = None
    vitamin_b6_mg: Decimal | None = None
    vitamin_b12_ug: Decimal | None = None
    folate_dfe_ug: Decimal | None = None
    choline_mg: Decimal | None = None
    pantothenic_acid_mg: Decimal | None = None
    vitamin_d2_ug: Decimal | None = None
    vitamin_d3_ug: Decimal | None = None
    vitamin_e_mg_ate: Decimal | None = None
    vitamin_e_mg: Decimal | None = None
    tocopherol_mg: Decimal | None = None
    alpha_tocopherol_mg: Decimal | None = None
    beta_tocopherol_mg: Decimal | None = None
    gamma_tocopherol_mg: Decimal | None = None
    delta_tocopherol_mg: Decimal | None = None
    tocotrienol_mg: Decimal | None = None
    alpha_tocotrienol_mg: Decimal | None = None
    beta_tocotrienol_mg: Decimal | None = None
    gamma_tocotrienol_mg: Decimal | None = None
    delta_tocotrienol_mg: Decimal | None = None
    vitamin_k_ug: Decimal | None = None
    vitamin_k1_ug: Decimal | None = None
    vitamin_k2_ug: Decimal | None = None
    galactose_g: Decimal | None = None
    fructose_g: Decimal | None = None
    sugar_alcohol_g: Decimal | None = None
    maltose_g: Decimal | None = None
    allulose_g: Decimal | None = None
    erythritol_g: Decimal | None = None
    lactose_g: Decimal | None = None
    sucrose_g: Decimal | None = None
    tagatose_g: Decimal | None = None
    glucose_g: Decimal | None = None
    total_unsaturated_fat_g: Decimal | None = None
    epa_dha_sum_mg: Decimal | None = None
    gadoleic_acid_mg: Decimal | None = None
    gamma_linolenic_acid_mg: Decimal | None = None
    nervonic_acid_mg: Decimal | None = None
    docosadienoic_acid_mg: Decimal | None = None
    docosapentaenoic_acid_n3_mg: Decimal | None = None
    docosapentaenoic_acid_n6_mg: Decimal | None = None
    docosahexaenoic_acid_mg: Decimal | None = None
    dihomo_linolenic_acid_mg: Decimal | None = None
    dihomo_gamma_linolenic_acid_mg: Decimal | None = None
    lauric_acid_mg: Decimal | None = None
    lignoceric_acid_mg: Decimal | None = None
    linoleic_acid_g: Decimal | None = None
    linoleic_acid_mg: Decimal | None = None
    myristoleic_acid_mg: Decimal | None = None
    myristic_acid_mg: Decimal | None = None
    vaccenic_acid_mg: Decimal | None = None
    behenic_acid_mg: Decimal | None = None
    butyric_acid_mg: Decimal | None = None
    stearic_acid_mg: Decimal | None = None
    stearidonic_acid_mg: Decimal | None = None
    arachidonic_acid_mg: Decimal | None = None
    arachidic_acid_mg: Decimal | None = None
    alpha_linolenic_acid_g: Decimal | None = None
    alpha_linolenic_acid_mg: Decimal | None = None
    erucic_acid_mg: Decimal | None = None
    eicosadienoic_acid_mg: Decimal | None = None
    eicosatrienoic_acid_mg: Decimal | None = None
    eicosapentaenoic_acid_mg: Decimal | None = None
    omega3_fat_g: Decimal | None = None
    omega6_fat_g: Decimal | None = None
    oleic_acid_mg: Decimal | None = None
    caproic_acid_mg: Decimal | None = None
    capric_acid_mg: Decimal | None = None
    caprylic_acid_mg: Decimal | None = None
    tridecanoic_acid_mg: Decimal | None = None
    trans_linoleic_acid_mg: Decimal | None = None
    trans_linolenic_acid_mg: Decimal | None = None
    caffeine_mg: Decimal | None = None
    trans_oleic_acid_mg: Decimal | None = None
    tricosanoic_acid_mg: Decimal | None = None
    palmitoleic_acid_mg: Decimal | None = None
    palmitic_acid_mg: Decimal | None = None
    pentadecanoic_acid_mg: Decimal | None = None
    heneicosanoic_acid_mg: Decimal | None = None
    heptadecenoic_acid_mg: Decimal | None = None
    heptadecanoic_acid_mg: Decimal | None = None
    copper_mg: Decimal | None = None
    copper_ug: Decimal | None = None
    magnesium_mg: Decimal | None = None
    manganese_mg: Decimal | None = None
    molybdenum_ug: Decimal | None = None
    fluorine_mg: Decimal | None = None
    selenium_ug: Decimal | None = None
    zinc_mg: Decimal | None = None
    chlorine_mg: Decimal | None = None
    iodine_ug: Decimal | None = None
    chromium_ug: Decimal | None = None
    total_amino_acid_mg: Decimal | None = None
    essential_amino_acid_mg: Decimal | None = None
    nonessential_amino_acid_mg: Decimal | None = None
    glutamic_acid_mg: Decimal | None = None
    glycine_mg: Decimal | None = None
    lysine_mg: Decimal | None = None
    leucine_mg: Decimal | None = None
    methionine_mg: Decimal | None = None
    valine_mg: Decimal | None = None
    serine_mg: Decimal | None = None
    cysteine_mg: Decimal | None = None
    arginine_mg: Decimal | None = None
    aspartic_acid_mg: Decimal | None = None
    alanine_mg: Decimal | None = None
    isoleucine_mg: Decimal | None = None
    taurine_mg: Decimal | None = None
    threonine_mg: Decimal | None = None
    tryptophan_mg: Decimal | None = None
    tyrosine_mg: Decimal | None = None
    phenylalanine_mg: Decimal | None = None
    proline_mg: Decimal | None = None
    histidine_mg: Decimal | None = None
    pentadecenoic_acid_mg: Decimal | None = None
    eicosatetraenoic_acid: Decimal | None = None
    heneicosapentaenoic_acid_mg: Decimal | None = None
    niacin_equivalent_ne: Decimal | None = None
    soluble_dietary_fiber_g: Decimal | None = None
    insoluble_dietary_fiber_g: Decimal | None = None
    pyridoxine_mg: Decimal | None = None
    food_folate_ug: Decimal | None = None
    folic_acid_ug: Decimal | None = None
    total_essential_fat_g: Decimal | None = None
    total_monounsaturated_fat_g: Decimal | None = None
    total_polyunsaturated_fat_g: Decimal | None = None
    total_fatty_acid_g: Decimal | None = None
    fatty_acid_sum_g: Decimal | None = None
    salt_equivalent_g: Decimal | None = None
    refuse_rate_pct: Decimal | None = None

    source_updated_at: MfdsDatetime = None


class FoodLedgerNutritionBase(FoodLedgerNutritionMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    food_code: str = Field(max_length=CODE_LENGTH)


class FoodLedgerNutritionCreateRequest(FoodLedgerNutritionBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerNutritionCreateRequest | None:
        """Map one canonical I2790 record onto the ledger, or refuse it.

        A record with no `food_code` cannot be upserted - the next page would
        insert it a second time - so it is dropped here rather than becoming a
        row no sync can match again. Every other refusal still raises: that is a
        contract change, not a sparse record.
        """
        food_code = cls.key_text(record.get("food_code"))
        if food_code is None:
            return None
        return cls.model_validate(
            {
                "food_code": food_code,
                "food_name": record.get("food_name"),
                "data_group_code": record.get("data_group_code"),
                "data_group_name": record.get("data_group_name"),
                "item_class_code": record.get("item_class_code"),
                "item_class_name": record.get("item_class_name"),
                "food_origin_code": record.get("food_origin_code"),
                "food_origin_name": record.get("food_origin_name"),
                "category_major_code": record.get("category_major_code"),
                "category_major_name": record.get("category_major_name"),
                "reference_food_code": record.get("reference_food_code"),
                "reference_food_name": record.get("reference_food_name"),
                "category_medium_code": record.get("category_medium_code"),
                "category_medium_name": record.get("category_medium_name"),
                "category_minor_code": record.get("category_minor_code"),
                "category_minor_name": record.get("category_minor_name"),
                "category_detail_code": record.get("category_detail_code"),
                "category_detail_name": record.get("category_detail_name"),
                "nutrient_basis_amount": record.get("nutrient_basis_amount"),
                "source_code": record.get("source_code"),
                "source_name": record.get("source_name"),
                "nutrient_reference_serving": record.get("nutrient_reference_serving"),
                "food_weight": record.get("food_weight"),
                "dish_reference_serving": record.get("dish_reference_serving"),
                "item_report_no": record.get("item_report_no"),
                "maker_name": record.get("maker_name"),
                "importer_name": record.get("importer_name"),
                "seller_name": record.get("seller_name"),
                "imported_yn": record.get("imported_yn"),
                "origin_country_code": record.get("origin_country_code"),
                "origin_country_name": record.get("origin_country_name"),
                "creation_method_code": record.get("creation_method_code"),
                "creation_method_name": record.get("creation_method_name"),
                "research_ymd": record.get("research_ymd"),
                "update_date": record.get("update_date"),
                "energy_kcal": _amount(record.get("energy_kcal")),
                "moisture_g": _amount(record.get("moisture_g")),
                "protein_g": _amount(record.get("protein_g")),
                "fat_g": _amount(record.get("fat_g")),
                "ash_g": _amount(record.get("ash_g")),
                "carbohydrate_g": _amount(record.get("carbohydrate_g")),
                "sugar_g": _amount(record.get("sugar_g")),
                "dietary_fiber_g": _amount(record.get("dietary_fiber_g")),
                "calcium_mg": _amount(record.get("calcium_mg")),
                "iron_mg": _amount(record.get("iron_mg")),
                "phosphorus_mg": _amount(record.get("phosphorus_mg")),
                "potassium_mg": _amount(record.get("potassium_mg")),
                "sodium_mg": _amount(record.get("sodium_mg")),
                "vitamin_a_ug_rae": _amount(record.get("vitamin_a_ug_rae")),
                "vitamin_a_ug": _amount(record.get("vitamin_a_ug")),
                "retinol_ug": _amount(record.get("retinol_ug")),
                "beta_carotene_ug": _amount(record.get("beta_carotene_ug")),
                "vitamin_b1_mg": _amount(record.get("vitamin_b1_mg")),
                "vitamin_b2_mg": _amount(record.get("vitamin_b2_mg")),
                "niacin_mg": _amount(record.get("niacin_mg")),
                "vitamin_c_mg": _amount(record.get("vitamin_c_mg")),
                "vitamin_d_ug": _amount(record.get("vitamin_d_ug")),
                "cholesterol_mg": _amount(record.get("cholesterol_mg")),
                "saturated_fat_g": _amount(record.get("saturated_fat_g")),
                "trans_fat_g": _amount(record.get("trans_fat_g")),
                "nicotinic_acid_mg": _amount(record.get("nicotinic_acid_mg")),
                "nicotinamide_mg": _amount(record.get("nicotinamide_mg")),
                "biotin_ug": _amount(record.get("biotin_ug")),
                "vitamin_b6_mg": _amount(record.get("vitamin_b6_mg")),
                "vitamin_b12_ug": _amount(record.get("vitamin_b12_ug")),
                "folate_dfe_ug": _amount(record.get("folate_dfe_ug")),
                "choline_mg": _amount(record.get("choline_mg")),
                "pantothenic_acid_mg": _amount(record.get("pantothenic_acid_mg")),
                "vitamin_d2_ug": _amount(record.get("vitamin_d2_ug")),
                "vitamin_d3_ug": _amount(record.get("vitamin_d3_ug")),
                "vitamin_e_mg_ate": _amount(record.get("vitamin_e_mg_ate")),
                "vitamin_e_mg": _amount(record.get("vitamin_e_mg")),
                "tocopherol_mg": _amount(record.get("tocopherol_mg")),
                "alpha_tocopherol_mg": _amount(record.get("alpha_tocopherol_mg")),
                "beta_tocopherol_mg": _amount(record.get("beta_tocopherol_mg")),
                "gamma_tocopherol_mg": _amount(record.get("gamma_tocopherol_mg")),
                "delta_tocopherol_mg": _amount(record.get("delta_tocopherol_mg")),
                "tocotrienol_mg": _amount(record.get("tocotrienol_mg")),
                "alpha_tocotrienol_mg": _amount(record.get("alpha_tocotrienol_mg")),
                "beta_tocotrienol_mg": _amount(record.get("beta_tocotrienol_mg")),
                "gamma_tocotrienol_mg": _amount(record.get("gamma_tocotrienol_mg")),
                "delta_tocotrienol_mg": _amount(record.get("delta_tocotrienol_mg")),
                "vitamin_k_ug": _amount(record.get("vitamin_k_ug")),
                "vitamin_k1_ug": _amount(record.get("vitamin_k1_ug")),
                "vitamin_k2_ug": _amount(record.get("vitamin_k2_ug")),
                "galactose_g": _amount(record.get("galactose_g")),
                "fructose_g": _amount(record.get("fructose_g")),
                "sugar_alcohol_g": _amount(record.get("sugar_alcohol_g")),
                "maltose_g": _amount(record.get("maltose_g")),
                "allulose_g": _amount(record.get("allulose_g")),
                "erythritol_g": _amount(record.get("erythritol_g")),
                "lactose_g": _amount(record.get("lactose_g")),
                "sucrose_g": _amount(record.get("sucrose_g")),
                "tagatose_g": _amount(record.get("tagatose_g")),
                "glucose_g": _amount(record.get("glucose_g")),
                "total_unsaturated_fat_g": _amount(record.get("total_unsaturated_fat_g")),
                "epa_dha_sum_mg": _amount(record.get("epa_dha_sum_mg")),
                "gadoleic_acid_mg": _amount(record.get("gadoleic_acid_mg")),
                "gamma_linolenic_acid_mg": _amount(record.get("gamma_linolenic_acid_mg")),
                "nervonic_acid_mg": _amount(record.get("nervonic_acid_mg")),
                "docosadienoic_acid_mg": _amount(record.get("docosadienoic_acid_mg")),
                "docosapentaenoic_acid_n3_mg": _amount(record.get("docosapentaenoic_acid_n3_mg")),
                "docosapentaenoic_acid_n6_mg": _amount(record.get("docosapentaenoic_acid_n6_mg")),
                "docosahexaenoic_acid_mg": _amount(record.get("docosahexaenoic_acid_mg")),
                "dihomo_linolenic_acid_mg": _amount(record.get("dihomo_linolenic_acid_mg")),
                "dihomo_gamma_linolenic_acid_mg": _amount(
                    record.get("dihomo_gamma_linolenic_acid_mg")
                ),
                "lauric_acid_mg": _amount(record.get("lauric_acid_mg")),
                "lignoceric_acid_mg": _amount(record.get("lignoceric_acid_mg")),
                "linoleic_acid_g": _amount(record.get("linoleic_acid_g")),
                "linoleic_acid_mg": _amount(record.get("linoleic_acid_mg")),
                "myristoleic_acid_mg": _amount(record.get("myristoleic_acid_mg")),
                "myristic_acid_mg": _amount(record.get("myristic_acid_mg")),
                "vaccenic_acid_mg": _amount(record.get("vaccenic_acid_mg")),
                "behenic_acid_mg": _amount(record.get("behenic_acid_mg")),
                "butyric_acid_mg": _amount(record.get("butyric_acid_mg")),
                "stearic_acid_mg": _amount(record.get("stearic_acid_mg")),
                "stearidonic_acid_mg": _amount(record.get("stearidonic_acid_mg")),
                "arachidonic_acid_mg": _amount(record.get("arachidonic_acid_mg")),
                "arachidic_acid_mg": _amount(record.get("arachidic_acid_mg")),
                "alpha_linolenic_acid_g": _amount(record.get("alpha_linolenic_acid_g")),
                "alpha_linolenic_acid_mg": _amount(record.get("alpha_linolenic_acid_mg")),
                "erucic_acid_mg": _amount(record.get("erucic_acid_mg")),
                "eicosadienoic_acid_mg": _amount(record.get("eicosadienoic_acid_mg")),
                "eicosatrienoic_acid_mg": _amount(record.get("eicosatrienoic_acid_mg")),
                "eicosapentaenoic_acid_mg": _amount(record.get("eicosapentaenoic_acid_mg")),
                "omega3_fat_g": _amount(record.get("omega3_fat_g")),
                "omega6_fat_g": _amount(record.get("omega6_fat_g")),
                "oleic_acid_mg": _amount(record.get("oleic_acid_mg")),
                "caproic_acid_mg": _amount(record.get("caproic_acid_mg")),
                "capric_acid_mg": _amount(record.get("capric_acid_mg")),
                "caprylic_acid_mg": _amount(record.get("caprylic_acid_mg")),
                "tridecanoic_acid_mg": _amount(record.get("tridecanoic_acid_mg")),
                "trans_linoleic_acid_mg": _amount(record.get("trans_linoleic_acid_mg")),
                "trans_linolenic_acid_mg": _amount(record.get("trans_linolenic_acid_mg")),
                "caffeine_mg": _amount(record.get("caffeine_mg")),
                "trans_oleic_acid_mg": _amount(record.get("trans_oleic_acid_mg")),
                "tricosanoic_acid_mg": _amount(record.get("tricosanoic_acid_mg")),
                "palmitoleic_acid_mg": _amount(record.get("palmitoleic_acid_mg")),
                "palmitic_acid_mg": _amount(record.get("palmitic_acid_mg")),
                "pentadecanoic_acid_mg": _amount(record.get("pentadecanoic_acid_mg")),
                "heneicosanoic_acid_mg": _amount(record.get("heneicosanoic_acid_mg")),
                "heptadecenoic_acid_mg": _amount(record.get("heptadecenoic_acid_mg")),
                "heptadecanoic_acid_mg": _amount(record.get("heptadecanoic_acid_mg")),
                "copper_mg": _amount(record.get("copper_mg")),
                "copper_ug": _amount(record.get("copper_ug")),
                "magnesium_mg": _amount(record.get("magnesium_mg")),
                "manganese_mg": _amount(record.get("manganese_mg")),
                "molybdenum_ug": _amount(record.get("molybdenum_ug")),
                "fluorine_mg": _amount(record.get("fluorine_mg")),
                "selenium_ug": _amount(record.get("selenium_ug")),
                "zinc_mg": _amount(record.get("zinc_mg")),
                "chlorine_mg": _amount(record.get("chlorine_mg")),
                "iodine_ug": _amount(record.get("iodine_ug")),
                "chromium_ug": _amount(record.get("chromium_ug")),
                "total_amino_acid_mg": _amount(record.get("total_amino_acid_mg")),
                "essential_amino_acid_mg": _amount(record.get("essential_amino_acid_mg")),
                "nonessential_amino_acid_mg": _amount(record.get("nonessential_amino_acid_mg")),
                "glutamic_acid_mg": _amount(record.get("glutamic_acid_mg")),
                "glycine_mg": _amount(record.get("glycine_mg")),
                "lysine_mg": _amount(record.get("lysine_mg")),
                "leucine_mg": _amount(record.get("leucine_mg")),
                "methionine_mg": _amount(record.get("methionine_mg")),
                "valine_mg": _amount(record.get("valine_mg")),
                "serine_mg": _amount(record.get("serine_mg")),
                "cysteine_mg": _amount(record.get("cysteine_mg")),
                "arginine_mg": _amount(record.get("arginine_mg")),
                "aspartic_acid_mg": _amount(record.get("aspartic_acid_mg")),
                "alanine_mg": _amount(record.get("alanine_mg")),
                "isoleucine_mg": _amount(record.get("isoleucine_mg")),
                "taurine_mg": _amount(record.get("taurine_mg")),
                "threonine_mg": _amount(record.get("threonine_mg")),
                "tryptophan_mg": _amount(record.get("tryptophan_mg")),
                "tyrosine_mg": _amount(record.get("tyrosine_mg")),
                "phenylalanine_mg": _amount(record.get("phenylalanine_mg")),
                "proline_mg": _amount(record.get("proline_mg")),
                "histidine_mg": _amount(record.get("histidine_mg")),
                "pentadecenoic_acid_mg": _amount(record.get("pentadecenoic_acid_mg")),
                "eicosatetraenoic_acid": _amount(record.get("eicosatetraenoic_acid")),
                "heneicosapentaenoic_acid_mg": _amount(record.get("heneicosapentaenoic_acid_mg")),
                "niacin_equivalent_ne": _amount(record.get("niacin_equivalent_ne")),
                "soluble_dietary_fiber_g": _amount(record.get("soluble_dietary_fiber_g")),
                "insoluble_dietary_fiber_g": _amount(record.get("insoluble_dietary_fiber_g")),
                "pyridoxine_mg": _amount(record.get("pyridoxine_mg")),
                "food_folate_ug": _amount(record.get("food_folate_ug")),
                "folic_acid_ug": _amount(record.get("folic_acid_ug")),
                "total_essential_fat_g": _amount(record.get("total_essential_fat_g")),
                "total_monounsaturated_fat_g": _amount(record.get("total_monounsaturated_fat_g")),
                "total_polyunsaturated_fat_g": _amount(record.get("total_polyunsaturated_fat_g")),
                "total_fatty_acid_g": _amount(record.get("total_fatty_acid_g")),
                "fatty_acid_sum_g": _amount(record.get("fatty_acid_sum_g")),
                "salt_equivalent_g": _amount(record.get("salt_equivalent_g")),
                "refuse_rate_pct": _amount(record.get("refuse_rate_pct")),
                "source_updated_at": record.get("update_date"),
            }
        )


def _amount(value: object) -> Decimal | None:
    """One nutrient measurement, or None where the portal sends nothing.

    The portal writes thousands separators into a numeric field (`1,000.000`,
    measured 451 times on the widest column), so a bare `Decimal(text)` raises
    on real data and would refuse the page the record arrived in. An unreadable
    amount costs that one measurement, never the food: the row still carries the
    other 156, and a nutrient nobody can parse is better absent than fabricated.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return Decimal(value.strip().replace(",", ""))
    except InvalidOperation:
        return None
