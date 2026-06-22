variable "auth_url" {
  description = "OpenStack Keystone authentication URL from Infomaniak Horizon / OpenRC."
  type        = string
}

variable "region" {
  description = "Infomaniak Public Cloud region, for example dc4-a."
  type        = string
  default     = "dc4-a"
}

variable "project_name" {
  description = "OpenStack project/tenant name."
  type        = string
}

variable "username" {
  description = "OpenStack API username, for example PCU-XXXX."
  type        = string
  sensitive   = true
}

variable "password" {
  description = "OpenStack API password."
  type        = string
  sensitive   = true
}

variable "external_network_id" {
  description = "External/public network ID used by the router gateway."
  type        = string
}

variable "external_network_name" {
  description = "External/public network name used for floating IP allocation. If empty, external_network_id is used."
  type        = string
  default     = ""
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key allowed on created VMs."
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "vm_count" {
  description = "Number of lab VMs to create for a course session."
  type        = number
  default     = 1

  validation {
    condition     = var.vm_count >= 1 && var.vm_count <= 25
    error_message = "vm_count must stay between 1 and 25 for one class batch."
  }
}

variable "vm_name_prefix" {
  description = "Prefix used for VM names."
  type        = string
  default     = "git-cloud-lab"
}

variable "image_name" {
  description = "OpenStack image used for lab VMs."
  type        = string
  default     = "Ubuntu 22.04"
}

variable "flavor_name" {
  description = "OpenStack flavor used for lab VMs."
  type        = string
  default     = "a1-ram2-disk20-perf1"
}

variable "private_network_cidr" {
  description = "CIDR of the private lab network."
  type        = string
  default     = "10.42.0.0/24"
}

variable "private_network_gateway" {
  description = "Gateway IP of the private lab subnet."
  type        = string
  default     = "10.42.0.1"
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH into VMs. Restrict this in production."
  type        = string
  default     = "0.0.0.0/0"
}

variable "assign_floating_ip" {
  description = "Whether to allocate and attach one floating IP per VM."
  type        = bool
  default     = true
}
