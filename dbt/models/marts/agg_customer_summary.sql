{{ config(materialized='table') }}

/*
    agg_customer_summary — Customer summary

    Aggregates key metrics per customer: revenue, products purchased,
    first and last purchase, average ticket.
*/

select
    customer_id,
    count(*) as total_transactions,
    count(distinct product_id) as unique_products,
    sum(quantity) as total_units_bought,
    sum(price * quantity)::numeric(12,2) as gross_revenue,
    sum(tax)::numeric(12,2) as total_tax,
    sum(total_amount)::numeric(12,2) as total_spent,
    (sum(total_amount) / count(*))::numeric(10,2) as avg_ticket,
    min(transaction_date) as first_purchase,
    max(transaction_date) as last_purchase
from {{ ref('fact_table') }}
where customer_id is not null
group by customer_id
order by total_spent desc
