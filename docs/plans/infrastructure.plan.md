---
name: infrastructure
overview: >
  Set up Azure resources, networking, and CI/CD pipeline for the meal planner backend.
  Target architecture: Azure Container Apps (compute) + Azure Database for PostgreSQL (data)
  + Azure Key Vault (secrets) + Azure Container Registry (images), all isolated within a VNet
  using Private Endpoints. GitHub Actions deploys via OIDC — no stored credentials.
todos:
  - id: local-containerization
    content: >
      Create a production-ready Dockerfile using a slim Python base and uv for dependency
      installation. The container must run alembic migrations then start the uvicorn server
      on port 80.
    status: done

  - id: gha-oidc
    content: >
      Configure GitHub Actions OIDC trust with an Azure App Registration so deployments
      require no stored secrets. Scope the Contributor role assignment to the resource group
      only (not subscription). Add AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID
      as GitHub Actions secrets.
    status: done

  - id: configure-vnet
    content: >
      Create VNet vnet-meal-planner-dev (10.0.0.0/16) with three subnets:
      snet-meal-planner-api-dev (10.0.1.0/24) for Container Apps,
      snet-meal-planner-db-dev (10.0.2.0/24) for PostgreSQL Private Endpoint,
      snet-meal-planner-workers-dev (10.0.3.0/24) reserved for future async workers.
      Azure CLI commands are documented in docs/INFRASTRUCTURE.md.
    status: done

  - id: provision-acr
    content: >
      Create Azure Container Registry in rg-fastapi-meal-planner-dev.
      Enable admin account or configure managed identity pull access for Container Apps.
      Record registry login server (e.g. acrfampdev.azurecr.io) for use in GHA workflow.
    status: pending

  - id: deploy-postgres
    content: >
      Deploy Azure Database for PostgreSQL Flexible Server within the DB subnet.
      Enable Private Endpoint so the database is not reachable from the public internet.
      Create the meal_planner database. Store connection string in Key Vault.
    status: pending
    dependencies:
      - configure-vnet

  - id: configure-keyvault
    content: >
      Create Azure Key Vault in rg-fastapi-meal-planner-dev.
      Enable Private Endpoint to restrict access to the VNet.
      Add secrets: DATABASE_URL, SECRET_KEY, ANTHROPIC_API_KEY.
      Grant the Container Apps managed identity the Key Vault Secrets User role (RBAC).
      Update app/config.py or container startup to pull secrets from Key Vault at runtime.
    status: pending
    dependencies:
      - configure-vnet
      - deploy-postgres

  - id: deploy-aca
    content: >
      Create an Azure Container Apps environment linked to snet-meal-planner-api-dev.
      Deploy the meal-planner-backend container app from ACR.
      Configure environment variables to reference Key Vault secrets via managed identity.
      Set min replicas = 0 (scale to zero when idle) and max replicas = 3.
      Expose port 80 with ingress set to external.
    status: pending
    dependencies:
      - provision-acr
      - deploy-postgres
      - configure-keyvault

  - id: finalize-gha-workflow
    content: >
      Replace the test-azure-connectivity.yaml workflow with a full CI/CD pipeline:
      1. Run pytest on push to master.
      2. Build Docker image (multi-stage, with layer caching).
      3. Push image to ACR with the git SHA as the tag.
      4. Trigger a new Container Apps revision using az containerapp update.
      Workflow must use OIDC login (no stored ACR credentials). Scoped to master branch only.
    status: pending
    dependencies:
      - provision-acr
      - deploy-aca

  - id: monitoring
    content: >
      Create a Log Analytics workspace and Application Insights instance in the resource group.
      Link Application Insights to the Container Apps environment for distributed tracing.
      Configure structured log output in the FastAPI app (JSON format with request_id and user_id).
      Set up a basic alert for HTTP 5xx error rate > 1% over 5 minutes.
    status: pending
    dependencies:
      - deploy-aca
---

## Roadmap

### Infrastructure

| Status | Task |
|--------|------|
| ✅ Done | Local containerization (`Dockerfile`) |
| ✅ Done | GitHub Actions OIDC — secretless Azure auth |
| ✅ Done | VNet + subnets designed and documented |
| ⏳ Pending | Provision Azure Container Registry |
| ⏳ Pending | Deploy Azure Database for PostgreSQL with Private Endpoint |
| ⏳ Pending | Configure Azure Key Vault with RBAC + Private Endpoint |
| ⏳ Pending | Deploy Azure Container Apps within VNet |
| ⏳ Pending | Full CI/CD GitHub Actions workflow (build → push → deploy) |
| ⏳ Pending | Application Insights + Log Analytics + alerting |

---

## Implementation notes

### Resource naming convention

| Resource | Name |
|----------|------|
| Resource Group | `rg-fastapi-meal-planner-dev` |
| VNet | `vnet-meal-planner-dev` |
| API subnet | `snet-meal-planner-api-dev` |
| DB subnet | `snet-meal-planner-db-dev` |
| Workers subnet | `snet-meal-planner-workers-dev` |
| Container Registry | `acrfampdev` (or similar — no hyphens) |
| PostgreSQL server | `psql-meal-planner-dev` |
| Key Vault | `kv-meal-planner-dev` |
| Container Apps env | `cae-meal-planner-dev` |
| Container App | `ca-meal-planner-backend-dev` |

### Azure CLI reference

Full setup commands are documented in [docs/INFRASTRUCTURE.md](../INFRASTRUCTURE.md).ES

### GitHub Actions workflow structure

```
.github/workflows/
  test-azure-connectivity.yaml
```

Workflow permissions required:
```yaml
permissions:
  id-token: write   # OIDC token
  contents: read    # checkout
```

### Key Vault secret names → app config mapping

| Key Vault secret | app/config.py field |
|-----------------|----------------------|
| `DATABASE-URL` | `database_url` |
| `SECRET-KEY` | `secret_key` |
| `ANTHROPIC-API-KEY` | `anthropic_api_key` |