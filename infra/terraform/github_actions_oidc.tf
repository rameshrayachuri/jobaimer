# GitHub Actions OIDC — no static AWS credentials ever stored in GitHub
# Creates 3 roles: dev, test, prod — scoped to minimum required permissions

data "aws_caller_identity" "current" {}

locals {
  github_org  = "your-github-org"    # TODO: replace with your GitHub org/user
  github_repo = "jobaimer"           # TODO: replace with your repo name
  account_id  = data.aws_caller_identity.current.account_id
}

# ── OIDC Provider (one per AWS account) ──────────────────────────────────────

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub Actions OIDC thumbprint (stable)
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = { Name = "github-actions-oidc" }
}

# ── Trust policy helper ───────────────────────────────────────────────────────

data "aws_iam_policy_document" "github_actions_trust" {
  for_each = toset(["dev", "test", "prod"])

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      # dev/test: allow feature branches + their own branch
      # prod: only main branch
      values = each.key == "prod" ? [
        "repo:${local.github_org}/${local.github_repo}:ref:refs/heads/main"
      ] : [
        "repo:${local.github_org}/${local.github_repo}:ref:refs/heads/${each.key}",
        "repo:${local.github_org}/${local.github_repo}:pull_request"
      ]
    }
  }
}

# ── IAM Roles ─────────────────────────────────────────────────────────────────

resource "aws_iam_role" "github_actions" {
  for_each = toset(["dev", "test", "prod"])

  name               = "jobaimer-github-actions-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust[each.key].json
  max_session_duration = 3600  # 1 hour max

  tags = { Environment = each.key }
}

# ── Permissions per environment ───────────────────────────────────────────────

data "aws_iam_policy_document" "github_actions_policy" {
  for_each = toset(["dev", "test", "prod"])

  # ECR — push/pull images
  statement {
    sid    = "ECRPush"
    effect = "Allow"
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeRepositories",
      "ecr:ListImages",
      "ecr:DescribeImages",
    ]
    resources = [
      "arn:aws:ecr:${var.aws_region}:${local.account_id}:repository/jobaimer-api",
      "arn:aws:ecr:${var.aws_region}:${local.account_id}:repository/jobaimer-agent",
    ]
  }

  statement {
    sid       = "ECRAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Lambda — update + publish versions
  statement {
    sid    = "LambdaDeploy"
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:GetFunction",
      "lambda:PublishVersion",
      "lambda:GetAlias",
      "lambda:CreateAlias",
      "lambda:UpdateAlias",
      "lambda:ListVersionsByFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:WaitForFunctionUpdated",
    ]
    resources = [
      "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:jobaimer-api-${each.key}",
      "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:jobaimer-api-${each.key}:*",
    ]
  }

  # ECS — update service + task definitions
  statement {
    sid    = "ECSDeploy"
    effect = "Allow"
    actions = [
      "ecs:UpdateService",
      "ecs:DescribeServices",
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
      "ecs:ListTaskDefinitions",
    ]
    resources = [
      "arn:aws:ecs:${var.aws_region}:${local.account_id}:service/jobaimer-${each.key}/jobaimer-agent-${each.key}",
      "arn:aws:ecs:${var.aws_region}:${local.account_id}:task-definition/jobaimer-agent-${each.key}:*",
    ]
  }

  statement {
    sid       = "ECSClusterRead"
    effect    = "Allow"
    actions   = ["ecs:DescribeClusters"]
    resources = ["arn:aws:ecs:${var.aws_region}:${local.account_id}:cluster/jobaimer-${each.key}"]
  }

  # IAM PassRole — needed for ECS task definition updates
  statement {
    sid     = "PassECSRole"
    effect  = "Allow"
    actions = ["iam:PassRole"]
    resources = [
      "arn:aws:iam::${local.account_id}:role/jobaimer-${each.key}-ecs-task",
    ]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  # SSM — read secrets (DB URL for migrations)
  statement {
    sid    = "SSMRead"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/jobaimer/${each.key}/*",
    ]
  }

  # KMS — for SSM SecureString decrypt
  statement {
    sid       = "KMSDecrypt"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = ["arn:aws:kms:${var.aws_region}:${local.account_id}:key/*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }

  # CloudWatch — read metrics for canary health check (prod only)
  dynamic "statement" {
    for_each = each.key == "prod" ? [1] : []
    content {
      sid       = "CloudWatchMetrics"
      effect    = "Allow"
      actions   = ["cloudwatch:GetMetricStatistics", "cloudwatch:ListMetrics"]
      resources = ["*"]
    }
  }

  # Lambda versions — list (needed for rollback)
  statement {
    sid       = "LambdaVersions"
    effect    = "Allow"
    actions   = ["lambda:ListVersionsByFunction"]
    resources = ["arn:aws:lambda:${var.aws_region}:${local.account_id}:function:jobaimer-api-${each.key}"]
  }
}

resource "aws_iam_role_policy" "github_actions" {
  for_each = toset(["dev", "test", "prod"])

  name   = "jobaimer-github-actions-${each.key}-policy"
  role   = aws_iam_role.github_actions[each.key].id
  policy = data.aws_iam_policy_document.github_actions_policy[each.key].json
}

# ── Outputs for GitHub Actions secrets ────────────────────────────────────────

output "github_actions_role_arns" {
  value = {
    dev  = aws_iam_role.github_actions["dev"].arn
    test = aws_iam_role.github_actions["test"].arn
    prod = aws_iam_role.github_actions["prod"].arn
  }
  description = "Set these as GitHub Actions secrets: AWS_ACCOUNT_ID = ${local.account_id}"
}
