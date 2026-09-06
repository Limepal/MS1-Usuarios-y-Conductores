// MS3 · crea el usuario de aplicacion y los indices. Contrato §6.
// mongo ejecuta este archivo con la variable de entorno MONGO_APP_PASS disponible.
const clave = process.env.MONGO_APP_PASS || "cambiame_ms3";

db = db.getSiblingDB("calificaciones_db");

db.createUser({
  user: "app_ms3",
  pwd: clave,
  roles: [{ role: "readWrite", db: "calificaciones_db" }]
});

db.createCollection("calificaciones");
db.calificaciones.createIndex({ viaje_id: 1 }, { unique: true });
db.calificaciones.createIndex({ conductor_id: 1, creado_en: -1 });
db.calificaciones.createIndex({ tags: 1 });
db.calificaciones.createIndex({ comentario: "text" });

db.createCollection("reportes");
db.reportes.createIndex({ calificacion_id: 1, estado: 1 });

print("MS3: usuario app_ms3 e indices creados en calificaciones_db");
