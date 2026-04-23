#!/bin/bash

until pg_isready -h "${POSTGRES_SERVER}" -p 5432 -U "${POSTGRES_USER}"; do
    echo "Postgres DB not initiated ..... wait.."
    sleep 2s
done


# run the migration
alembic upgrade head