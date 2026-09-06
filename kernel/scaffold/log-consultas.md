# Log de consultas

Qué se le ha **preguntado** a este cerebro: una línea por consulta, agrupada por
fecha y con la más reciente arriba. Lo escribe `/x-consultar`.

Va aparte de `log.md` a propósito. Aquel registra **escrituras** —«quien escribe,
loguea»— y otros skills lo leen para responder «qué pasó»; una consulta no cambia
nada, así que mezclarlas haría ruido en la respuesta de todos ellos.

Existe porque **v1 no registraba ninguna pregunta**, y sin eso hay dos cosas que
no se pueden saber mirando hacia atrás: con qué frecuencia se pregunta cada cosa
—las competency questions del kernel lo tienen estimado, no medido— y cuántas
consultas hay por cada ingesta, que es lo que decide cuándo conviene una capa
consultable en vez de navegar índices.

Cada línea lleva la pregunta, cuántos documentos hubo que abrir para responderla
y si la respuesta se archivó. Los encabezados de fecha son `## YYYY-MM-DD`, y eso
lo comprueba V3.
