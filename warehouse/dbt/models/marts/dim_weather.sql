-- warehouse/dbt/models/marts/dim_weather.sql

with stg_orders as (
    select * from {{ ref('stg_delivery_orders') }}
),

unique_weather as (
    select distinct
        base_weather_conditions,
        temperature,
        precipitation,
        wind_speed,
        humidity
    from stg_orders
)

select
    md5(
        coalesce(base_weather_conditions, 'unknown') || '-' ||
        cast(coalesce(temperature, -999) as varchar) || '-' ||
        cast(coalesce(precipitation, -999) as varchar) || '-' ||
        cast(coalesce(wind_speed, -999) as varchar) || '-' ||
        cast(coalesce(humidity, -999) as varchar)
    ) as weather_id,
    
    base_weather_conditions as summary,
    temperature,
    precipitation,
    wind_speed,
    humidity
from unique_weather
