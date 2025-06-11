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

echo "User input collection complete. Next steps will configure .env and Docker."

# --- .env File Configuration ---
echo "Configuring backend .env file at ledgerpro/backend/.env..."

# Ensure backend directory exists (it should, but good practice)
mkdir -p "ledgerpro/backend" # BACKEND_DIR definition used here

ENV_FILE="ledgerpro/backend/.env" #Matches definition in prompt
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

if [ ! -f "${ENV_FILE}" ] || [ "${OVERWRITE_ENV}" = true ]; then
    echo "Creating/Overwriting ${ENV_FILE}..."
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
    mv "${TEMP_ENV_FILE}" "${ENV_FILE}"
    if [ $? -eq 0 ]; then
        echo "${ENV_FILE} created successfully."
    else
        echo "Error creating ${ENV_FILE}. Manual creation might be needed." >&2
    fi
else
    echo "Using existing ${ENV_FILE}. Ensure it's correctly configured for Docker Compose (e.g., DATABASE_URL uses 'db' as hostname)."
fi

# --- Frontend Dependency Setup ---
echo ""
echo "Checking frontend dependencies and lockfile..."

FRONTEND_DIR="ledgerpro/frontend"
PACKAGE_JSON="${FRONTEND_DIR}/package.json"
EXPECTED_LOCKFILE_NPM="${FRONTEND_DIR}/package-lock.json"
ROOT_LOCKFILE_NPM="./package-lock.json"
LOCKFILE_YARN="${FRONTEND_DIR}/yarn.lock"
LOCKFILE_PNPM="${FRONTEND_DIR}/pnpm-lock.yaml"
NEEDS_LOCKFILE_GENERATION=true

if [ -f "${EXPECTED_LOCKFILE_NPM}" ]; then
    echo "Found ${EXPECTED_LOCKFILE_NPM}. This will be used for the Docker frontend build."
    NEEDS_LOCKFILE_GENERATION=false
elif [ -f "${LOCKFILE_YARN}" ] || [ -f "${LOCKFILE_PNPM}" ]; then
    echo "Found a non-npm lockfile (${LOCKFILE_YARN} or ${LOCKFILE_PNPM}) in ${FRONTEND_DIR}."
    echo "The Dockerfile.frontend is currently configured for npm (package-lock.json and 'npm ci')."
    echo "If this project uses yarn or pnpm, Dockerfile.frontend may need adjustment."
    NEEDS_LOCKFILE_GENERATION=false # Assume it's the correct lockfile for the project type
elif [ -f "${ROOT_LOCKFILE_NPM}" ]; then
    echo "Found a \`package-lock.json\` at the project root: ${ROOT_LOCKFILE_NPM}"
    echo "This might be due to an npm workspace setup. The frontend Docker build expects this file inside ${FRONTEND_DIR}/."
    read -p "Copy ${ROOT_LOCKFILE_NPM} to ${EXPECTED_LOCKFILE_NPM} for the Docker build? (y/n) [y]: " choice_copy_root_lockfile
    if [[ "${choice_copy_root_lockfile,,}" == "y" || "${choice_copy_root_lockfile,,}" == "yes" || -z "${choice_copy_root_lockfile}" ]]; then
        if cp "${ROOT_LOCKFILE_NPM}" "${EXPECTED_LOCKFILE_NPM}"; then
            echo "Successfully copied ${ROOT_LOCKFILE_NPM} to ${EXPECTED_LOCKFILE_NPM}."
            NEEDS_LOCKFILE_GENERATION=false
        else
            echo "Error: Failed to copy ${ROOT_LOCKFILE_NPM} to ${EXPECTED_LOCKFILE_NPM}." >&2
            echo "Please perform the copy manually or resolve permissions issues."
            echo "The Docker build for the frontend will likely fail."
            NEEDS_LOCKFILE_GENERATION=true
        fi
    else
        echo "Skipping copy. The frontend Docker build will likely fail without ${EXPECTED_LOCKFILE_NPM}."
        echo "You might need to adjust Dockerfile.frontend to use the root lockfile or ensure it's copied manually."
        NEEDS_LOCKFILE_GENERATION=true
    fi
fi

if [ "$NEEDS_LOCKFILE_GENERATION" = true ]; then
    echo "No suitable \`package-lock.json\` found in ${FRONTEND_DIR} for the Docker build."
    if [ ! -f "${PACKAGE_JSON}" ]; then
        echo "Error: ${PACKAGE_JSON} not found! Cannot install frontend dependencies or generate lockfile." >&2
        echo "Please ensure the frontend project is correctly structured."
    else
        echo "The frontend Docker build requires ${EXPECTED_LOCKFILE_NPM} for 'npm ci'."
        read -p "Do you want to attempt to generate/update ${EXPECTED_LOCKFILE_NPM} now (runs 'npm install' commands in ${FRONTEND_DIR})? (y/n) [y]: " choice_npm_install
        if [[ "${choice_npm_install,,}" == "y" || "${choice_npm_install,,}" == "yes" || -z "${choice_npm_install}" ]]; then
            echo "Attempting to generate/update ${EXPECTED_LOCKFILE_NPM} in ${FRONTEND_DIR}..."
            ORIGINAL_DIR=$(pwd)
            cd "${FRONTEND_DIR}"
            echo "Running 'npm install --package-lock-only --legacy-peer-deps' first..."
            if npm install --package-lock-only --legacy-peer-deps; then
                echo "'npm install --package-lock-only' completed."
            else
                echo "Warning: 'npm install --package-lock-only' encountered issues. Will proceed with full 'npm install'."
            fi

            if [ ! -f "package-lock.json" ]; then # Check within FRONTEND_DIR
                echo "package-lock.json still not found in $(pwd). Running full 'npm install --legacy-peer-deps'..."
                if npm install --legacy-peer-deps; then
                    echo "Full 'npm install' completed."
                else
                    echo "Error: Full 'npm install' in $(pwd) failed. Please check for errors above." >&2
                fi
            fi
            cd "${ORIGINAL_DIR}"

            if [ -f "${EXPECTED_LOCKFILE_NPM}" ]; then
                echo "SUCCESS: ${EXPECTED_LOCKFILE_NPM} has been generated/updated."
                echo "IMPORTANT: Please commit ${EXPECTED_LOCKFILE_NPM} to your Git repository!"
            elif [ -f "${ROOT_LOCKFILE_NPM}" ]; then # Check root again if frontend install created it at root
                echo "Warning: \`package-lock.json\` was generated at the project root (${ROOT_LOCKFILE_NPM}) instead of ${EXPECTED_LOCKFILE_NPM}."
                echo "This is likely due to an npm workspace configuration."
                read -p "Copy ${ROOT_LOCKFILE_NPM} to ${EXPECTED_LOCKFILE_NPM} for the Docker build? (y/n) [y]: " choice_copy_root_lockfile_after_gen
                if [[ "${choice_copy_root_lockfile_after_gen,,}" == "y" || "${choice_copy_root_lockfile_after_gen,,}" == "yes" || -z "${choice_copy_root_lockfile_after_gen}" ]]; then
                    if cp "${ROOT_LOCKFILE_NPM}" "${EXPECTED_LOCKFILE_NPM}"; then
                        echo "Successfully copied ${ROOT_LOCKFILE_NPM} to ${EXPECTED_LOCKFILE_NPM}. Please commit both (or just the one in ${FRONTEND_DIR} if workspaces are configured to share)."
                    else
                        echo "Error: Failed to copy ${ROOT_LOCKFILE_NPM} to ${EXPECTED_LOCKFILE_NPM}. The Docker build will likely fail." >&2
                    fi
                else
                    echo "Skipping copy. The frontend Docker build will likely fail without ${EXPECTED_LOCKFILE_NPM}."
                fi
            else
                echo "CRITICAL ERROR: ${EXPECTED_LOCKFILE_NPM} was NOT created and not found at root either, even after 'npm install' attempts." >&2
                echo "The Docker build for the frontend WILL LIKELY FAIL." >&2
                echo "Possible causes:" >&2
                echo "  - Issues with your npm installation or version." >&2
                echo "  - An '.npmrc' file in '${FRONTEND_DIR}' or your home directory with 'package-lock=false'." >&2
                echo "  - Restrictive directory permissions preventing file creation." >&2
                echo "Please try the following MANUALLY:" >&2
                echo "  1. cd ${FRONTEND_DIR}" >&2
                echo "  2. npm install" >&2
                echo "  3. (If no lockfile) npm install --package-lock-only" >&2
                echo "  4. Inspect for errors and resolve them." >&2
                echo "  5. Ensure ${EXPECTED_LOCKFILE_NPM} is generated and then commit it to Git." >&2
                read -p "Do you want to continue with the script despite the high chance of Docker build failure? (y/n) [n]: " choice_continue_anyway
                if [[ "${choice_continue_anyway,,}" != "y" && "${choice_continue_anyway,,}" != "yes" ]]; then
                    echo "Exiting script. Please resolve frontend dependency issues manually."
                    exit 1
                fi
            fi
        else
            echo "Skipping frontend dependency generation attempt."
            echo "Warning: The frontend Docker build may fail if ${EXPECTED_LOCKFILE_NPM} is not present."
        fi
    fi
fi
echo ""
# --- Docker Compose & Initial Backend Setup ---
echo "Proceeding with Docker Compose setup..."

# Determine Docker Compose command
DC_COMMAND=""
if command -v docker && docker compose version &> /dev/null; then
    echo "Found Docker Compose V2 (docker compose)."
    DC_COMMAND="docker compose"
elif command -v docker-compose &> /dev/null; then
    echo "Found Docker Compose V1 (docker-compose)."
    DC_COMMAND="docker-compose"
else
    echo "Error: Docker Compose (neither 'docker compose' V2 nor 'docker-compose' V1) is not installed or not in PATH." >&2
    echo "Please install Docker and Docker Compose to continue." >&2
    exit 1
fi

# Basic Docker daemon connectivity test
echo "Testing basic Docker daemon connectivity..."
if ! docker info > /dev/null 2>&1; then
    echo "Error: Could not connect to Docker daemon. Is Docker running?" >&2
    exit 1
fi
echo "Docker daemon is responsive."

# Optional: Clean previous Docker environment
read -p "Do you want to stop and remove existing Docker containers and volumes (if any) for this project? (y/n) [n]: " choice_clean_docker
if [[ "${choice_clean_docker,,}" == "y" || "${choice_clean_docker,,}" == "yes" ]]; then
    echo "Stopping and removing existing Docker environment (including database data) using ${DC_COMMAND}..."
    ${DC_COMMAND} down -v
    if [ $? -ne 0 ]; then
        echo "Warning: '${DC_COMMAND} down -v' encountered an issue. This might be okay if no services were running."
    fi
else
    echo "Skipping cleanup of existing Docker environment."
fi

# Ensure Redis is in docker-compose.yml if REDIS_URL is set to use 'redis' host
# Define BACKEND_DIR for this check, consistent with how ENV_FILE was used.
BACKEND_DIR="ledgerpro/backend"
ENV_FILE_PATH="${BACKEND_DIR}/.env"
if [ -f "${ENV_FILE_PATH}" ] && grep -q "REDIS_URL='redis://redis" "${ENV_FILE_PATH}"; then
    if ! grep -q "redis:" "docker-compose.yml"; then
        echo "Warning: REDIS_URL in .env points to 'redis' host, but no 'redis' service found in docker-compose.yml."
        echo "You might need to uncomment or add a Redis service to your docker-compose.yml for Celery/Caching to work."
    fi
fi

echo "Building and starting Docker services in detached mode (${DC_COMMAND} up --build -d)..."
UP_OUTPUT_FILE=$(mktemp)
if ! ${DC_COMMAND} up --build -d > "${UP_OUTPUT_FILE}" 2>&1; then
    echo "Error: Docker Compose failed to start services. See details below:" >&2
    cat "${UP_OUTPUT_FILE}" >&2
    if grep -q -E "URLSchemeUnknown|http\+docker" "${UP_OUTPUT_FILE}"; then
        echo "-----------------------------------------------------------------------" >&2
        echo "Specific Troubleshooting for 'URLSchemeUnknown' or 'http+docker' error:" >&2
        echo "This error can occur with older docker-compose (V1) versions if the Docker environment is unusual." >&2
        echo "1. Check DOCKER_HOST: Ensure the DOCKER_HOST environment variable is unset or correctly configured." >&2
        echo "   Run: echo \$DOCKER_HOST" >&2
        echo "2. Check Docker Context: Ensure your current Docker context is standard." >&2
        echo "   Run: docker context ls" >&2
        echo "3. If using docker-compose V1 (Python script), this might be an issue with its Python environment or dependencies." >&2
        echo "   Consider using Docker Compose V2 ('docker compose') if available, which is generally more robust." >&2
        echo "-----------------------------------------------------------------------" >&2
    fi
    rm "${UP_OUTPUT_FILE}"
    exit 1
fi
rm "${UP_OUTPUT_FILE}"
echo "Docker services started."

# Wait for services to be ready (especially PostgreSQL)
echo "Waiting for backend and database services to initialize (approx. 15-30 seconds)..."
sleep 15 # Initial sleep

MAX_DB_RETRIES=5
DB_RETRY_COUNT=0
DB_READY=false
until [ "$DB_READY" = true ] || [ "$DB_RETRY_COUNT" -ge "$MAX_DB_RETRIES" ]; do
    if ${DC_COMMAND} exec -T backend pg_isready -h db -p 5432 -U ledgerpro -d ledgerpro -q; then
        echo "PostgreSQL database is ready."
        DB_READY=true
    else
        DB_RETRY_COUNT=$((DB_RETRY_COUNT + 1))
        echo "Database not yet ready (attempt ${DB_RETRY_COUNT}/${MAX_DB_RETRIES}). Waiting 5 seconds..."
        sleep 5
    fi
done

if [ "$DB_READY" = false ]; then
    echo "Error: Database service did not become ready. Check Docker logs: ${DC_COMMAND} logs db" >&2
    echo "You may need to wait longer and then manually run migrations and superuser creation."
fi

echo "Running Django database migrations inside the backend container..."
${DC_COMMAND} exec backend python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Error: Database migrations failed. Check logs above and Docker container logs: ${DC_COMMAND} logs backend" >&2
fi
echo "Database migrations completed."

# Optional: Create Django Superuser
read -p "Do you want to create a Django superuser now? (y/n) [y]: " choice_superuser
if [[ "${choice_superuser,,}" == "y" || "${choice_superuser,,}" == "yes" || -z "${choice_superuser}" ]]; then
    echo "Creating Django superuser (this will be interactive)..."
    echo "Please follow the prompts to set username, email (optional), and password."
    ${DC_COMMAND} exec backend python manage.py createsuperuser
    if [ $? -ne 0 ]; then
        echo "Warning: Superuser creation might have been skipped or encountered an issue."
    else
        echo "Superuser creation process finished."
    fi
else
    echo "Skipping superuser creation. You can create one later with:"
    echo "  ${DC_COMMAND} exec backend python manage.py createsuperuser"
fi

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
echo "  Run '${DC_COMMAND} down' in the project root directory." # Use determined DC_COMMAND
echo "  To also remove data volumes (e.g., database data): '${DC_COMMAND} down -v'"
echo ""
echo "To view logs for running services:"
echo "  '${DC_COMMAND} logs -f' (for all services, streaming)"
echo "  '${DC_COMMAND} logs backend' (for just the backend service)"
echo ""
echo "Remember to make this script executable if you haven't: chmod +x setup_dev_env.sh"
echo ""
