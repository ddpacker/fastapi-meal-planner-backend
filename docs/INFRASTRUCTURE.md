# Infrastructure Setup

## Azure Configuration

### Prerequisites

Before starting, ensure you have the Azure CLI installed and are logged in:

```bash
az login
```

## Setup

1. **Create Resource Group**

```bash
RG_NAME=rg-fastapi-meal-planner-dev

az group create --name $RG_NAME --location eastus
```

---
2. **Create Service Principal**

```bash
CLIENT_ID=$(az ad app create --display-name "fastapi-meal-planner-gha" --query appId -o tsv)
echo "CLIENT_ID: $CLIENT_ID" # Ensure the app registration was created successfully

az ad sp create --id $CLIENT_ID
```

---
3. **Set Up Federated Identity (for OIDC)**

```bash
CLIENT_ID=$(az ad app list --display-name "fastapi-meal-planner-gha" --query '[0].appId' -o tsv)

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

---
4. **Assign Permissions**

```bash
CLIENT_ID=$(az ad app list --display-name "fastapi-meal-planner-gha" --query '[0].appId' -o tsv)
SP_OBJECT_ID=$(az ad sp show --id $CLIENT_ID --query id -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az role assignment create \
    --assignee  $SP_OBJECT_ID \
    --role Contributor \
    --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-fastapi-meal-planner-dev
```

---
5. **Add GitHub Secrets**

Retrieve the values:

```bash
AZURE_CLIENT_ID=$(az ad app list --display-name "fastapi-meal-planner-gha" --query '[0].appId' -o tsv)
AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)
AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "AZURE_CLIENT_ID: $AZURE_CLIENT_ID"
echo "AZURE_TENANT_ID: $AZURE_TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID: $AZURE_SUBSCRIPTION_ID"
```
Then in your GitHub repo: 

**Settings → Secrets and variables → Actions → New repository secret**

Create three entries:
- Name: `AZURE_CLIENT_ID`, Value: [paste from above]
- Name: `AZURE_TENANT_ID`, Value: [paste from above]
- Name: `AZURE_SUBSCRIPTION_ID`, Value: [paste from above]

---
6. **Validate Github Secrets and OIDC Connection**

Test the connection by running the **test-azure-connection** workflow.

1. Go to your GitHub repo → Actions
2. Select "Test Azure Connection" workflow
3. Click "Run workflow" (manual trigger)
    - Use workflow from: `Branch: <DEFAULT_BRANCH>`
4. If it succeeds, your secrets and OIDC are configured correctly
5. If it fails, check the error logs—common issues:
    - Secret values copied incorrectly
    - Service principal doesn't have Contributor role
    - Federated credential misconfigured (check `subject` matches your repo)

---
7. **Create VNets and Subnets Within Azure RG**
```bash
VNET_NAME=vnet-meal-planner-dev
VNET_ADDRESS_PREFIX=10.0.0.0/16
RG_NAME=rg-fastapi-meal-planner-dev

az network vnet create \
--name $VNET_NAME \
--resource-group $RG_NAME \
--address-prefixes $VNET_ADDRESS_PREFIX

az network vnet subnet create \
--name snet-meal-planner-api-dev \
--resource-group $RG_NAME \
--vnet-name $VNET_NAME \
--address-prefixes 10.0.1.0/24

az network vnet subnet create \
--name snet-meal-planner-db-dev \
--resource-group $RG_NAME \
--vnet-name $VNET_NAME \
--address-prefixes 10.0.2.0/24

# This subnet is for future async services: vector embedding, bulk recipe operations, etc.
# Currently unused but provisioned for future development.
az network vnet subnet create \
--name snet-meal-planner-workers-dev \
--resource-group $RG_NAME \
--vnet-name $VNET_NAME \
--address-prefixes 10.0.3.0/24
```

## Github Actions Workflows

### Authentication

All workflows use OIDC-based authentication (configured in steps 1-6 above).

### Available Workflows

- **test-azure-connection** (`.github/workflows/test-azure-connection.yml`) - Validates OIDC configuration and Azure resource group access. Manually trigger to verify setup is complete.

### Planned Workflows

- Build and push to Azure Container Registry
- Deploy to Azure Container Apps
- Run database migrations