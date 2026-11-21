resource "aws_secretsmanager_secret" "model" {
  for_each                = var.model_secrets_enabled ? toset(["ANTHROPIC_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY"]) : toset([])
  name                    = "${var.project_name}/${each.key}"
  recovery_window_in_days = 7
  tags                    = { Name = "${var.project_name}-${each.key}" }
}
