-- =============================================================================
-- MS1 - Usuarios y Conductores · transporte-ms1-usuarios
-- DDL exacto definido en el Contrato Cero v1.0 (§4)
-- No renombrar ni reordenar columnas. Aplicar tal cual en PostgreSQL 16.
-- =============================================================================

CREATE TABLE usuarios (
    id             SERIAL PRIMARY KEY,
    nombre         VARCHAR(60)  NOT NULL,
    apellido       VARCHAR(60)  NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    telefono       VARCHAR(20),
    distrito       VARCHAR(60),
    fecha_nacimiento DATE,
    fecha_registro TIMESTAMP    NOT NULL DEFAULT NOW(),
    activo         BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE conductores (
    id             SERIAL PRIMARY KEY,
    nombre         VARCHAR(60)  NOT NULL,
    apellido       VARCHAR(60)  NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    telefono       VARCHAR(20),
    nro_licencia   VARCHAR(20)  NOT NULL UNIQUE,
    distrito_base  VARCHAR(60),
    fecha_ingreso  DATE         NOT NULL,
    calificacion_promedio NUMERIC(3,2) DEFAULT 0,
    activo         BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE vehiculos (
    id            SERIAL PRIMARY KEY,
    conductor_id  INTEGER NOT NULL REFERENCES conductores(id) ON DELETE CASCADE,
    placa         VARCHAR(10) NOT NULL UNIQUE,
    marca         VARCHAR(40) NOT NULL,
    modelo        VARCHAR(40) NOT NULL,
    anio          SMALLINT    NOT NULL,
    color         VARCHAR(25),
    capacidad     SMALLINT    NOT NULL DEFAULT 4,
    tipo_servicio VARCHAR(20) NOT NULL DEFAULT 'estandar'
);

CREATE INDEX idx_vehiculos_conductor ON vehiculos(conductor_id);
CREATE INDEX idx_usuarios_distrito   ON usuarios(distrito);
CREATE INDEX idx_conductores_ingreso ON conductores(fecha_ingreso);
