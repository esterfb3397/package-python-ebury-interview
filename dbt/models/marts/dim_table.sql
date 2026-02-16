{{ config(materialized='table') }}

/*
    dim_table — Product dimension

    Deduplicated product catalogue extracted from transactions.
*/

select distinct
    product_id,
    product_name
from {{ ref('stg_customer_transactions') }}
order by product_id
