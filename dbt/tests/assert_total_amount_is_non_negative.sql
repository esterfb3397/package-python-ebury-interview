-- Singular test: total_amount must be >= 0 for all transactions.
-- Returns rows that violate the rule (dbt expects 0 rows for a passing test).

select
    transaction_id,
    total_amount
from {{ ref('fact_table') }}
where total_amount < 0
