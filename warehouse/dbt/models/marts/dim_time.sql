-- warehouse/dbt/models/marts/dim_time.sql

with stg_orders as (
    select * from {{ ref('stg_delivery_orders') }}
),

unique_times as (
    select distinct
        order_date,
        order_hour,
        order_day_of_week,
        order_month,
        is_weekend,
        is_peak_hour,
        festival
    from stg_orders
    where order_date is not null
)

select
    -- Create a surrogate key combining date and hour
    md5(cast(order_date as varchar) || '-' || cast(order_hour as varchar)) as time_id,
    order_date,
    order_hour,
    order_day_of_week,
    order_month,
    cast(is_weekend as boolean) as is_weekend,
    cast(is_peak_hour as boolean) as is_peak_hour,
    case when festival = 'Yes' then true else false end as is_festival
from unique_times
