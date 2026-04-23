-- Runs on first Postgres init (empty data volume).
-- Creates an isolated database for n8n so it does not pollute retail_orders.

CREATE DATABASE n8n;
GRANT ALL PRIVILEGES ON DATABASE n8n TO retail;
