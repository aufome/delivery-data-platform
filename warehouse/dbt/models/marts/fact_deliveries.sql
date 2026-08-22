-- warehouse/dbt/models/marts/fact_deliveries.sql

with stg_orders as (
    select * from {{ ref('stg_delivery_orders') }}
)

select
    -- Primary Key
    order_id,
    
    -- Foreign Keys
    delivery_person_id as courier_id,
    
    md5(cast(order_date as varchar) || '-' || cast(order_hour as varchar)) as time_id,
    
    md5(
        cast(restaurant_latitude as varchar) || '-' ||
        cast(restaurant_longitude as varchar) || '-' ||
        coalesce(city_type, 'unknown') || '-' ||
        coalesce(road_traffic_density, 'unknown')
    ) as geo_id,
    
    md5(
        coalesce(base_weather_conditions, 'unknown') || '-' ||
        cast(coalesce(temperature, -999) as varchar) || '-' ||
        cast(coalesce(precipitation, -999) as varchar) || '-' ||
        cast(coalesce(wind_speed, -999) as varchar) || '-' ||
        cast(coalesce(humidity, -999) as varchar)
    ) as weather_id,
    
    -- Degenerate Dimensions (order-specific descriptors not worth a separate dimension)
    type_of_order,
    multiple_deliveries,
    
    -- Facts / Measures
    delivery_distance_km,
    pickup_delay as pickup_delay_minutes,
    delivery_duration as delivery_duration_minutes,
    
    -- Timestamps
    time_ordered,
    time_order_picked
    
from stg_orders
where order_id is not null
