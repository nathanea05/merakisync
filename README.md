# meraki-sync

[![PyPI - Version](https://img.shields.io/pypi/v/meraki-sync.svg)](https://pypi.org/project/meraki-sync)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/meraki-sync.svg)](https://pypi.org/project/meraki-sync)

-----

## Table of Contents

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install merakisync
```

## License

`meraki-sync` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.


# Database Setup
1. Make sure you have postgres installed on a host that is reachable on the network
2. If the database is remote (not on localhost), adjust pg_hba to allow remote connections
3. Create database `merakisync` (This can be customized, but remember the name for when you run merakisync init)
4. Create schema meraki and authorize merakisync


# Create Database
CREATE DATABASE meraki;

# Create User
CREATE USER merakisync WITH PASSWORD 'password';

# Create Schema
-- Create schema
CREATE SCHEMA IF NOT EXISTS meraki AUTHORIZATION merakisync;

-- Allow using/creating objects in schema
GRANT USAGE, CREATE ON SCHEMA meraki TO merakisync;

-- If tables already exist:
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA meraki TO merakisync;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA meraki TO merakisync;

-- Ensure future tables/sequences created by migrations are usable:
ALTER DEFAULT PRIVILEGES IN SCHEMA meraki
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO merakisync;

ALTER DEFAULT PRIVILEGES IN SCHEMA meraki
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO merakisync;

-- Make meraki the default schema for this role in this database
ALTER ROLE merakisync IN DATABASE pacs_engineering
SET search_path = meraki, public;
