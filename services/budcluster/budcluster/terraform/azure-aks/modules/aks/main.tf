resource "random_string" "aks_suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "${var.cluster_name}-logs-${random_string.aks_suffix.result}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = "${var.environment}-aks"
  kubernetes_version  = var.kubernetes_version
  tags                = var.tags

  default_node_pool {
    name            = "default"
    node_count      = var.enable_auto_scaling ? null : var.node_count
    vm_size         = var.vm_size
    os_disk_size_gb = var.os_disk_size_gb
    vnet_subnet_id  = var.vnet_subnet_id
    min_count       = var.enable_auto_scaling ? var.min_count : null
    max_count       = var.enable_auto_scaling ? var.max_count : null
    type            = "VirtualMachineScaleSets"
    # zones           = ["2", "3"]
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    network_policy    = "calico"
    service_cidr      = "172.16.0.0/16" # Non-overlapping service CIDR
    dns_service_ip    = "172.16.0.10"   # Must be within service_cidr
  }

  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  }

  azure_policy_enabled = true

  auto_scaler_profile {
    balance_similar_node_groups      = true
    expander                         = "random"
    max_graceful_termination_sec     = 600
    max_node_provisioning_time       = "15m"
    max_unready_nodes                = 3
    max_unready_percentage           = 45
    new_pod_scale_up_delay           = "10s"
    scale_down_delay_after_add       = "10m"
    scale_down_delay_after_delete    = "10s"
    scale_down_delay_after_failure   = "3m"
    scan_interval                    = "10s"
    scale_down_unneeded              = "10m"
    scale_down_unready               = "20m"
    scale_down_utilization_threshold = "0.5"
  }

  lifecycle {
    ignore_changes = [
      kubernetes_version,
      default_node_pool[0].node_count
    ]
  }
}

# Create a managed identity for AKS pod identity
resource "azurerm_user_assigned_identity" "aks_pod_identity" {
  name                = "${var.cluster_name}-pod-identity"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

# Role assignment for AKS to pull images from ACR
# resource "azurerm_role_assignment" "aks_acr_pull" {
#   scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${var.resource_group_name}"
#   role_definition_name = "AcrPull"
#   principal_id         = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
# }

# Get current client config
data "azurerm_client_config" "current" {}
