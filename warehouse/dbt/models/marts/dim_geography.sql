-- warehouse/dbt/models/marts/dim_geography.sql

with stg_orders as (
    select * from {{ ref('stg_delivery_orders') }}
),

unique_geos as (
    select distinct
        restaurant_latitude,
        restaurant_longitude,
        city_type,
        road_traffic_density
    from stg_orders
    where restaurant_latitude is not null
)

select
    -- Surrogate key for geography
    md5(
        cast(restaurant_latitude as varchar) || '-' ||
        cast(restaurant_longitude as varchar) || '-' ||
        coalesce(city_type, 'unknown') || '-' ||
        coalesce(road_traffic_density, 'unknown')
    ) as geo_id,
    
    restaurant_latitude as latitude,
    restaurant_longitude as longitude,
    city_type,
    road_traffic_density
from unique_geos
