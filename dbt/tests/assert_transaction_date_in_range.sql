-- Singular test: transaction dates should be within a reasonable range.
-- Catches parsing errors that produce dates in the future or too far in the past.

select
    transaction_id,
    transaction_date
from {{ ref('fact_table') }}
where transaction_date < '2020-01-01'
   or transaction_date > current_date
