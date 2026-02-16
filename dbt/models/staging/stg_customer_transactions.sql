{{ config(materialized='table') }}

/*
    stg_customer_transactions

    Cleans and normalises raw data from raw_customer_transactions:
      - transaction_id: strip 'T' prefix, cast to INTEGER
      - customer_id: strip '.0' suffix, cast to INTEGER (NULLs preserved)
      - transaction_date: normalise mixed formats (YYYY-MM-DD / DD-MM-YYYY) to DATE
      - product_id: strip 'P' prefix, cast to INTEGER
      - quantity: cast to INTEGER (NULLs preserved)
      - price: convert text ('Two Hundred') to numeric, cast to NUMERIC
      - tax: convert text ('Fifteen') to numeric, cast to NUMERIC
*/

with source as (

    select * from {{ source('raw', 'raw_customer_transactions') }}

),

cleaned as (

    select
        -- transaction_id: strip 'T' prefix and cast
        regexp_replace(transaction_id, '^T', '')::integer
            as transaction_id,

        -- customer_id: strip '.0' and cast (empty → NULL)
        case
            when customer_id = '' then null
            else regexp_replace(customer_id, '\.0$', '')::integer
        end as customer_id,

        -- transaction_date: detect format and normalise to DATE
        case
            when transaction_date ~ '^\d{4}-\d{2}-\d{2}$'
                then transaction_date::date
            when transaction_date ~ '^\d{2}-\d{2}-\d{4}$'
                then to_date(transaction_date, 'DD-MM-YYYY')
            else null
        end as transaction_date,

        -- product_id: strip 'P' prefix and cast
        regexp_replace(product_id, '^P', '')::integer
            as product_id,

        -- product_name: no changes needed
        product_name,

        -- quantity: empty → NULL, strip '.0' and cast to INTEGER
        case
            when quantity = '' then null
            else regexp_replace(quantity, '\.0$', '')::integer
        end as quantity,

        -- price: convert text to numeric
        (case
            when price = '' then null
            when lower(price) = 'two hundred' then 200.00
            else price::numeric
        end)::numeric(10,2) as price,

        -- tax: convert text to numeric
        (case
            when tax = '' then null
            when lower(tax) = 'fifteen' then 15.00
            else tax::numeric
        end)::numeric(10,2) as tax

    from source

)

select * from cleaned
