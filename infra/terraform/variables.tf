variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "voyager-travel-agent"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "container_image" {
  description = "ECR image URI for the API container"
  type        = string
}

variable "anthropic_api_key_arn" {
  description = "SSM Parameter ARN for Anthropic API key"
  type        = string
}

variable "langsmith_api_key_arn" {
  description = "SSM Parameter ARN for LangSmith API key"
  type        = string
}
