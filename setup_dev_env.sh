#!/bin/bash

# LedgerPro Development Environment Setup Script
# This script helps automate the initial setup of the Docker-based development environment.

# Function to prompt user for input with a message
prompt_user() {
    local prompt_message=$1
    local var_name=$2
    local default_value=${3:-""} # Optional default value
    local current_value

    if [ ! -z "${!var_name}" ]; then # Check if variable is already set (e.g. from .env load attempt)
        current_value=${!var_name}
    elif [ ! -z "${default_value}" ]; then
        current_value=${default_value}
    fi

    if [ ! -z "${current_value}" ]; then
        read -p "${prompt_message} [${current_value}]: " input
        eval $var_name=\"${input:-"$current_value"}\"
    else
        read -p "${prompt_message}: " input
        eval $var_name=\"${input}\"
    fi
    # Basic validation: ensure critical inputs are not empty
    if [[ "$var_name" == "PLAID_CLIENT_ID" || "$var_name" == "PLAID_SECRET_SANDBOX" || "$var_name" == "SENDGRID_API_KEY" ]]; then
        if [ -z "${!var_name}" ]; then
            echo "Error: ${prompt_message} cannot be empty." >&2
            # exit 1 # Option to exit if critical info is missing
        fi
    fi
}

# Function to generate a Django SECRET_KEY
generate_django_secret_key() {
    # Attempt to use Python to generate a secure key if available
    if command -v python &> /dev/null; then
        python -c 'import secrets; print(secrets.token_urlsafe(50))'
    elif command -v openssl &> /dev/null; then # Fallback to openssl
        openssl rand -base64 48 # Generates roughly 64 chars, good enough
    else # Basic fallback, less secure
        date +%s%N | sha256sum | base64 | head -c 50
    fi
}

echo "Welcome to the LedgerPro Development Environment Setup!"
echo "This script will help you configure your .env file and start the services."

# --- User Inputs ---
echo "Please provide the following details. Press Enter to accept a default value if shown in [brackets]."

# These variables will store the user's input
PLAID_CLIENT_ID=
PLAID_SECRET_SANDBOX=
PLAID_SECRET_DEVELOPMENT=
PLAID_ENV='sandbox'
SENDGRID_API_KEY=
DEFAULT_FROM_EMAIL=
DJANGO_SECRET_KEY=

prompt_user "Enter your Plaid Client ID" PLAID_CLIENT_ID
prompt_user "Enter your Plaid Sandbox Secret" PLAID_SECRET_SANDBOX
prompt_user "Enter your Plaid Development Secret (optional, can be same as Sandbox for some setups)" PLAID_SECRET_DEVELOPMENT
prompt_user "Enter Plaid Environment (e.g., sandbox, development)" PLAID_ENV "sandbox"

prompt_user "Enter your SendGrid API Key" SENDGRID_API_KEY
prompt_user "Enter your Default From Email (e.g., noreply@yourcompany.com)" DEFAULT_FROM_EMAIL

# Generate or prompt for Django Secret Key
echo "A Django SECRET_KEY is required."
read -p "Autogenerate Django SECRET_KEY? (y/n) [y]: " choice_sk
if [[ "${choice_sk,,}" == "n" || "${choice_sk,,}" == "no" ]]; then
    prompt_user "Enter your existing Django SECRET_KEY" DJANGO_SECRET_KEY
else
    DJANGO_SECRET_KEY=$(generate_django_secret_key)
    echo "Generated Django SECRET_KEY: ${DJANGO_SECRET_KEY}"
fi
if [ -z "${DJANGO_SECRET_KEY}" ]; then
    echo "Error: Django SECRET_KEY cannot be empty." >&2
    # exit 1
fi

# --- End of User Inputs (for this step) ---

# (Script will continue in next steps to create .env file and run docker-compose commands)

echo "User input collection complete. Next steps will configure .env and Docker."

# --- .env File Configuration ---
echo "Configuring backend .env file at ledgerpro/backend/.env..."

# Ensure backend directory exists (it should, but good practice)
mkdir -p "ledgerpro/backend"

ENV_FILE="ledgerpro/backend/.env"
OVERWRITE_ENV=false
if [ -f "${ENV_FILE}" ]; then
    echo "Found existing .env file at ${ENV_FILE}."
    read -p "Overwrite existing .env file? (y/n) [n]: " choice_overwrite_env
    if [[ "${choice_overwrite_env,,}" == "y" || "${choice_overwrite_env,,}" == "yes" ]]; then
        OVERWRITE_ENV=true
        echo "Existing .env file will be overwritten."
    else
        echo "Skipping .env file creation. Using existing file."
    fi
fi

# Create .env file if it doesn't exist or if user chose to overwrite
if [ ! -f "${ENV_FILE}" ] || [ "${OVERWRITE_ENV}" = true ]; then
    echo "Creating/Overwriting ${ENV_FILE}..."
    # Use a temporary file to build .env content, then move, to avoid partial writes on error
    TEMP_ENV_FILE=$(mktemp)

    echo "# Django Settings" > "${TEMP_ENV_FILE}"
    echo "DJANGO_SECRET_KEY='${DJANGO_SECRET_KEY}'" >> "${TEMP_ENV_FILE}"
    echo "DEBUG=True" >> "${TEMP_ENV_FILE}"
    echo "ALLOWED_HOSTS='localhost,127.0.0.1'" >> "${TEMP_ENV_FILE}"

    echo "" >> "${TEMP_ENV_FILE}"
    echo "# Database (PostgreSQL for Docker Compose)" >> "${TEMP_ENV_FILE}"
    echo "DATABASE_URL='postgres://ledgerpro:secret@db:5432/ledgerpro'" >> "${TEMP_ENV_FILE}"

    echo "" >> "${TEMP_ENV_FILE}"
    echo "# Redis (for Celery, Caching, if using Docker Compose)" >> "${TEMP_ENV_FILE}"
    echo "REDIS_URL='redis://redis:6379/0'" >> "${TEMP_ENV_FILE}"

    echo "" >> "${TEMP_ENV_FILE}"
    echo "# Plaid API Keys" >> "${TEMP_ENV_FILE}"
    echo "PLAID_CLIENT_ID='${PLAID_CLIENT_ID}'" >> "${TEMP_ENV_FILE}"
    echo "PLAID_SECRET_SANDBOX='${PLAID_SECRET_SANDBOX}'" >> "${TEMP_ENV_FILE}"
    echo "PLAID_SECRET_DEVELOPMENT='${PLAID_SECRET_DEVELOPMENT}'" >> "${TEMP_ENV_FILE}"
    echo "PLAID_ENV='${PLAID_ENV}'" >> "${TEMP_ENV_FILE}"

    echo "" >> "${TEMP_ENV_FILE}"
    echo "# SendGrid API Key" >> "${TEMP_ENV_FILE}"
    echo "SENDGRID_API_KEY='${SENDGRID_API_KEY}'" >> "${TEMP_ENV_FILE}"
    echo "DEFAULT_FROM_EMAIL='${DEFAULT_FROM_EMAIL}'" >> "${TEMP_ENV_FILE}"

    echo "" >> "${TEMP_ENV_FILE}"
    # Move the temp file to the actual .env file location
    mv "${TEMP_ENV_FILE}" "${ENV_FILE}"
    if [ $? -eq 0 ]; then
        echo "${ENV_FILE} created successfully."
    else
        echo "Error creating ${ENV_FILE}. Manual creation might be needed." >&2
    fi
else
    echo "Using existing ${ENV_FILE}. Ensure it's correctly configured for Docker Compose (e.g., DATABASE_URL uses 'db' as hostname)."
fi

# (Script will continue with Docker Compose commands in the next step)

# --- Docker Compose & Initial Backend Setup ---
echo "Proceeding with Docker Compose setup..."

# Check for Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker to continue." >&2
    exit 1
fi
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed. Please install Docker Compose to continue." >&2
    exit 1
fi
echo "Docker and Docker Compose found."

# Optional: Clean previous Docker environment
read -p "Do you want to stop and remove existing Docker containers and volumes (if any) for this project? (y/n) [n]: " choice_clean_docker
if [[ "${choice_clean_docker,,}" == "y" || "${choice_clean_docker,,}" == "yes" ]]; then
    echo "Stopping and removing existing Docker environment (including database data)..."
    docker-compose down -v
    if [ $? -ne 0 ]; then
        echo "Warning: 'docker-compose down -v' encountered an issue. This might be okay if no services were running."
    fi
else
    echo "Skipping cleanup of existing Docker environment."
fi

# Ensure Redis is in docker-compose.yml if REDIS_URL is set to use 'redis' host
if grep -q "REDIS_URL='redis://redis" "${ENV_FILE}"; then
    if ! grep -q "redis:" "docker-compose.yml"; then
        echo "Warning: REDIS_URL in .env points to 'redis' host, but no 'redis' service found in docker-compose.yml."
        echo "You might need to uncomment or add a Redis service to your docker-compose.yml for Celery/Caching to work."
    fi
fi

echo "Building and starting Docker services in detached mode (docker-compose up --build -d)..."
docker-compose up --build -d
if [ $? -ne 0 ]; then
    echo "Error: Docker Compose failed to start services. Check logs above." >&2
    exit 1
fi
echo "Docker services started."

# Wait for services to be ready (especially PostgreSQL)
echo "Waiting for backend and database services to initialize (approx. 15-30 seconds)..."
sleep 15 # Initial sleep

# Basic check for PostgreSQL readiness (conceptual, might need refinement)
# This tries to connect to the DB using psql inside the backend container.
MAX_DB_RETRIES=5
DB_RETRY_COUNT=0
DB_READY=false
until [ "$DB_READY" = true ] || [ "$DB_RETRY_COUNT" -ge "$MAX_DB_RETRIES" ]; do
    if docker-compose exec -T backend pg_isready -h db -p 5432 -U ledgerpro -d ledgerpro -q; then
        echo "PostgreSQL database is ready."
        DB_READY=true
    else
        DB_RETRY_COUNT=$((DB_RETRY_COUNT + 1))
        echo "Database not yet ready (attempt ${DB_RETRY_COUNT}/${MAX_DB_RETRIES}). Waiting 5 seconds..."
        sleep 5
    fi
done

if [ "$DB_READY" = false ]; then
    echo "Error: Database service did not become ready. Check Docker logs: docker-compose logs db" >&2
    echo "You may need to wait longer and then manually run migrations and superuser creation."
    # exit 1 # Decide if script should exit or continue with a warning
fi

echo "Running Django database migrations inside the backend container..."
docker-compose exec backend python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Error: Database migrations failed. Check logs above and Docker container logs: docker-compose logs backend" >&2
    # exit 1
fi
echo "Database migrations completed."

# Optional: Create Django Superuser
read -p "Do you want to create a Django superuser now? (y/n) [y]: " choice_superuser
if [[ "${choice_superuser,,}" == "y" || "${choice_superuser,,}" == "yes" || -z "${choice_superuser}" ]]; then
    echo "Creating Django superuser (this will be interactive)..."
    echo "Please follow the prompts to set username, email (optional), and password."
    docker-compose exec backend python manage.py createsuperuser
    if [ $? -ne 0 ]; then
        echo "Warning: Superuser creation might have been skipped or encountered an issue."
    else
        echo "Superuser creation process finished."
    fi
else
    echo "Skipping superuser creation. You can create one later with:"
    echo "  docker-compose exec backend python manage.py createsuperuser"
fi

# (Script will continue with final instructions and README update in the next step)

# --- Setup Complete - Next Steps ---
echo ""
echo "======================================================================="
echo "LedgerPro Development Environment Setup Complete!"
echo "======================================================================="
echo ""
echo "Services started via Docker Compose include: Backend, Database (PostgreSQL)"
echo "(And Redis if you've uncommented/added it in docker-compose.yml and .env)"
echo ""
echo "Accessing Services:"
echo "  - Backend API: http://localhost:8000/api"
echo "  - Django Admin (if superuser created): http://localhost:8000/admin"
echo ""
echo "Frontend Development:"
echo "  If you haven't started the frontend Next.js development server yet:"
echo "    cd ledgerpro/frontend"
echo "    npm install (if you haven't already)"
echo "    npm run dev"
echo "  The frontend will typically be available at http://localhost:3000"
echo ""
echo "To stop the Docker Compose services:"
echo "  Run 'docker-compose down' in the project root directory."
echo "  To also remove data volumes (e.g., database data): 'docker-compose down -v'"
echo ""
echo "To view logs for running services:"
echo "  'docker-compose logs -f' (for all services, streaming)"
echo "  'docker-compose logs backend' (for just the backend service)"
echo ""
echo "Remember to make this script executable if you haven't: chmod +x setup_dev_env.sh"
echo ""
