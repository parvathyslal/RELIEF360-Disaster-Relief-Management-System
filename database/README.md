# Implemented PostgreSQL database

Run SETUP_WINDOWS.bat or setup_database.py against your existing relief360 database. schema.sql contains native PostgreSQL DDL, indexes, views and PL/pgSQL triggers. store.py connects through psycopg. pgAdmin and the webpage use the same public schema; no SQLite file is used. See SCHEMA_NOTES.md for relation mappings and integrity rules.
