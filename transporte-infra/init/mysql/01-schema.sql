-- =====================================================================
--  MS2 · viajes_db  (MySQL 8)
--  Contrato Cero §5 · tarifas 1—N viajes, viajes 1—N paradas
--  Este archivo va en transporte-infra/init/mysql/01-schema.sql
--  Se monta como docker-entrypoint-initdb.d y corre solo al crear el volumen.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS viajes_db
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE viajes_db;

SET time_zone = '+00:00';   -- todo en UTC (Contrato §3, regla 3)

-- ---------------------------------------------------------------------
-- tarifas · catalogo fijo, id 1..4 (Contrato §3)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tarifas (
  id                 INT           NOT NULL,
  tipo_servicio      VARCHAR(20)   NOT NULL,
  tarifa_base        DECIMAL(10,2) NOT NULL,
  costo_por_km       DECIMAL(10,2) NOT NULL,
  costo_por_minuto   DECIMAL(10,2) NOT NULL,
  recargo_hora_pico  DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  activa             BOOLEAN       NOT NULL DEFAULT TRUE,
  PRIMARY KEY (id),
  CONSTRAINT ck_tarifas_tipo CHECK (tipo_servicio IN ('economico','estandar','confort','xl'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- viajes · id 1..25000, tabla que carga los >=20 000 registros de fake data
-- pasajero_id, conductor_id y vehiculo_id son referencias LOGICAS a
-- PostgreSQL (MS1). No hay FK entre motores (Contrato §3).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS viajes (
  id                 INT           NOT NULL AUTO_INCREMENT,
  pasajero_id        INT           NOT NULL,   -- usuarios.id      1..20000
  conductor_id       INT           NOT NULL,   -- conductores.id   1..600
  vehiculo_id        INT           NOT NULL,   -- vehiculos.id     1..600
  tarifa_id          INT           NOT NULL,
  estado             VARCHAR(20)   NOT NULL,
  metodo_pago        VARCHAR(20)   NOT NULL,
  distrito_origen    VARCHAR(60)   NOT NULL,
  distrito_destino   VARCHAR(60)   NOT NULL,
  direccion_origen   VARCHAR(160)  NULL,
  direccion_destino  VARCHAR(160)  NULL,
  distancia_km       DECIMAL(6,2)  NULL,
  duracion_min       INT           NULL,
  monto_total        DECIMAL(10,2) NULL,
  solicitado_en      DATETIME      NOT NULL,
  iniciado_en        DATETIME      NULL,
  finalizado_en      DATETIME      NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_viajes_tarifa FOREIGN KEY (tarifa_id) REFERENCES tarifas(id),
  CONSTRAINT ck_viajes_estado CHECK (estado IN ('solicitado','en_curso','finalizado','cancelado')),
  CONSTRAINT ck_viajes_pago   CHECK (metodo_pago IN ('efectivo','tarjeta','billetera')),
  INDEX ix_viajes_pasajero  (pasajero_id),
  INDEX ix_viajes_conductor (conductor_id),
  INDEX ix_viajes_estado    (estado),
  INDEX ix_viajes_fecha     (solicitado_en),
  INDEX ix_viajes_ruta      (distrito_origen, distrito_destino)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- paradas · 1—N desde viajes. Un viaje puede tener 0..n paradas intermedias.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS paradas (
  id           BIGINT        NOT NULL AUTO_INCREMENT,
  viaje_id     INT           NOT NULL,
  orden        INT           NOT NULL,
  distrito     VARCHAR(60)   NOT NULL,
  direccion    VARCHAR(160)  NULL,
  latitud      DECIMAL(9,6)  NULL,
  longitud     DECIMAL(9,6)  NULL,
  llegada_en   DATETIME      NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_paradas_viaje FOREIGN KEY (viaje_id) REFERENCES viajes(id) ON DELETE CASCADE,
  CONSTRAINT uk_paradas_viaje_orden UNIQUE (viaje_id, orden),
  INDEX ix_paradas_viaje (viaje_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Catalogo de tarifas (los 4 ids son fijos y los usan P3 y P5)
-- ---------------------------------------------------------------------
INSERT IGNORE INTO tarifas
  (id, tipo_servicio, tarifa_base, costo_por_km, costo_por_minuto, recargo_hora_pico, activa)
VALUES
  (1, 'economico', 4.00,  1.10, 0.25, 1.50, TRUE),
  (2, 'estandar',  5.50,  1.45, 0.32, 2.00, TRUE),
  (3, 'confort',   8.00,  1.90, 0.45, 3.00, TRUE),
  (4, 'xl',       11.00,  2.40, 0.55, 4.00, TRUE);

-- ---------------------------------------------------------------------
-- Usuario de aplicacion (Contrato §9 · nunca root desde la app)
-- El compose de MySQL ya crea app_ms2 con MYSQL_USER/MYSQL_PASSWORD.
-- Si lo creas a mano:
--   CREATE USER IF NOT EXISTS 'app_ms2'@'%' IDENTIFIED BY '<clave del .env>';
--   GRANT SELECT, INSERT, UPDATE, DELETE ON viajes_db.* TO 'app_ms2'@'%';
--   FLUSH PRIVILEGES;
-- ---------------------------------------------------------------------
