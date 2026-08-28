# Deploying on Azure (single VM)

Same shape as the AWS runbook: one small Linux VM, SQLite on local disk, the
gateway's rate limiter in-process, systemd keeping it alive. Only the
provider-specific pieces differ.

| AWS | Azure |
| --- | --- |
| EC2 instance | Virtual Machine |
| Security Group | Network Security Group (NSG) |
| IAM instance role | Managed Identity |
| Secrets Manager | Key Vault |
| Elastic IP | Static Public IP |
| `VCC_SECRET_ID` | `VCC_KEYVAULT_URL` + `VCC_KEYVAULT_SECRET` |

The gateway reads Key Vault through the VM's managed identity using the IMDS
endpoint and the Key Vault REST API directly — **no `azure-*` packages
required**, keeping the project dependency-free.

---

## 0. Check your credit first

```bash
az login
az account show --output table
az consumption budget list --output table
```

Or in the portal: **Education → Overview** (Azure for Students) shows credit
remaining and the renewal countdown. **Cost Management → Cost analysis** gives
the breakdown.

**Use `Standard_B1s`.** The Azure for Students free-services allowance includes
750 hours/month of a B1s VM - about 24/7 for a full month - so the server may
cost you nothing at all. Check the **Free Services** card on the Education
Overview page to confirm Linux B1s is covered on your offer; if it is not, a
Linux B1s is roughly $8/month, which is still trivial.

B1s is 1 vCPU / 1 GB, and that is enough here: evaluation takes 0.1 s per
submission and the gateway is network-bound, waiting on Gemini rather than
computing. If you would rather have headroom, `Standard_B2s` is ~$30/month -
fine for the few days you actually need it, dangerous if forgotten.

**Set a budget alert before you build anything** (§0a), then deallocate the
moment the workshop ends (§8). The risk here is never the workshop itself -
it is a VM you forget about for three months.

## 0a. Set a budget alert first

Two minutes now, and a forgotten VM can never quietly eat the year's credit:

```bash
az consumption budget create \
  --budget-name vibe-challenge-guard \
  --amount 20 \
  --time-grain Monthly \
  --category Cost \
  --start-date $(date +%Y-%m-01) \
  --end-date 2027-06-01
```

Or in the portal: **Cost Management → Budgets → Add**, $20/month, alert at 80%.

## 1. Create the VM

```bash
RG=vibe-challenge
LOC=westeurope           # put this near your venue
VM=vibe-board

az group create --name $RG --location $LOC

az vm create \
  --resource-group $RG --name $VM \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --assign-identity
```

`--assign-identity` creates the system-assigned managed identity the gateway
uses to read the key. Do not skip it.

Make the public IP static so the URL on your slide survives a restart:

```bash
az network public-ip update --resource-group $RG --name ${VM}PublicIP \
  --allocation-method Static
```

## 2. Open the ports

```bash
az vm open-port --resource-group $RG --name $VM --port 8000 --priority 1001
```

SSH (22) is opened by `az vm create`. Restrict it to your own IP in the NSG
afterwards. Outbound internet is allowed by default on Azure VMs, so the
Gemini API is reachable — but `scripts/preflight.py` verifies it anyway.

## 3. Key Vault

```bash
KV=vibe-challenge-kv-$RANDOM      # vault names are globally unique

az keyvault create --name $KV --resource-group $RG --location $LOC \
  --enable-rbac-authorization true

az keyvault secret set --vault-name $KV --name gemini-api-key --value 'AIza...'
```

Grant the VM's identity read access to the vault, and nothing else:

```bash
PRINCIPAL=$(az vm identity show --resource-group $RG --name $VM --query principalId -o tsv)
SCOPE=$(az keyvault show --name $KV --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL \
  --role "Key Vault Secrets User" \
  --scope $SCOPE
```

## 4. Install

```bash
ssh azureuser@<public-ip>

sudo apt update && sudo apt install -y git python3 python3-pip
sudo mkdir -p /opt/vibe-challenge && sudo chown azureuser:azureuser /opt/vibe-challenge
git clone https://github.com/naderagentx/Vibe-Coding-Challenge.git /opt/vibe-challenge
cd /opt/vibe-challenge
```

No pip packages needed. The Azure secret path is pure stdlib.

## 5. Configure

```bash
export VCC_MODEL=gemini-2.5-flash
export VCC_KEYVAULT_URL=https://<your-vault>.vault.azure.net
export VCC_KEYVAULT_SECRET=gemini-api-key
export VCC_BUDGET_TOKENS=35000
export VCC_MAX_CONCURRENT=8
export VCC_TARGET_RPM=800        # ~80% of your real AI Studio limit
```

## 6. Preflight

```bash
python3 scripts/preflight.py
```

Ten checks including a real end-to-end generation. If **api key resolves**
fails with an IMDS error, the managed identity is missing (§1). If it fails
with HTTP 403 from Key Vault, the role assignment is missing (§3).

## 7. Run as a service

Copy `scripts/vibe-challenge.service` to `/etc/systemd/system/`, replace the
AWS `Environment=` lines with the Azure ones from §5, change `User=ec2-user`
to `User=azureuser`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vibe-challenge
journalctl -u vibe-challenge -f
```

## 8. After the workshop — do not skip this

```bash
az vm deallocate --resource-group $RG --name $VM     # stops compute billing
# or, once you have the results you need:
az group delete --name $RG --yes --no-wait           # deletes everything
```

A stopped-but-allocated VM still bills. `deallocate` is the one that stops the
meter. Export the SQLite database first if you want the call logs for the
debrief:

```bash
scp azureuser@<public-ip>:/opt/vibe-challenge/server_data/board.sqlite3 .
```
