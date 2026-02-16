{{ config(materialized='table') }}

/*
    fact_table — Transaction facts

    Contains each transaction with calculated metrics:
      - total_amount: (price * quantity) + tax
      - transaction_month: first day of the month (for monthly aggregations)
*/

select
    transaction_id,
    customer_id,
    product_id,
    transaction_date,
    date_trunc('month', transaction_date)::date as transaction_month,
    quantity,
    price,
    tax,
    (coalesce(price, 0) * coalesce(quantity, 0) + coalesce(tax, 0))::numeric(10,2)
        as total_amount
from {{ ref('stg_customer_transactions') }}
