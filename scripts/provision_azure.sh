#!/usr/bin/env bash
# Rebuild the whole Azure environment from nothing.
#
#   bash scripts/provision_azure.sh          # create everything
#   bash scripts/provision_azure.sh destroy  # delete everything
#
# Run it in Azure Cloud Shell. Idempotent: safe to re-run.
#
# Why this exists: the App Service plan, web app, Key Vault, managed identity
# and role assignments are all disposable. If the subscription is suspended,
# the credit lapses, or someone deletes the resource group, this rebuilds the
# lot in about ten minutes. The things that are NOT disposable - the code and
# the Gemini API key - live on GitHub and in AI Studio respectively.

set -euo pipefail

RG=${RG:-vibe-challenge}
LOC=${LOC:-eastus}
PLAN=${PLAN:-vibe-plan}
APP=${APP:-}                    # must be globally unique
KV=${KV:-}                      # must be globally unique
SKU=${SKU:-B1}
MODEL=${VCC_MODEL:-gemini-3.6-flash}

if [ "${1:-}" = "destroy" ]; then
  echo "Deleting resource group $RG and everything in it."
  read -r -p "Type the resource group name to confirm: " confirm
  [ "$confirm" = "$RG" ] || { echo "Aborted."; exit 1; }
  az group delete --name "$RG" --yes
  echo "Gone. Re-run without 'destroy' to rebuild."
  exit 0
fi

[ -n "$APP" ] || APP="vibe-board-$RANDOM"
[ -n "$KV"  ] || KV="vibe-kv-$RANDOM"

echo "=============================================================="
echo " resource group : $RG   ($LOC)"
echo " app            : $APP  ->  https://$APP.azurewebsites.net"
echo " key vault      : $KV"
echo " model          : $MODEL"
echo "=============================================================="

# --- 0. resource providers ------------------------------------------------
# Azure requires each provider to be registered per subscription before first
# use. Microsoft.Web self-registers; Microsoft.KeyVault does not.
for ns in Microsoft.Web Microsoft.KeyVault; do
  state=$(az provider show --namespace "$ns" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)
  if [ "$state" != "Registered" ]; then
    echo "registering $ns (this takes ~60s)..."
    az provider register --namespace "$ns" --wait
  fi
done

# --- 1. resource group ----------------------------------------------------
az group create --name "$RG" --location "$LOC" -o none

# --- 2. app service plan + web app ---------------------------------------
# NB: VM quota is zero on Azure for Students, which is why this is PaaS and
# not an IaaS VM. App Service is a different resource provider with its own
# quota rules, and it is available where Microsoft.Compute is not.
az appservice plan create --name "$PLAN" --resource-group "$RG" \
  --location "$LOC" --sku "$SKU" --is-linux -o none

az webapp create --resource-group "$RG" --plan "$PLAN" --name "$APP" \
  --runtime "PYTHON:3.11" -o none

# --assign-identity equivalent: the app gets an Entra ID identity so it can
# read Key Vault with no stored credential.
az webapp identity assign --resource-group "$RG" --name "$APP" -o none
PRINCIPAL=$(az webapp identity show --resource-group "$RG" --name "$APP" --query principalId -o tsv)

# --- 3. key vault ---------------------------------------------------------
az keyvault create --name "$KV" --resource-group "$RG" --location "$LOC" \
  --enable-rbac-authorization true -o none
SCOPE=$(az keyvault show --name "$KV" --query id -o tsv)

# Control plane (creating the vault) and data plane (reading its secrets) are
# separate in Azure. Being subscription Owner grants the first, not the second.
ME=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --assignee "$ME" --role "Key Vault Secrets Officer" \
  --scope "$SCOPE" -o none 2>/dev/null || echo "  (you already have Secrets Officer)"

# The app only ever reads, so it only gets read.
az role assignment create --assignee "$PRINCIPAL" --role "Key Vault Secrets User" \
  --scope "$SCOPE" -o none 2>/dev/null || echo "  (app already has Secrets User)"

echo
echo "Waiting 60s for RBAC propagation before writing the secret..."
sleep 60

if [ -n "${GEMINI_API_KEY:-}" ]; then
  az keyvault secret set --vault-name "$KV" --name gemini-api-key \
    --value "$GEMINI_API_KEY" -o none
  echo "  secret stored from \$GEMINI_API_KEY"
else
  echo "  GEMINI_API_KEY not set - store it yourself with:"
  echo "    az keyvault secret set --vault-name $KV --name gemini-api-key --value 'YOUR_KEY'"
fi

# --- 4. app configuration -------------------------------------------------
az webapp config appsettings set --resource-group "$RG" --name "$APP" --settings \
  VCC_MODEL="$MODEL" \
  VCC_KEYVAULT_URL="https://$KV.vault.azure.net" \
  VCC_KEYVAULT_SECRET=gemini-api-key \
  VCC_BUDGET_TOKENS=35000 \
  VCC_MAX_CONCURRENT=8 \
  VCC_TARGET_RPM=800 \
  WEBSITES_PORT=8000 \
  SCM_DO_BUILD_DURING_DEPLOYMENT=false \
  -o none

az webapp config set --resource-group "$RG" --name "$APP" \
  --startup-file "python -m webboard --port 8000 --data /home/server_data" -o none

# --- 5. done --------------------------------------------------------------
cat <<EOF

==============================================================
  https://$APP.azurewebsites.net

  Save these - later commands need them:
    APP=$APP
    KV=$KV
    RG=$RG
    LOC=$LOC

  Deploy the code:
    az webapp deploy --resource-group $RG --name $APP --src-path app.zip --type zip

  Verify from inside the running app:
    az webapp ssh --resource-group $RG --name $APP
    cd /home/site/wwwroot && python3 scripts/preflight.py

  Tear it all down:
    bash scripts/provision_azure.sh destroy
==============================================================
EOF
