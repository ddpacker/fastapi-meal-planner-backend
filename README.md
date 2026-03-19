## FastAPI Meal Planner Backend

This is a FastAPI + PostgreSQL backend for a weekly meal planning assistant that integrates with Anthropic models
to generate recipes, support per-meal chat refinement, build grocery lists, and estimate basic nutrition.

### Features

- **User auth** with JWT (email + password).
- **Weekly meal plans** with 7 planned meals.
- **Recipe generation** via Anthropic.
- **Per-meal chat sessions** to iteratively refine recipes.
- **Grocery list generation** from all ingredients in a week.
- **Basic nutrition estimates** per recipe.

### Infrastructure

- **Cloud Provider:** Azure
- **Compute:** Azure Container Apps - Scalable serverless container hosting for cost optimization
- **Database:** Azure Database for PostgreSQL - Relational storage with robust vector support. Private Link enables secure network isolation
- **Security:**
    - Azure Key Vault - Centralized secret management for Anthropic keys and database credentials
    - Managed Identity - Passwordless authentication between application and Azure resources
- **Networking:** Azure Virtual Network - Private Endpoints ensure the application, database, and Key Vault are entirely isolated from the public internet
- **Observability:** Azure Monitor and Application Insights - Tracing and performance metrics

### DevOps and Tooling

- **CI/CD:** GitHub Actions with OpenID Connect - Secretless deployment to Azure Container Registry
- **Package Management:** uv - Deterministic, high-speed dependency management
- **Containerization:** Docker - Multi-stage builds utilizing layer caching to minimize image size and reduce the production attack surface
- **Database Migrations:** Alembic - Schema versioning managed via container script. Synchronizes state between PostgreSQL schema and Pydantic models

### Project layout

- `app/main.py` – FastAPI application, router registration, startup.
- `app/config.py` – settings (DB URL, Anthropic API key, JWT secrets, etc.).
- `app/db/` – SQLAlchemy engine, session, and base model.
- `app/models/` – SQLAlchemy models.
- `app/schemas/` – Pydantic models for requests/responses.
- `app/routers/` – FastAPI routers for auth, meal plans, recipes, chat, grocery, and nutrition.
- `app/services/` – business logic and orchestration.
- `app/clients/` – Anthropic client wrapper.
- `app/utils/` – helpers such as prompt templates.
- `alembic/` – Alembic migration environment.

### Getting started

1. **Install dependencies and setup environment**

```bash
uv sync
```

2. **Configure environment**

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/meal_planner
SECRET_KEY=change-me
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20240620
```

3. **Run migrations**

```bash
uv run alembic upgrade head
```

4. **Run the development server**

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Open `http://localhost:8000/docs` for the interactive
Swagger UI.

## Infrastructure Setup

### Azure Configuration

1. **Create Resource Group**
```bash
   az group create --name rg-fastapi-meal-planner-dev --location eastus
```

2. **Create Service Principal**
```bash
    CLIENT_ID=$(az ad app create --display-name "fastapi-meal-planner-gha" --query appId -o tsv)

    az ad sp create --id $CLIENT_ID
```

3. **Set Up Federated Identity (for OIDC)**
```bash
    az ad app federated-credential create \
      --id $CLIENT_ID \
      --parameters '{
        "name": "gha-main-branch-trust",
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "repo:<your-github-org>/<your-repo>:ref:refs/heads/master",
        "description": "Trusts GitHub Actions running on the main branch",
        "audiences": ["api://AzureADTokenExchange"]
      }'
```

4. **Assign Permissions**
```bash
    SP_OBJECT_ID=$(az ad sp show --id $CLIENT_ID --query id -o tsv)
       az role assignment create \
         --assignee  $SP_OBJECT_ID \
         --role Contributor \
         --scope /subscriptions//resourceGroups/rg-fastapi-meal-planner-dev
```

5. **Add GitHub Secrets**
```bash
    az ad app show --id $CLIENT_ID --query appId -o tsv    # AZURE_CLIENT_ID
    az account show --query tenantId -o tsv                # AZURE_TENANT_ID
    az account show --query id -o tsv                      # AZURE_SUBSCRIPTION_ID
```

   - `AZURE_CLIENT_ID` → Your app registration's Application (client) ID
   - `AZURE_TENANT_ID` → Your Azure tenant ID
   - `AZURE_SUBSCRIPTION_ID` → Your Azure subscription ID

### Github Actions Workflows
- **test-azure-connection** - Check to ensure GHA is able to connect to your Azure resource group

## Roadmap

**Infrastructure**
- [X] Local containerization
- [X] Configure GitHub Actions OIDC and application Managed Identity for secretless Azure access
- [ ] Provision Azure Container Registry with token-based access
- [ ] Configure Azure VNet and Private Endpoints for database and Key Vault
- [ ] Deploy Azure Database for PostgreSQL within the VNet
- [ ] Deploy Azure Container Apps within the VNet and configure horizontal autoscaling
- [ ] Configure RBAC for Azure Key Vault and migrate secrets
- [ ] Finalize GitHub Actions workflow to build, push to ACR, and trigger ACA revisions
- [ ] Enable Application Insights and Log Analytics for distributed tracing and log aggregation

**Backend API**
- [X] Project skeleton & health endpoint
- [X] Database models & Alembic migrations
- [X] Pydantic schemas & router stubs
- [ ] Anthropic integration & prompt templates
- [ ] Grocery & nutrition services
- [ ] Tests & OpenAPI documentation

**Future milestones**
- [ ] Angular web client
- [ ] Recipe rating system (thumbs up/down per generated recipe)
- [ ] RAG layer via pgvector (approved recipes embedded and retrieved as few-shot context)
- [ ] Swap Anthropic for local Llama model (provider-agnostic AI layer)
- [ ] Mobile client
- [ ] Distroless?
- [ ] Integrate Alembic migrations into deployment workflow
