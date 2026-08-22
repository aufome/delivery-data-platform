-- warehouse/dbt/models/marts/dim_delivery_person.sql

with stg_orders as (
    select * from {{ ref('stg_delivery_orders') }}
),

unique_couriers as (
    select distinct
        delivery_person_id,
        delivery_person_age,
        delivery_person_ratings,
        vehicle_condition,
        type_of_vehicle
    from stg_orders
    where delivery_person_id is not null
)

select
    -- We can generate a surrogate key here, but using the natural ID for simplicity
    delivery_person_id as courier_id,
    delivery_person_age as age,
    delivery_person_ratings as rating,
    vehicle_condition,
    type_of_vehicle
from unique_couriers
