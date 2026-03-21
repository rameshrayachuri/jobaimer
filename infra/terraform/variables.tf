variable "environment" { type = string }
variable "aws_region" { type = string; default = "us-east-1" }
variable "ecr_registry" { type = string; default = "" }
variable "image_tag" { type = string; default = "latest" }
variable "vpc_id" { type = string; default = "" }
variable "private_subnet_ids" { type = list(string); default = [] }
variable "allowed_origins" { type = list(string); default = ["https://jobaimer.com"] }
variable "agent_desired_count" { type = number; default = 1 }

# New variables
variable "domain_name" {
  type        = string
  default     = "jobaimer.com"
  description = "Primary domain — must be registered and Route53 zone must exist"
}

variable "admin_allowed_ips" {
  type        = list(string)
  description = "CIDR blocks allowed to access admin.jobaimer.com (e.g. [\"1.2.3.4/32\"])"
  default     = []
}

variable "lambda_reserved_concurrency" {
  type        = number
  default     = -1
  description = "Reserved concurrency for Lambda (-1 = unreserved)"
}
