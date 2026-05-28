# setup_postgres.ps1
# Spins up a local Postgres in Docker and seeds a small sample schema for the
# MCP-Bench `postgres` server tasks. Idempotent: re-running reuses the
# container and re-seeds the schema.
#
# Usage:   backend\scripts\setup_postgres.ps1
# Requires: Docker Desktop running.
# Teardown: docker rm -f mcpbench-postgres

$ErrorActionPreference = "Stop"

$Container = "mcpbench-postgres"
$DbName    = "mcpbench"
$Password  = "postgres"
$Port      = 5432

# 1. Verify Docker is available.
try {
    docker info *> $null
} catch {
    Write-Error "Docker is not running. Start Docker Desktop and retry."
    exit 1
}

# 2. Start (or reuse) the container.
$existing = docker ps -a --filter "name=^/$Container$" --format "{{.Names}}"
if ($existing -eq $Container) {
    Write-Host "Container '$Container' exists - ensuring it is running."
    docker start $Container | Out-Null
} else {
    Write-Host "Creating container '$Container' (postgres:16)..."
    docker run -d --name $Container `
        -e POSTGRES_PASSWORD=$Password `
        -e POSTGRES_DB=$DbName `
        -p "${Port}:5432" `
        postgres:16 | Out-Null
}

# 3. Wait for Postgres to accept connections.
Write-Host "Waiting for Postgres to be ready..."
$ready = $false
foreach ($i in 1..30) {
    docker exec $Container pg_isready -U postgres *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    Write-Error "Postgres did not become ready in time."
    exit 1
}

# 4. Seed a small, deterministic sample schema.
$seed = @'
DROP TABLE IF EXISTS salaries;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS departments;

CREATE TABLE departments (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE employees (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    hired_on      DATE NOT NULL
);

CREATE TABLE salaries (
    employee_id INTEGER REFERENCES employees(id),
    amount      INTEGER NOT NULL
);

INSERT INTO departments (name) VALUES ('Engineering'), ('Sales'), ('HR');

INSERT INTO employees (name, department_id, hired_on) VALUES
    ('Alice',   1, '2021-03-01'),
    ('Bob',     1, '2022-07-15'),
    ('Carol',   2, '2020-01-10'),
    ('Dave',    2, '2023-05-20'),
    ('Eve',     3, '2019-11-30');

INSERT INTO salaries (employee_id, amount) VALUES
    (1, 120000), (2, 105000), (3, 90000), (4, 80000), (5, 75000);
'@

Write-Host "Seeding sample schema into '$DbName'..."
$seed | docker exec -i $Container psql -U postgres -d $DbName -v ON_ERROR_STOP=1 | Out-Null

Write-Host ""
Write-Host "Postgres ready at: postgresql://postgres:$Password@localhost:$Port/$DbName"
Write-Host "Set this in .env as POSTGRES_DSN (it is the default if unset)."
Write-Host "Tables: departments, employees, salaries"
