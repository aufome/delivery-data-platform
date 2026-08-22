-- warehouse/dbt/models/staging/stg_delivery_orders.sql

with source as (
    -- In a real setup, this points to the external table created via Redshift Spectrum
    -- e.g. select * from {# source('datalake', 'enriched_delivery_orders') #}
    -- For this portfolio demo, we define a stub representation if the external table isn't present
    select * from datalake.enriched_delivery_orders
),

renamed as (
    select
        -- Identifiers
        id as order_id,
        delivery_person_id,
        
        -- Temporal fields
        order_date,
        time_orderd as time_ordered,
        time_order_picked as time_order_picked,
        order_hour,
        order_day_of_week,
        order_month,
        is_weekend,
        is_peak_hour,
        pickup_delay,
        delivery_duration,
        
        -- Weather fields (from Phase 5 enrichment)
        temperature,
        precipitation,
        wind_speed,
        humidity,
        
        -- Geography & Context
        restaurant_latitude,
        restaurant_longitude,
        delivery_location_latitude,
        delivery_location_longitude,
        straight_line_distance as delivery_distance_km,
        
        -- Courier specifics
        delivery_person_age,
        delivery_person_ratings,
        vehicle_condition,
        type_of_order,
        type_of_vehicle,
        multiple_deliveries,
        festival,
        
        -- Environmental context (original dataset fields)
        weather_conditions as base_weather_conditions,
        road_traffic_density,
        city as city_type

    from source
)

select * from renamed
