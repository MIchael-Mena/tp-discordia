# TP-Discordia

Repositorio raíz de trabajo del proyecto **TP-Discordia** para la materia
Ingeniería de Software II.

Este repositorio funciona como un contenedor de documentación, configuración y
herramientas comunes. Los servicios de la aplicación se mantienen como
repositorios Git independientes dentro de este directorio y, por ese motivo,
no se versionan desde este repositorio raíz.

## Repositorios independientes

| Servicio | Descripción |
| --- | --- |
| [`auth-service`](./auth-service) | Gestión de cuentas, autenticación, sesiones y tokens |
| [`gateway`](./gateway) | API Gateway, validación JWT y enrutamiento |
| [`profile`](./profile) | Gestión de perfiles de usuario |
| [`web-client`](./web-client) | Cliente web/mobile basado en Expo y React Native |
| [`text-channel`](./text-channel) | Servicio de canales de texto |
| [`server`](./server) | Servicio de servidores de la plataforma |
| [`infra`](./infra) | Infraestructura, despliegue y configuración operativa |

Estos directorios están excluidos en [`.gitignore`](./.gitignore), al igual
que la clave privada `discordia-key.pem`.

## Archivos del repositorio raíz

- [`AGENTS.md`](./AGENTS.md): contexto, arquitectura y convenciones del proyecto.
- [`Backlog.json`](./Backlog.json): backlog general y seguimiento de tareas.
- [`Backlog-text-channel.md`](./Backlog-text-channel.md): backlog específico del
  servicio de canales de texto.
- [`repos.json`](./repos.json): configuración de los repositorios y sus ramas.
- [`limpiar_ramas.py`](./limpiar_ramas.py): utilidad para limpiar ramas locales
  según la configuración del proyecto.
- [`mejoras-ci-cd.md`](./mejoras-ci-cd.md): documentación de mejoras de CI/CD.

## Clonar el proyecto

```bash
git clone git@github.com:MIchael-Mena/tp-discordia.git
cd tp-discordia
```

Después de clonar este repositorio, los servicios independientes deben
obtenerse o actualizarse por separado dentro de sus respectivos directorios.

## Arquitectura general

La plataforma está compuesta por varios microservicios:

```text
web-client -> gateway -> auth-service
                    -> profile
                    -> server

auth-service --eventos RabbitMQ--> profile
infra -------> bases de datos, RabbitMQ y despliegue
```

La documentación específica de cada servicio se encuentra en el README y la
configuración del repositorio correspondiente.
