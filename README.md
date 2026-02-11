# package-python-ebury-interview

## Requisitos previos

- **Docker Engine** con al menos 4 GB de RAM asignados (recomendado 8 GB).
- **Docker Compose v2.14.0** o superior.
- Al menos **2 CPUs** y **10 GB de disco** disponibles.

## Inicio rapido

```bash
# 1. Crear el fichero de entorno a partir del ejemplo
cp .env.example .env

# 2. (Solo Linux) Establecer el UID del usuario del host
echo "AIRFLOW_UID=$(id -u)" >> .env

# 3. Inicializar la base de datos y crear el usuario administrador
docker compose up airflow-init

# 4. Arrancar todos los servicios
docker compose up -d

# 5. Comprobar que los servicios estan sanos
docker compose ps

# 6. Verificar la conexion de dbt
docker compose --profile dbt run --rm dbt debug
```

Una vez levantados, los puntos de acceso son:

| Servicio | URL | Credenciales por defecto |
|---|---|---|
| Airflow UI / API | <http://localhost:8080> | `airflow` / `airflow` |
| Flower (monitoring Celery) | <http://localhost:5555> | -- |

> Flower no arranca por defecto. Activalo con `docker compose --profile flower up -d`.

## Arquitectura de servicios

```
                ┌───────────────┐
                │   PostgreSQL  │  Base de datos compartida
                └──────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
 ┌─────▼─────┐  ┌─────▼──────┐  ┌─────▼──────┐
 │  Airflow   │  │  App DB    │  │ Analytics  │
 │  metadata  │  │ (POSTGRES_ │  │ (DBT_DB_   │
 │  (airflow) │  │  DB)       │  │  NAME)     │
 └─────┬──────┘  └────────────┘  └─────▲──────┘
       │                               │
       │         ┌────────┐            │
       │         │ Valkey  │      ┌────┴─────┐
       │         │ (broker)│      │   dbt    │
       │         └────┬────┘      │ 1.11.4   │
       │              │           └──────────┘
 ┌─────▼──────────────▼──────────────────────────┐
 │              Airflow 3.1.7                     │
 │  ┌────────────┐  ┌───────────┐  ┌──────────┐  │
 │  │ API Server │  │ Scheduler │  │ DAG Proc │  │
 │  └────────────┘  └───────────┘  └──────────┘  │
 │  ┌────────────┐  ┌───────────┐  ┌──────────┐  │
 │  │   Worker   │  │ Triggerer │  │  Flower  │  │
 │  └────────────┘  └───────────┘  └──────────┘  │
 └────────────────────────────────────────────────┘
```

### Descripcion de cada servicio

| Servicio | Descripcion |
|---|---|
| **postgres** | Instancia PostgreSQL 16 compartida. Aloja la base de datos de la aplicacion (`POSTGRES_DB`), la base de datos de metadatos de Airflow (`AIRFLOW_DB_NAME`) y la base de datos de analytics de dbt (`DBT_DB_NAME`). Las dos ultimas se crean automaticamente mediante `init-db.sh` en el primer arranque. |
| **valkey** | Broker de mensajes Valkey 9.0.2 (fork open-source de Redis bajo licencia BSD). Actua como cola de tareas entre el scheduler y los workers cuando se usa `CeleryExecutor`. Solo expone el puerto `6379` dentro de la red interna de Docker (no accesible desde el host). Protegido con password, persistencia AOF habilitada y limite de memoria configurable. Compatible al 100% con el protocolo Redis. |
| **airflow-apiserver** | Sirve la interfaz web de Airflow y la REST API v2. Es el punto de entrada principal para los usuarios y para la comunicacion interna con los workers via la Execution API. |
| **airflow-scheduler** | Monitoriza todos los DAGs y sus tareas. Decide cuando una tarea esta lista para ejecutarse (dependencias cumplidas, horario alcanzado) y la encola en Valkey para que un worker la recoja. |
| **airflow-dag-processor** | Proceso dedicado (nuevo en Airflow 3.x) que parsea los ficheros Python del directorio `dags/` y los registra en la base de datos. En Airflow 2.x esta responsabilidad la tenia el scheduler directamente. |
| **airflow-worker** | Worker Celery que ejecuta las tareas encoladas. Puede escalarse horizontalmente (`docker compose up -d --scale airflow-worker=3`) para aumentar el paralelismo. |
| **airflow-triggerer** | Gestiona tareas deferibles (*deferrable operators*). Ejecuta bucles de eventos asincronos que esperan condiciones externas (por ejemplo, que un job en un servicio externo termine) sin ocupar un slot del worker. |
| **airflow-init** | Servicio de un solo uso que se ejecuta antes que el resto. Migra el esquema de la base de datos, crea el usuario administrador de la UI y verifica que el host tiene recursos suficientes (RAM, CPU, disco). |
| **airflow-cli** | Contenedor auxiliar para ejecutar comandos `airflow` ad-hoc. Solo se levanta bajo el profile `debug` (`docker compose --profile debug run airflow-cli <comando>`). |
| **flower** | Dashboard web para monitorizar los workers Celery en tiempo real (tareas activas, completadas, fallidas, tiempos). Solo se levanta bajo el profile `flower`. |
| **dbt** | dbt-postgres 1.9.0 para transformaciones de datos. Servicio one-shot que se ejecuta bajo el profile `dbt` mediante `docker compose --profile dbt run --rm dbt <comando>`. Conecta a la base de datos `analytics` dedicada, separada de la aplicacion y de Airflow. |

## Variables de entorno

Todas las variables se definen en el fichero `.env` (partir de `.env.example`). A continuacion se documenta cada una agrupada por contexto.

### PostgreSQL

Variables consumidas directamente por la imagen oficial de PostgreSQL.

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `POSTGRES_USER` | `app` | Nombre del superusuario de PostgreSQL. Se crea al inicializar el contenedor por primera vez. Este usuario es el propietario de la base de datos principal de la aplicacion. |
| `POSTGRES_PASSWORD` | `changeme` | Contrasena del superusuario de PostgreSQL. **Debe cambiarse** en cualquier entorno que no sea desarrollo local. |
| `POSTGRES_DB` | `app` | Nombre de la base de datos principal que PostgreSQL crea al arrancar. Destinada a la aplicacion (no a Airflow). |
| `POSTGRES_PORT` | `5432` | Puerto del host mapeado al puerto 5432 del contenedor. Permite conectarse a PostgreSQL desde el host (por ejemplo con `psql` o un IDE de BD). |

### Valkey

Variables para configurar el broker de mensajes.

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `VALKEY_PASSWORD` | `changeme` | Contrasena de autenticacion de Valkey. Se inyecta tanto en el `--requirepass` del servidor como en la `BROKER_URL` de Celery. **Debe cambiarse** en cualquier entorno que no sea desarrollo local. |
| `VALKEY_IMAGE_NAME` | `valkey/valkey:9.0.2` | Imagen Docker de Valkey. Permite fijar o actualizar la version sin modificar el `docker-compose.yml`. |
| `VALKEY_MAXMEMORY` | `256mb` | Limite maximo de memoria que Valkey puede usar. La politica de eviccion esta fijada a `noeviction`, lo que significa que Valkey rechazara escrituras cuando se alcance el limite en lugar de eliminar claves. Esto es lo recomendado para brokers de mensajes, ya que perder mensajes de la cola seria peor que rechazar temporalmente nuevas tareas. |

### Base de datos de Airflow

Estas variables alimentan el script `init-db.sh` y las cadenas de conexion de Airflow.

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `AIRFLOW_DB_USER` | `airflow` | Rol de PostgreSQL dedicado para Airflow. Se crea automaticamente via `init-db.sh` en el primer arranque del contenedor postgres. Mantenerlo separado de `POSTGRES_USER` sigue el principio de minimo privilegio. |
| `AIRFLOW_DB_PASSWORD` | `airflow` | Contrasena del rol `AIRFLOW_DB_USER`. **Debe cambiarse** en entornos no locales. |
| `AIRFLOW_DB_NAME` | `airflow` | Base de datos donde Airflow almacena sus metadatos (DAGs, ejecuciones, tareas, conexiones, variables, logs de eventos, etc.). Se crea automaticamente via `init-db.sh`. |

### dbt

Variables que configuran la conexion de dbt a PostgreSQL. Se inyectan en el contenedor y son leidas por `profiles.yml` via `env_var()`.

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `DBT_DB_USER` | `dbt` | Rol de PostgreSQL dedicado para dbt. Se crea automaticamente via `init-db.sh` en el primer arranque. Separado de los demas usuarios por principio de minimo privilegio. |
| `DBT_DB_PASSWORD` | `changeme` | Contrasena del rol `DBT_DB_USER`. **Debe cambiarse** en entornos no locales. |
| `DBT_DB_NAME` | `analytics` | Base de datos donde dbt gestiona las transformaciones (warehouse). Separada de la BD de aplicacion y de Airflow siguiendo el patron ELT estandar. |
| `DBT_SCHEMA` | `public` | Schema por defecto donde dbt materializa los modelos. Puede cambiarse para organizar los modelos en schemas distintos (ej. `staging`, `marts`). |

### Airflow - Configuracion general

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `AIRFLOW_UID` | `50000` | UID del usuario que ejecuta los procesos dentro de los contenedores de Airflow. En Linux debe coincidir con el UID del usuario del host (`id -u`) para evitar problemas de permisos en los volumenes montados. En macOS/Windows se puede dejar el valor por defecto. |
| `AIRFLOW_IMAGE_NAME` | `apache/airflow:3.1.7` | Imagen Docker usada para todos los servicios de Airflow. Permite cambiar a una imagen custom (por ejemplo, una extendida con dependencias adicionales) sin modificar el `docker-compose.yml`. |
| `AIRFLOW_API_PORT` | `8080` | Puerto del host mapeado a la API/UI de Airflow. Cambiar si hay conflicto con otro servicio en el puerto 8080. |
| `AIRFLOW_FERNET_KEY` | *(vacio)* | Clave de encriptacion simetrica (Fernet) que Airflow usa para cifrar valores sensibles almacenados en la base de datos (contrasenas en Connections, Variables marcadas como secretas). Si se deja vacia, Airflow genera una automaticamente, pero **debe fijarse en produccion** para que los datos cifrados sobrevivan a reinicios. Generar con: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |
| `AIRFLOW_WWW_USER` | `airflow` | Nombre de usuario del administrador de la interfaz web. Se crea durante `airflow-init`. |
| `AIRFLOW_WWW_PASSWORD` | `airflow` | Contrasena del administrador de la interfaz web. **Debe cambiarse** en cualquier entorno expuesto. |

### Airflow - Configuracion interna (docker-compose.yml)

Estas variables estan definidas directamente en el `docker-compose.yml` dentro del bloque `x-airflow-common`. Usan la convencion de Airflow `AIRFLOW__<SECCION>__<CLAVE>` que permite sobreescribir cualquier parametro de `airflow.cfg` mediante variables de entorno.

| Variable | Valor | Descripcion |
|---|---|---|
| `AIRFLOW__CORE__EXECUTOR` | `CeleryExecutor` | Define el motor de ejecucion de tareas. `CeleryExecutor` distribuye las tareas a traves de Valkey a uno o mas workers, permitiendo ejecucion paralela y escalado horizontal. Alternativas: `LocalExecutor` (un solo contenedor, sin Valkey ni workers) o `KubernetesExecutor` (un pod por tarea). |
| `AIRFLOW__CORE__AUTH_MANAGER` | `airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager` | Gestor de autenticacion y autorizacion de la UI. FAB (Flask-AppBuilder) Auth Manager es el gestor por defecto en Airflow 3.x. Controla login, roles (Admin, Viewer, User, Op) y permisos sobre DAGs y conexiones. |
| `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` | `postgresql+psycopg2://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PASSWORD}@postgres/${AIRFLOW_DB_NAME}` | Cadena de conexion SQLAlchemy a la base de datos de metadatos. Airflow la usa para almacenar el estado de DAGs, tareas, ejecuciones, XComs, conexiones y variables. El driver `psycopg2` es el recomendado para PostgreSQL. |
| `AIRFLOW__CELERY__RESULT_BACKEND` | `db+postgresql://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PASSWORD}@postgres/${AIRFLOW_DB_NAME}` | Backend donde Celery almacena los resultados de las tareas ejecutadas. Usa la misma base de datos de Airflow para simplificar la arquitectura. Permite al scheduler consultar el estado final de cada tarea. |
| `AIRFLOW__CELERY__BROKER_URL` | `redis://:${VALKEY_PASSWORD}@valkey:6379/0` | URL del broker de mensajes Celery. Incluye la contrasena de Valkey inyectada desde `VALKEY_PASSWORD`. El esquema `redis://` se mantiene porque Valkey es compatible con el protocolo Redis. Valkey actua como cola FIFO: el scheduler encola las tareas y los workers las consumen. La base de datos `0` se usa por defecto; pueden usarse otras (ej. `/1`, `/2`) si Valkey se comparte con otros servicios. |
| `AIRFLOW__CORE__FERNET_KEY` | `${AIRFLOW_FERNET_KEY:-}` | Clave Fernet inyectada desde la variable de entorno del `.env`. Ver la descripcion de `AIRFLOW_FERNET_KEY` arriba. |
| `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION` | `true` | Cuando Airflow detecta un DAG nuevo, lo registra en estado **pausado**. Esto evita ejecuciones involuntarias de DAGs recien desplegados. El usuario debe activar cada DAG manualmente desde la UI o la API. |
| `AIRFLOW__CORE__LOAD_EXAMPLES` | `false` | Controla si Airflow carga los DAGs de ejemplo incluidos en la imagen. Se desactiva para mantener la interfaz limpia y evitar confusiones con los DAGs reales del proyecto. |
| `AIRFLOW__CORE__EXECUTION_API_SERVER_URL` | `http://airflow-apiserver:8080/execution/` | URL interna que los workers y el triggerer usan para comunicarse con el API Server via la Execution API (nuevo en Airflow 3.x). Esta API reemplaza el acceso directo a la base de datos desde los workers, mejorando el aislamiento y la seguridad. |
| `AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK` | `true` | Habilita un servidor HTTP ligero en el scheduler (puerto 8974) que responde a peticiones de healthcheck. Docker Compose lo usa para verificar que el scheduler esta vivo y reiniciarlo si deja de responder. |
| `AIRFLOW_CONFIG` | `/opt/airflow/config/airflow.cfg` | Ruta al fichero de configuracion de Airflow dentro del contenedor. Se monta desde el directorio local `config/`. Si no existe, Airflow genera uno con valores por defecto durante `airflow-init`. Las variables de entorno `AIRFLOW__*` siempre tienen precedencia sobre este fichero. |
| `_PIP_ADDITIONAL_REQUIREMENTS` | *(vacio)* | Paquetes pip adicionales que se instalan al arrancar cada contenedor. Util para pruebas rapidas (ej. `apache-airflow-providers-google==10.0.0`). **No recomendado para produccion**: al ejecutarse en cada arranque, ralentiza el inicio. En su lugar, crear una imagen custom con un `Dockerfile`. |
| `DUMB_INIT_SETSID` | `0` | Solo se aplica al worker. Controla como `dumb-init` (el proceso init del contenedor) propaga las senales. Con valor `0`, las senales se envian solo al proceso hijo directo (Celery) en lugar de a todo el grupo de procesos. Esto permite un *graceful shutdown* del worker: Celery termina las tareas en curso antes de apagarse. |
| `_AIRFLOW_DB_MIGRATE` | `true` | Solo en `airflow-init`. Indica al entrypoint que ejecute `airflow db migrate` para crear/actualizar las tablas del esquema de metadatos. |
| `_AIRFLOW_WWW_USER_CREATE` | `true` | Solo en `airflow-init`. Indica al entrypoint que cree el usuario administrador de la UI si no existe. |
| `CONNECTION_CHECK_MAX_COUNT` | `0` | Solo en `airflow-cli`. Numero maximo de reintentos para comprobar la conexion a la base de datos al arrancar. Con `0` se desactiva la comprobacion, ya que el CLI se usa de forma puntual y no necesita esperar a que la BD este lista. |

### Variables opcionales

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `AIRFLOW_PROJ_DIR` | `.` (directorio actual) | Ruta base en el host desde la que se montan los directorios `dags/`, `logs/`, `config/` y `plugins/`. Util si los ficheros del proyecto estan en un directorio distinto al del `docker-compose.yml`. |
| `FLOWER_PORT` | `5555` | Puerto del host mapeado a la UI de Flower. Solo relevante si se activa el profile `flower`. |

## Estructura de directorios

```
.
├── docker-compose.yml     # Definicion de todos los servicios
├── init-db.sh            # Crea las BDs y usuarios de Airflow y dbt en Postgres
├── .env.example           # Plantilla de variables de entorno
├── .env                   # Variables reales (no versionado)
├── dags/                  # Ficheros Python con las definiciones de DAGs
├── logs/                  # Logs de ejecucion (no versionado)
├── config/                # Configuracion custom de Airflow (airflow.cfg)
├── plugins/               # Plugins custom de Airflow (operators, hooks, etc.)
└── dbt/                   # Proyecto dbt
    ├── dbt_project.yml    # Configuracion del proyecto dbt
    ├── profiles.yml       # Conexion a PostgreSQL (via variables de entorno)
    ├── models/            # Modelos SQL/Python de transformacion
    ├── seeds/             # Ficheros CSV para carga estatica
    ├── macros/            # Macros Jinja reutilizables
    └── tests/             # Tests custom de datos
```

## Comandos utiles

```bash
# Ver logs de un servicio concreto
docker compose logs -f airflow-scheduler

# Ejecutar un comando Airflow ad-hoc
docker compose --profile debug run --rm airflow-cli airflow dags list

# Escalar workers horizontalmente
docker compose up -d --scale airflow-worker=3

# Activar Flower para monitorizar Celery
docker compose --profile flower up -d

# dbt — verificar conexion
docker compose --profile dbt run --rm dbt debug

# dbt — ejecutar modelos
docker compose --profile dbt run --rm dbt run

# dbt — ejecutar tests de datos
docker compose --profile dbt run --rm dbt test

# dbt — generar documentacion
docker compose --profile dbt run --rm dbt docs generate

# Parar todos los servicios conservando los datos
docker compose down

# Parar y eliminar todos los datos (volumenes)
docker compose down -v
```
