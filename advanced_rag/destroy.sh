cd /Users/dc/Documents/ChatGPT/aggents/geha-advanced-rag-deploy/advanced_rag

# Keep a local state backup
cp infra/terraform/terraform.tfstate \
  /private/tmp/geha-advanced-rag-terraform.tfstate.backup

# Preview and save the complete 31-resource destruction plan
terraform -chdir=infra/terraform plan \
  -destroy \
  -input=false \
  -out=/private/tmp/geha-advanced-rag-destroy.tfplan

# Execute exactly that saved plan
terraform -chdir=infra/terraform apply \
  -input=false \
  -auto-approve \
  /private/tmp/geha-advanced-rag-destroy.tfplan

