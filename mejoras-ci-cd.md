# Propuestas futuras de mejora para CI/CD

Este documento contiene propuestas de evolución del pipeline. No describe funcionalidades implementadas actualmente.

## Reestructuración de servicios backend

La configuración actual de CI/CD de `auth-service`, `gateway` y `profile` es funcional, pero cada workflow combina validación de código, construcción de imagen y despliegue. Como mejora futura se propone aplicar separación de responsabilidades y reducir duplicación.

### Flujos CI independientes

Crear un workflow CI por servicio, por ejemplo `ci-auth.yml`, `ci-gateway.yml` y `ci-profile.yml`.

- Ejecutar ante push a ramas de trabajo y pull requests hacia `main` o `develop`.
- Instalar dependencias y ejecutar `ruff`, `pytest` y `behave` donde corresponda.
- Generar reportes de cobertura y badges.
- Validar la construcción de la imagen y los smoke tests de `/livez` y `/readyz`.
- No publicar imágenes ni modificar AWS.

### Workflow reutilizable para AWS

Extraer la lógica común de OIDC, login en ECR, build/push de Docker y despliegue mediante SSM a un workflow reutilizable con `workflow_call`.

El workflow recibiría parámetros como:

- Nombre del repositorio ECR.
- Nombre del servicio de Docker Compose.
- Rol IAM que debe asumir GitHub Actions.
- Variable de tag que debe actualizarse en la EC2.

### Flujos CD independientes

Crear un workflow CD por servicio, por ejemplo `cd-auth.yml`, `cd-gateway.yml` y `cd-profile.yml`.

- Ejecutar estrictamente ante push a `main` después de un merge exitoso.
- Invocar el workflow reutilizable de AWS.
- Mantener los permisos de escritura en AWS asociados únicamente al despliegue productivo.

## Reestructuración del frontend

### CI del cliente web

Crear un `ci-frontend.yml` para ejecutar en pull requests:

- Instalación reproducible de dependencias.
- Lint y typecheck.
- Tests disponibles para el cliente.
- Validación del build web antes del merge.

### CD web separado

Crear un `cd-frontend-web.yml` para publicar la versión web ante push a `main`, separado de la construcción de aplicaciones móviles.

### Release Android separado

Crear un `release-android.yml` para ejecutar `eas build` únicamente de forma manual mediante `workflow_dispatch` o ante un tag/release de GitHub, por ejemplo `v1.2.0`.

La construcción de un APK consume más tiempo y cuota que un despliegue web, por lo que no debería ejecutarse ante cada push a `main`.

## Objetivo del roadmap

Separar validación, publicación y release permite reducir duplicación, limitar permisos AWS, controlar mejor los entornos y evitar que un release móvil costoso bloquee o acompañe innecesariamente a cada despliegue web.
