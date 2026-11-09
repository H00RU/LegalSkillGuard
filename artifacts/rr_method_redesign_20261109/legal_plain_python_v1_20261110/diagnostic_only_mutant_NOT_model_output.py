def basic_standard_deduction(is_joint_return: bool, is_surviving_spouse: bool, is_head_of_household: bool, is_2018_through_2025_taxable_year: bool, is_c5_dependent: bool, earned_income: int, is_married_filing_separately_with_either_spouse_itemizing: bool, is_nonresident_alien_individual: bool, is_estate_trust_common_trust_fund_or_partnership: bool) -> int:
    if is_nonresident_alien_individual or is_estate_trust_common_trust_fund_or_partnership:
        return 0
    if is_married_filing_separately_with_either_spouse_itemizing:
        return 0
    if is_c5_dependent:
        basic_deduction = max(500, 250 + earned_income)
    elif is_joint_return or is_surviving_spouse:
        basic_deduction = 2 * (12000 if is_2018_through_2025_taxable_year else 3000)
    elif is_head_of_household:
        basic_deduction = 18000 if is_2018_through_2025_taxable_year else 4400
    else:
        basic_deduction = 12000 if is_2018_through_2025_taxable_year else 3000
    return basic_deduction
