{{ config(materialized='table') }}

/*
    agg_monthly_summary — Monthly transaction summary

    Aggregates key metrics per month: revenue, tax,
    transaction count, and average ticket.
*/

select
    transaction_month,
    count(*) as total_transactions,
    count(distinct customer_id) as unique_customers,
    count(distinct product_id) as unique_products,
    sum(quantity) as total_units_sold,
    sum(price * quantity)::numeric(12,2) as gross_revenue,
    sum(tax)::numeric(12,2) as total_tax,
    sum(total_amount)::numeric(12,2) as total_revenue,
    (sum(total_amount) / count(*))::numeric(10,2) as avg_ticket
from {{ ref('fact_table') }}
group by transaction_month
order by transaction_month
