-- Policy rules referenced by policy engine and decision_rule_hit.rule_id
INSERT INTO risk_policy_rule (rule_code, rule_name, description, priority, is_active)
VALUES
    (
        'POLICY_HIGH_DTI',
        'High DTI flag',
        'high_dti_flag=Y enforces minimum REVIEW',
        30,
        TRUE
    ),
    (
        'POLICY_PRIOR_DELINQ',
        'Prior delinquency',
        'prior_delinquency_flag=Y forces DECLINE',
        10,
        TRUE
    ),
    (
        'POLICY_HIGH_LTI',
        'High loan-to-income',
        'loan_amount_to_income_ratio>=0.7 enforces minimum REVIEW',
        20,
        TRUE
    )
ON CONFLICT (rule_code) DO NOTHING;
