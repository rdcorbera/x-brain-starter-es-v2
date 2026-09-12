# Manifiesto de fuentes crudas

Registro de todo original archivado en `raw/`. Lo mantiene `/x-procesar-inbox`; no se edita a
mano.

Cada fila dice de dónde salió un archivo, **su SHA-256** y a qué parte del cerebro se atribuyó.
Lo primero y lo último es lo que hace posible reconstruir con `/x-reconstruir`; el hash es lo que
convierte la regla «nada se edita» en algo comprobable:

```bash
./brain verify-raw        # ¿sigue cada original siendo el que se archivó?
```

| Fecha | Archivo | SHA-256 | Origen | Destino en el cerebro |
|---|---|---|---|---|
