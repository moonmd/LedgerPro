# LedgerPro Accounting Platform

## Badges

[![CI/CD](https://github.com/YOUR_USERNAME/YOUR_REPONAME/actions/workflows/cicd.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPONAME/actions/workflows/cicd.yml) <!-- Replace YOUR_USERNAME/YOUR_REPONAME -->
<!-- Add other badges here, e.g., Code Coverage, Version, License -->

## Overview

LedgerPro is a cloud-native, small-business accounting platform designed to replicate and surpass the core functionalities of existing solutions like QuickBooks Online. It aims to provide robust, intuitive, and highly adaptable financial management tools, from double-entry bookkeeping and invoicing to payroll and advanced reporting.

Built with modern cloud technologies and a developer-friendly architecture (including a planned marketplace and public API), LedgerPro focuses on scalability, reliability, security, and extensibility.

## CI/CD

This project uses [GitHub Actions](.github/workflows/cicd.yml) for Continuous Integration and Continuous Delivery. The current CI/CD pipeline includes:
- **Linting:** Code style checks for both frontend (Next.js/TypeScript) and backend (Python/Django).
- **Testing:** Execution of unit and integration tests for frontend and backend components (currently placeholder tests, to be expanded).
- **Building:** Placeholder build steps for frontend and backend artifacts.
<!-- Further steps like deployment to staging/production environments can be added. -->

## Dependencies (Core Tech Stack)

LedgerPro is built with a modern, scalable technology stack:

- **Frontend:**
  - React 18 + TypeScript
  - Next.js 14 (App Router)
  - Tailwind CSS
  - Zustand (or Redux Toolkit for state management - specified in PRD)

- **Backend:**
  - Python 3.12
  - Django 5 + Django REST Framework (DRF)
  - Celery + Redis (for asynchronous tasks and message queuing)

- **Database:**
  - PostgreSQL 16 (Operational DB)
  - Redis 7 (Cache, Celery Broker)

- **Infrastructure & Deployment:**
  - Docker / Docker Compose (for local development and containerization)
  - Kubernetes (EKS/GKE - planned for production)
  - Terraform (planned for Infrastructure as Code)

- **Third-Party Service Integrations (Key Examples):**
  - Plaid (Bank Feeds)
  - SendGrid (Transactional Emails)
  - Stripe / PayPal (Payment Processing - planned)
  - TaxJar / AvaTax (Tax Calculation - planned)

## Automated Development Setup Script (Recommended)

For a quicker and more automated setup of your local development environment (especially when using Docker Compose), a bash script `setup_dev_env.sh` is provided in the project root.

This script will:
- Prompt you for necessary API keys and secrets (Plaid, SendGrid, Django Secret Key).
- Create the `ledgerpro/backend/.env` file with your inputs and appropriate defaults for Docker.
- **Check for frontend dependencies:** If a lockfile (`package-lock.json`, etc.) is missing in `ledgerpro/frontend`, it will offer to run `npm install` to generate it. This is crucial for the frontend Docker build.
- Check for Docker and Docker Compose installations (and prefer Docker Compose V2 if available).
- Optionally clean up any previous Docker environment for this project.
- Build and start the Docker Compose services (backend, database, redis if configured).
- Wait for the database service to be ready.
- Run Django database migrations inside the backend container.
- Optionally, prompt you to create a Django superuser interactively.
- Provide final instructions on accessing the services.

**How to use the script:**

1.  **Ensure Prerequisites:** You still need Git, Docker, and Docker Compose installed.
2.  **Clone the Repository:** (If you haven't already)
    ```bash
    git clone https://github.com/YOUR_USERNAME/YOUR_REPONAME.git # Replace
    cd YOUR_REPONAME
    ```
3.  **Make the script executable:**
    ```bash
    chmod +x setup_dev_env.sh
    ```
4.  **Run the script:**
    ```bash
    ./setup_dev_env.sh
    ```
5.  **Follow the prompts.** The script will guide you through providing necessary configurations.

After the script completes, your Dockerized backend environment should be up and running. You can then proceed to start the frontend development server separately if you wish (see "Frontend Setup" section below).

Using this script is recommended over fully manual setup if you plan to use Docker Compose. The manual steps below are still useful for understanding the components or for setups not using Docker for all services.

## Local Development Setup

This section guides you through setting up LedgerPro for local development and testing.

### Prerequisites

- **Git:** For cloning the repository.
- **Python:** Version 3.10+ (project uses 3.12).
- **Node.js & npm:** For frontend development (check `ledgerpro/frontend/package.json` for version, e.g., Node 20.x).
- **Docker & Docker Compose:** (Optional but Recommended) For easily running PostgreSQL, Redis, and potentially the entire application stack.

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPONAME.git # Replace YOUR_USERNAME/YOUR_REPONAME
cd YOUR_REPONAME # Or your chosen directory name
```

### 2. Backend Setup (Django / Python)

These steps are for running the backend directly on your host machine.

#### a. Navigate to Backend Directory
```bash
cd ledgerpro/backend
```

#### b. Create and Activate a Python Virtual Environment
```bash
python -m venv venv
# On macOS/Linux
source venv/bin/activate
# On Windows
# venv\Scripts\activate
```

#### c. Install Python Dependencies
```bash
pip install -r requirements.txt
```

#### d. Configure Environment Variables

The backend requires several environment variables for configuration. These are typically stored in a `.env` file in the `ledgerpro/backend` directory.

1.  **Create a `.env` file** in `ledgerpro/backend/` by copying the example below:
    ```env
# ledgerpro/backend/.env
# Django Settings
DJANGO_SECRET_KEY='your_strong_secret_key_here' # Replace with a real secret key
DEBUG=True

# Database (PostgreSQL - for local Docker setup or external DB)
# If using local Docker Compose setup (see docker-compose.yml):
DATABASE_URL='postgres://ledgerpro:secret@localhost:5432/ledgerpro'
# If using SQLite for very basic local testing (not recommended for full features):
# DATABASE_URL='sqlite:///./db.sqlite3'

# Redis (for Celery, Caching - if using local Docker setup or external Redis)
REDIS_URL='redis://localhost:6379/0'

# Plaid API Keys (obtain from Plaid dashboard)
PLAID_CLIENT_ID='your_plaid_client_id'
PLAID_SECRET_SANDBOX='your_plaid_secret_for_sandbox'
PLAID_SECRET_DEVELOPMENT='your_plaid_secret_for_development'
PLAID_ENV='sandbox' # Or 'development'
# PLAID_PRODUCTS and PLAID_COUNTRY_CODES are often set in settings.py defaults but can be overridden here

# SendGrid API Key (obtain from SendGrid dashboard)
SENDGRID_API_KEY='YOUR_SENDGRID_API_KEY_PLACEHOLDER'
DEFAULT_FROM_EMAIL='noreply@yourdomain.com' # Your default sending email

# Allowed Hosts (for Django DEBUG=False)
# ALLOWED_HOSTS='localhost,127.0.0.1,.yourproductiondomain.com'
    ```
2.  **Important:** Replace placeholder values (like `your_strong_secret_key_here`, Plaid keys, SendGrid key) with your actual development keys.
    - For `DJANGO_SECRET_KEY`, you can generate one using Django's `get_random_secret_key()` or an online generator.
    - The `DATABASE_URL` provided is configured for the PostgreSQL service in the `docker-compose.yml` file. If you are not using Docker for PostgreSQL, adjust this URL accordingly.
    - For Plaid and SendGrid, sign up for their services and get API keys from their respective dashboards. Use sandbox/development keys for local development.

The `ledgerpro_project/settings.py` file is configured to read these variables using `python-dotenv`.

#### e. Run Database Migrations

Ensure your PostgreSQL database server is running (e.g., via Docker Compose, see section below) before running migrations if you configured a PostgreSQL `DATABASE_URL`.
```bash
python manage.py makemigrations api # Ensure all model changes are captured (usually needed if you change models)
python manage.py migrate
```

#### f. Create a Superuser (Optional but Recommended)
```bash
python manage.py createsuperuser
```
Follow the prompts to create an administrator account for accessing the Django admin interface.

#### g. Run the Django Development Server
```bash
python manage.py runserver
```
The backend API should now be running, typically at `http://127.0.0.1:8000/`.

### 3. Frontend Setup (Next.js / React)

These steps are for running the frontend directly on your host machine.

#### a. Navigate to Frontend Directory
```bash
# From the project root directory
cd ledgerpro/frontend
```

#### b. Install Node.js Dependencies
```bash
npm install
# This command will also generate or update your `package-lock.json` (or `yarn.lock`/`pnpm-lock.yaml`).
# **Important:** Ensure this lockfile is committed to your Git repository for consistent builds.
# Or if you prefer using yarn and have a yarn.lock file:
# yarn install
```

#### c. Configure Frontend Environment Variables (Optional)

The frontend might require environment variables, especially for connecting to the backend API.
Next.js uses `.env.local` for local environment variables. Create this file in the `ledgerpro/frontend` directory if needed.

Example `ledgerpro/frontend/.env.local`:
```env
# ledgerpro/frontend/.env.local
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api

# Add other frontend specific environment variables here if any
# Variables prefixed with NEXT_PUBLIC_ are exposed to the browser.
```
If this variable is not set, the frontend might default to a relative path or a hardcoded URL for the API, which might work if served from the same domain, but explicitly setting it is good practice for clarity.

#### d. Run the Next.js Development Server
```bash
npm run dev
```
The frontend development server should now be running, typically at `http://localhost:3000/`.

### 4. Docker Compose Setup (Recommended for Integrated Services)

For a more integrated local development experience, especially for managing services like PostgreSQL and Redis, using Docker Compose is recommended. The project includes a `docker-compose.yml` file at the root directory.

The current `docker-compose.yml` sets up services for:
- `backend`: The Django application.
- `db`: A PostgreSQL database instance (data is persisted in a Docker volume named `postgres_data`).
- `redis`: A Redis instance (if you add it to your docker-compose for Celery/Caching).
  *(Note: The provided `docker-compose.yml` in previous steps had Redis commented out; ensure it's uncommented if Celery is actively used or caching is needed.)*

The frontend service is also defined (`Dockerfile.frontend`) but might be run separately for a faster development feedback loop if preferred (e.g., `npm run dev` directly on host).

#### a. Prerequisites
- Docker and Docker Compose installed on your system.

#### b. Environment Variables for Docker Compose

The Docker Compose setup for the `backend` service will also utilize the `.env` file located in `ledgerpro/backend/.env` for its configuration (e.g., `DJANGO_SECRET_KEY`, Plaid keys, etc.). Make sure this file is created and configured as described in the "Backend Setup" section.

The `DATABASE_URL` in your `ledgerpro/backend/.env` should match the PostgreSQL service defined in `docker-compose.yml`. The example provided typically is:
```env
DATABASE_URL='postgres://ledgerpro:secret@db:5432/ledgerpro'
```
**Note the hostname `db`**: This refers to the PostgreSQL service name within the Docker network, not `localhost`.

Similarly, if you use Redis via Docker Compose:
```env
REDIS_URL='redis://redis:6379/0'
```
**Note the hostname `redis`**.

#### c. Determine Your Docker Compose Command

LedgerPro supports both Docker Compose V2 (`docker compose`) and V1 (`docker-compose`).
- **Docker Compose V2** is the current standard, typically included with Docker Desktop, and invoked as `docker compose` (with a space). It's generally recommended.
- **Docker Compose V1** is the older, Python-based version, invoked as `docker-compose` (with a hyphen).

The automated `./setup_dev_env.sh` script will attempt to detect and use V2 if available, otherwise V1.
If running commands manually, please determine which version you have installed:
```bash
# Check for V2
docker compose version
# Check for V1
docker-compose --version
```
Use the command that works for your system in the examples below. We will use `[docker compose command]` as a placeholder.

#### d. Build and Run Services with Docker Compose

From the **project root directory** (where `docker-compose.yml` is located):
```bash
# Build the images and start the services
# Using V2:
docker compose up --build
# Or using V1:
# docker-compose up --build

# To run in detached mode (in the background):
# Using V2:
docker compose up --build -d
# Or using V1:
# docker-compose up --build -d
```
This command will:
- Build the Docker images for the `frontend` and `backend` services if they don't exist or if their Dockerfiles have changed.
- Start all services defined in `docker-compose.yml`.
- You will see logs from all services in your terminal (unless using detached mode).

#### e. Initial Setup (First time running with Docker Compose)

If this is the first time you are running the stack with Docker Compose, or after a database reset, you'll need to run database migrations and potentially create a superuser **inside the running backend container**.

1.  **Open a new terminal window.**
2.  **Find the name of your running backend container (usually `ledgerpro-backend-1` or similar if using default project name from compose file, or `yourprojectname_backend_1`):**
    ```bash
    # Using V2:
    docker compose ps
    # Or using V1:
    # docker-compose ps
    ```
3.  **Execute commands inside the backend container:**
    ```bash
    # Replace 'ledgerpro-backend-1' with your actual container name/ID if different.
    # Using V2:
    docker compose exec backend python manage.py makemigrations api
    docker compose exec backend python manage.py migrate
    docker compose exec backend python manage.py createsuperuser

    # Or using V1:
    # docker-compose exec backend python manage.py makemigrations api
    # docker-compose exec backend python manage.py migrate
    # docker-compose exec backend python manage.py createsuperuser
    ```

#### f. Accessing Services

- **Backend API:** Should be accessible at `http://localhost:8000` (as mapped in `docker-compose.yml`).
- **Frontend (if run via Docker Compose):** Should be accessible at `http://localhost:3000`.
- **PostgreSQL Database:** Accessible to the backend service at `db:5432`. If you need to connect from your host machine (e.g., with a DB tool), it's usually mapped to `localhost:5432` (check `ports` in `docker-compose.yml` for the `db` service).

#### g. Stopping Docker Compose Services
```bash
# If running in the foreground, press Ctrl+C in the terminal.
# If running in detached mode, or from another terminal:
# Using V2:
docker compose down
# Or using V1:
# docker-compose down

# To stop and remove volumes (e.g., to reset the database):
# Using V2:
docker compose down -v
# Or using V1:
# docker-compose down -v
```

## Cloud Installation (Backend - Conceptual Guide)

Deploying a Django application like LedgerPro to a cloud environment involves several key considerations. Below is a conceptual guide. Specific steps will vary greatly depending on your chosen cloud provider (e.g., AWS, Google Cloud, Azure, Heroku, DigitalOcean) and deployment strategy.

### 1. Application Server (WSGI)

- **WSGI Server:** Django's development server (`manage.py runserver`) is NOT suitable for production. You'll need a production-grade WSGI server like [Gunicorn](https://gunicorn.org/) or [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/).
  - Example Gunicorn command: `gunicorn ledgerpro_project.wsgi:application --bind 0.0.0.0:8000 --workers 3` (adjust workers based on your server resources).
- **Reverse Proxy (Optional but Recommended):** Often, a web server like [Nginx](https://nginx.org/en/) or Apache is used as a reverse proxy in front of your WSGI server. Nginx can handle things like:
  - Serving static files directly (see below).
  - SSL/TLS termination (HTTPS).
  - Load balancing (if you have multiple application instances).
  - Caching certain requests.

### 2. Static Files & Media Files

- **Collect Static Files:** Run `python manage.py collectstatic` in your production environment (or during your build process). This command gathers all static files (CSS, JavaScript, images from your apps and Django admin) into a single directory specified by `STATIC_ROOT` in your `settings.py`.
- **Serving Static Files:**
  - **Dedicated Service:** For best performance, serve static files using a dedicated service like Amazon S3, Google Cloud Storage, or a CDN (Content Delivery Network). Libraries like `django-storages` can help with this.
  - **Reverse Proxy:** Alternatively, your reverse proxy (Nginx/Apache) can be configured to serve static files directly from the `STATIC_ROOT` directory, bypassing the Django application for these requests.
- **Media Files (User Uploads):** If your application handles user-uploaded files (e.g., receipt OCR, invoice logos - as per PRD), these are typically stored in the directory specified by `MEDIA_ROOT`. In production, these should also be stored in a cloud storage service (like S3) rather than the application server's local filesystem, especially if you have multiple application instances or ephemeral containers.

### 3. Database & Cache

- **Production Database:** Use a managed PostgreSQL service from your cloud provider (e.g., AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL). These services handle backups, scaling, and maintenance.
  - Ensure your `DATABASE_URL` environment variable points to this production database.
- **Production Cache/Broker:** Similarly, use a managed Redis service (e.g., AWS ElastiCache, Google Memorystore, Azure Cache for Redis) for Celery task queuing and application caching.
  - Ensure your `REDIS_URL` environment variable points to this production Redis instance.

### 4. Environment Variables & Configuration

- **Secure Management:** NEVER hardcode secrets (like `DJANGO_SECRET_KEY`, database passwords, API keys) in your codebase.
- **Cloud Provider Tools:** Use your cloud provider's mechanisms for managing environment variables securely (e.g., AWS Secrets Manager, AWS Systems Manager Parameter Store, Google Secret Manager, Azure Key Vault, or environment variable settings within your app service).
- **Key Variables for Production:**
  - `DJANGO_SECRET_KEY`: Must be a strong, unique secret.
  - `DEBUG=False`: CRITICAL for security and performance.
  - `ALLOWED_HOSTS`: Set this to your production domain(s).
  - `DATABASE_URL`: Connection string for your production database.
  - `REDIS_URL`: Connection string for your production Redis.
  - Plaid, SendGrid, and other third-party API keys should use production keys, not sandbox/development keys.
  - CORS settings (`CORS_ALLOWED_ORIGINS` in Django settings if your frontend is on a different domain).

### 5. Containerization (Docker)

- **Consistency:** Using Docker for deployment (as done for local development) provides consistency between your development and production environments.
- **Orchestration:** Cloud platforms offer services for running Docker containers (e.g., Amazon ECS, Amazon EKS, Google Kubernetes Engine (GKE), Azure Kubernetes Service (AKS), Heroku Docker Deploy).
- **Dockerfile for Production:** Your `Dockerfile.backend` might need adjustments for production (e.g., ensuring Gunicorn is the CMD, not `manage.py runserver`, multi-stage builds for smaller images).

### 6. Logging & Monitoring

- Configure Django logging to output in a format suitable for your cloud provider's logging service (e.g., JSON).
- Integrate with monitoring and error tracking tools (e.g., Sentry, Grafana/Prometheus as mentioned in PRD).

### 7. Running Migrations & Initial Setup

- Database migrations (`python manage.py migrate`) typically need to be run as part of your deployment process before the new application version goes live.
- You might also need to run other management commands (e.g., `createsuperuser` if not done, or custom setup commands).

This conceptual guide provides a starting point. Always refer to your cloud provider's documentation and best practices for deploying Django applications.

## Security Checklist (High-Level)

Security is paramount for an accounting platform. This checklist provides a high-level overview of key security considerations. Always consult Django's security documentation and OWASP guidelines for comprehensive practices.

- **HTTPS:** Ensure your production deployment uses HTTPS exclusively to encrypt data in transit. Configure your reverse proxy (Nginx/Apache) or load balancer for SSL/TLS termination.
- **Secrets Management:**
  - Never hardcode secrets (`DJANGO_SECRET_KEY`, API keys, database passwords) in your code.
  - Use environment variables, managed secrets services (e.g., AWS Secrets Manager, HashiCorp Vault, Google Secret Manager, Azure Key Vault), or configuration files that are not committed to version control.
- **Django Built-in Protections:** Leverage Django's built-in security features:
  - Cross-Site Scripting (XSS) protection (template auto-escaping).
  - Cross-Site Request Forgery (CSRF) protection (ensure `{% csrf_token %}` is used in forms if not using DRF exclusively for state changes).
  - SQL injection protection (Django's ORM helps prevent this).
  - Clickjacking protection (X-Frame-Options middleware).
- **DEBUG Mode:** CRITICAL: Ensure `DEBUG = False` in your production settings. Running with `DEBUG = True` can expose sensitive configuration information.
- **ALLOWED_HOSTS:** Configure `ALLOWED_HOSTS` in your production settings to a specific list of your domain(s) to prevent HTTP Host header attacks.
- **Input Validation:** Always validate and sanitize user-supplied data on both client-side and server-side (Django Forms, DRF Serializers are good for this).
- **Authentication & Authorization (Permissions):**
  - Use strong password hashing (Django's default is good).
  - Implement robust authentication mechanisms (e.g., JWT for APIs, session auth).
  - Enforce strict, role-based permissions (RBAC) for all views and API endpoints. Use Django's permission framework or DRF permissions.
  - Ensure users can only access data within their own organization (as implemented with `OrganizationScopedViewMixin`).
- **Dependency Management:**
  - Keep all dependencies (Python packages, Node modules) up-to-date to patch known vulnerabilities.
  - Regularly scan dependencies for vulnerabilities using tools like `pip-audit` (Python) or `npm audit` (Node.js).
- **Error Handling & Logging:**
  - Avoid exposing detailed error messages or stack traces to users in production.
  - Implement comprehensive logging to track suspicious activities and errors, but be careful not to log sensitive data.
- **Regular Security Audits & Penetration Testing:** Consider these for mature applications.
- **Rate Limiting:** Protect login and other sensitive endpoints from brute-force attacks by implementing rate limiting (e.g., using `django-ratelimit` or Nginx).
- **Data Encryption at Rest:** Sensitive data in the database (e.g., certain employee details, Plaid access tokens if not using a vault) should be encrypted. (PRD mentions AES-256 for PostgreSQL and S3).
- **Least Privilege:** Ensure all components and users operate with the minimum level of privilege necessary.

## Performance Optimizations (Brief Notes)

While detailed performance tuning is application-specific and an ongoing process, here are some general areas to consider:

- **Database Optimization:**
  - **Indexing:** Ensure appropriate database indexes are created for frequently queried fields, especially foreign keys and fields used in filters or ordering. Use Django's `Meta.indexes` or add them directly to your database.
  - **Query Optimization:** Use Django Debug Toolbar or tools like `django-silk` during development to identify and optimize slow or numerous database queries. Use `select_related` and `prefetch_related` to avoid N+1 problems.
  - **Connection Pooling:** Use a database connection pooler (like PgBouncer for PostgreSQL) in production environments to manage database connections efficiently.

- **Caching:**
  - Implement caching strategies for frequently accessed, computationally expensive, or rarely changing data. Django's caching framework can be used with Redis or Memcached.
  - Consider caching API responses, parts of templates, or function results.

- **Asynchronous Tasks (Celery):**
  - Offload long-running or resource-intensive tasks (e.g., sending emails, generating complex reports, third-party API calls that can tolerate delay) to background workers using Celery with Redis or RabbitMQ as a broker. This improves API response times and user experience.

- **Frontend Performance:**
  - **Code Splitting & Lazy Loading:** Next.js handles this well automatically for pages. Apply similar principles for large components.
  - **Optimized Images:** Use optimized image formats (like WebP) and sizes. Next.js Image component helps.
  - **Minimize Bundle Size:** Regularly audit frontend bundle sizes.
  - **Client-Side State Management:** Optimize state updates and re-renders if using complex state management.

- **Static Asset Serving:** Serve static files and media efficiently, preferably via a CDN as mentioned in the Cloud Installation section.

- **Load Testing:** For production systems, perform load testing to identify bottlenecks under stress.

## Troubleshooting Docker Issues

Common issues when setting up or running with Docker/Docker Compose:

### 1. "Not supported URL scheme http+docker" or "URLSchemeUnknown"

This error typically occurs when using `docker-compose` (V1, the Python script) and it cannot correctly determine how to connect to the Docker daemon.
Suggestions:
- **Use Docker Compose V2:** If available, prefer using `docker compose` (with a space). It's generally more robust. The `./setup_dev_env.sh` script attempts to do this.
- **Check `DOCKER_HOST` Environment Variable:**
  - In most local setups, this variable should be **unset**. If it's set (e.g., `echo $DOCKER_HOST`), try unsetting it: `unset DOCKER_HOST` and try again.
  - If you need it set for other reasons, ensure it's a valid URI that your Docker client version supports (e.g., `unix:///var/run/docker.sock` on Linux).
- **Check Docker Context:**
  - List your Docker contexts: `docker context ls`
  - Show your current context: `docker context show`
  - Ensure the current context is correctly configured for your local Docker daemon (often the 'default' context).
- **Docker Daemon Status:** Ensure your Docker daemon is running and responsive. Try `docker ps` or `docker info`.
- **`docker-compose` V1 Environment:** If you must use `docker-compose` V1, this error can sometimes be due to issues in its Python environment or outdated dependencies (`docker` Python library, `requests`, `urllib3`). Consider reinstalling or updating `docker-compose` or its dependencies in a dedicated Python environment.

### 2. Port Conflicts

If you see errors like "port is already allocated" or "address already in use":
- Another service on your machine is using a port that Docker Compose is trying to use (e.g., 8000 for backend, 3000 for frontend, 5432 for PostgreSQL).
- Stop the conflicting service or change the port mapping in the `ports` section of your `docker-compose.yml` file (e.g., change `"8000:8000"` to `"8001:8000"` to map container port 8000 to host port 8001).

### 3. Database Connection Issues from Backend Container

- Ensure the `DATABASE_URL` in `ledgerpro/backend/.env` uses the correct service name for the database host (e.g., `db` as defined in `docker-compose.yml`, not `localhost`). Example: `postgres://ledgerpro:secret@db:5432/ledgerpro`.
- Check logs of the database container (`docker compose logs db` or `docker-compose logs db`) for any errors during its startup.
- Ensure the database service is fully up and running before the backend tries to connect (the setup script has a basic wait, but complex setups might need more).

### 4. General Docker Issues

- **Permissions:** On Linux, you might need to run Docker commands with `sudo` or add your user to the `docker` group (`sudo usermod -aG docker $USER` then log out/in).
- **Disk Space:** Ensure you have enough free disk space for Docker images and volumes.
- **Firewall:** Check if a firewall is blocking communication to/from Docker containers or the Docker daemon.

[end of README.md]
