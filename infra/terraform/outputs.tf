output "api_url" {
  description = "Public API endpoint"
  value       = module.ecs.alb_dns_name
}

output "dynamodb_table_name" {
  description = "User profiles DynamoDB table"
  value       = module.dynamodb.table_name
}

output "sqs_queue_url" {
  description = "Agent events SQS queue URL"
  value       = module.sqs.queue_url
}
