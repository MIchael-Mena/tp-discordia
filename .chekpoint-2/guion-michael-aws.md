## Guion

### Diapo 1

Al planificar el entorno productivo evaluamos plataformas PaaS como Railway, pero las descartamos rápidamente: la gestión de variables y configuraciones quedaba centralizada en una sola cuenta personal —lo que trababa el trabajo en equipo— y no nos brindaba control sobre el aislamiento de redes. Elegimos AWS porque nos da control granular mediante IAM, permite integrar despliegues seguros con OIDC y nos da flexibilidad para diseñar nuestra propia topología de red.

### Diapo 2

En cuanto a la arquitectura, la prioridad fue **separar la persistencia de los contenedores de la aplicación**. La capa de microservicios corre en contenedores Docker sobre una instancia Amazon EC2, mientras que las bases de datos viven de forma independiente en **Amazon RDS** bajo el patrón *Database-per-Service*: PostgreSQL 16 para `auth-service` y PostgreSQL 17 para `profile`.

Esto representó una evolución clave: al principio las bases corrían dentro de Docker Compose en el mismo host. Migrarlas a RDS no solo cumplió con la pauta de la cátedra, sino que nos permitió delegar backups automáticos en AWS y liberar recursos críticos en la máquina: recuperamos más de 1 GB de disco entre imágenes y volúmenes, y descomprimimos la memoria RAM al retirar dos motores de base de datos del host.

A nivel de red y perímetro, implementamos un esquema cerrado: **ningún microservicio publica puertos al host de la EC2**. El único puerto expuesto a internet es el puerto 80, administrado por **Traefik v3.7** como Ingress Reverse Proxy.
Internamente, aislamos el tráfico en dos redes Docker bridge:
  • La red **proxy**, donde Traefik recibe las peticiones públicas en `/api`, aplica `stripprefix` y las deriva al **API Gateway** en el puerto interno 22000, que actúa como único punto de entrada de la API.
  • La red **rabbitmq-network**, una red interna sin salida a internet donde corre el broker RabbitMQ, a la que únicamente acceden `auth-service` para publicar eventos y `profile-worker` para consumirlos.
  
Por su parte, los **Security Groups de Amazon RDS** están configurados para aceptar conexiones únicamente desde la IP privada de la EC2, por lo que las bases de datos son completamente inaccesibles desde internet.

### Diapo 3

Para el cómputo seleccionamos una instancia **t3.small** (2 vCPUs y 2.0 GB de RAM). Con los 7 contenedores del stack en marcha, el consumo se mantiene en torno a 1 GB, dejándonos un margen libre de casi 900 MB para incorporar nuevos microservicios en Python (que consumen entre 50 y 80 MB cada uno).
Por último, como cada deploy descarga una nueva imagen desde Amazon ECR con tags inmutables, mitigamos el riesgo de saturación de disco programando un **timer diario de systemd** (`discordia-prune-images.timer`), que purga automáticamente imágenes huérfanas de más de 2 horas sin afectar los contenedores en ejecución, mas una politica de ciclo de vida que limita la cantidad de imágenes almacenadas a 5.

Asumimos conscientemente el trade-off de esta arquitectura: ganamos aislamiento, persistencia segura y control de red, a cambio de una mayor complejidad operativa en la configuración de Security Groups, redes Docker y variables de entorno.

Toda esta arquitectura en AWS necesita un mecanismo confiable para recibir los cambios de código. Delimitamos el alcance separando lo operativo de lo automatizado: el archivo Compose y la configuración del host aún se gestionan de forma manual, pero la construcción, validación y despliegue continuo de los contenedores está automatizada con GitHub Actions.

### Diapo CI/CD

Para explicar en detalle cómo funciona este pipeline, qué condiciones bloqueantes exigimos antes de tocar producción y cómo resolvemos la autenticación segura sin contraseñas fijas, le paso la palabra a Pablo.