-- Singular test: quantity must be > 0 when present.
-- Returns rows that violate the rule.

select
    transaction_id,
    quantity
from {{ ref('fact_table') }}
where quantity is not null
  and quantity <= 0
