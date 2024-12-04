# Peony OpenVPN Management Scripts

Scripts for deploying and managing OpenVPN servers with Caddy integration. Built on [d3vilh/openvpn-server](https://github.com/d3vilh/openvpn-server).

For detailed specifications and architecture details, please refer to the [documentation](https://docs.google.com/document/d/1sQOw4j7yWPoopRipE6pQS8Y7TJhqU4xim82za_FugUA/).


## Overview

This system consists of three main components:
1. Caddy Server (Reverse Proxy)
2. OpenVPN Management
3. Backup System

## Prerequisites
- Linux system with sudo privileges
- Docker installed and running
- Python 3 with required packages (`pip install -r requirements.txt`)
- Git for cloning the repository

## Directory Structure and Path Management

The scripts check directories in this order:
1. Looks for `/opt/wiw/` first
   - If found, uses:
     - `/opt/wiw/config/`: Configurations  
     - `/opt/wiw/backup/`: Backups
2. If `/opt/wiw/` is not found, creates and uses `/opt/vpn/` (for customers):
   - `/opt/vpn/config/`: Configurations
   - `/opt/vpn/backup/`: Backups

## 1. Caddy Server Setup (Required First Step)

### What is Caddy?
Caddy is a modern web server that acts as a secure gateway to your VPN management interfaces. It:
- Provides secure HTTPS access to VPN admin interfaces
- Manages multiple VPN interfaces through a single point
- Handles SSL certificates automatically
- Serves the VPN selection page to list and access your VPNs

### Caddy Configuration (caddy_settings)
Before installing Caddy, configure `caddy_settings` at project root:
```bash
# Required:
HOSTNAME= # Your server hostname or IP (ex vpn.company.com)

# Optional (default values shown):
CADDY_VOLUME_PATH=/opt/docker/volumes/${container_name}
VPN_PROXY_NETWORK=vpns-proxy
VPN_DOCKER_SUBNET=172.28.0.0/24
```

### Installing Caddy
```bash
# Create Caddy server
sudo python3 vpns-caddy.py create [caddy-name]
```

Notes:
- ${container_name} in configurations will be replaced with your chosen caddy-name
- If no name is specified, "caddy" is used by default
- This name is used for :
  - Caddy docker container name
  - Volume paths (/opt/docker/volumes/${container_name})
  - Backup file prefixes

## 2. VPN Management

### VPN Configuration (vpn_settings)
Before creating any VPN, configure `vpn_settings` at project root:

```bash

# Easy-RSA Certificate Configuration:

EASYRSA_REQ_COUNTRY=     # Two-letter country code (e.g., "FR")
EASYRSA_REQ_PROVINCE=    # State or province
EASYRSA_REQ_CITY=        # City name
EASYRSA_REQ_ORG=         # Organization name
EASYRSA_REQ_EMAIL=       # Admin email address
EASYRSA_REQ_OU=          # Organizational Unit (optional)

# Certificate Parameters (optional with defaults):
EASYRSA_KEY_SIZE=    # Key size in bits 2048 or 4096 recommended
EASYRSA_CA_EXPIRE=  # CA certificate expiry in days default
EASYRSA_CERT_EXPIRE= # Server certificate expiry in days
EASYRSA_CERT_RENEW=   # Certificate renewal period in days
EASYRSA_CRL_DAYS=     # Certificate validity period

# OpenVPN Configuration (optional with defaults):
OPENVPN_PROT=udp        # Protocol (udp or tcp)
OPENVPN_GATEWAY=false  # Route all client traffic through VPN(true or false)
OPENVPN_DNS=false      
```

### Creating a New VPN
```bash
# Create a new VPN instance
sudo python3 vpns-vpn.py create vpn01
```

What happens during creation:
- Clones OpenVPN server template and creates required directories
- Generates SSL certificates and security keys (can take several minutes on low end pc)
- Configures OpenVPN server:
  - Sets network subnets for VPN clients
  - Configures security parameters
  - Sets up client connection rules
- Creates Docker containers:
  - OpenVPN server for handling VPN connections
  - OpenVPN UI interface for managing users and certificates
- Integrates with Caddy:
  - Updates Caddy configuration file
  - Adds VPN to the selection page
- Sets up network configuration:
  - Configures port forwarding

### Managing Existing VPNs

```bash
# Update an existing VPN
sudo python3 vpns-vpn.py update vpn01
```

What happens during update:
- Creates backup in default backup location
- Updates all VPN configurations (server.conf, client.conf, certificates)
- Stops and restarts VPN containers to apply changes
- Updates Caddy configuration
- Restarts all required services

```bash
# Remove a VPN
sudo python3 vpns-vpn.py remove vpn01
```

What happens during removal:
- Creates safety backup before deletion
- Stops and removes VPN containers and their UI
- Removes VPN network configuration
- Removes VPN from Caddy configuration
- Deletes all VPN files and certificates
- Updates VPN selection page

```bash
# List all VPN
sudo python3 vpns-vpn.py list
```

What happens during list:
- Shows all configured VPNs
- Displays each VPN's current status (Running, Exited, etc)
- Shows the port number for each VPN

## 3. Backup System

The backup system provides two types of backups to ensure your configurations are protected.

### Backup Types

#### 1. Automatic Backups
Created automatically by the system before operations bellow:
- Before removing a VPN
- Before updating a VPN
- Before removing Caddy server

Format: `[caddy-name]-[vpn-name]-YYYYMMDD_HHMMSS-remove.tgz`

#### 2. Manual Backups

```bash
# Create backup with default settings
sudo python3 vpns-backup.py

# Available options:
--dest /path/to/backup    # Custom backup location
--file backup-name.tgz    # Custom backup filename
--caddy custom-caddy      # Specify Caddy container name (default: "caddy")

# Complete example with all options
sudo python3 vpns-backup.py --dest /documents/backups --file backup.tgz --caddy custom-caddy
```

### What Gets Backed Up
1. Caddy server configuration from (`opt/docker/volumes/[caddy-name]`)
2. All detected VPN configurations from (`opt/vpn/config/[vpn-name]`) or (`opt/wiw/config/[vpn-name]`)

### Backup Location Priority
1. Custom location (if specified with `--dest`)
2. Default locations (in order):
   - `/opt/wiw/backup/` (if exists)
   - `/opt/vpn/backup/` (fallback)

## Directory Structure
```
├── caddy_settings        # Caddy configuration
├── vpn_settings         # VPN configuration
├── templates/           # Configuration templates
│   ├── caddy/          # Caddy-related templates
│   └── vpns/           # VPN-related templates
├── vpns-backup.py      # Backup script
├── vpns-caddy.py       # Caddy management script
└── vpns-vpn.py         # VPN management script
```

## Important Notes


1. Setup Order
   - Configuration files must be properly filled first
   - Caddy MUST be installed before creating any VPNs
   - VPNs can be created after Caddy is running
   - We suggest you to only edit `vpn_settings` and `caddy_settings`
   - You can also use the UI dashboard for additional settings

2. First VPN Creation
   - Initial setup may take time (key generation)
   - Monitor initialization: `docker logs -f [vpn-name]`
   - Wait for completion before attempting connections

3. System Requirements
   - All scripts require sudo privileges
   - Python 3 with required packages (see requirements.txt)
   - Docker installed and running



## Accessing Your VPNs

After setup is complete:
1. Access the VPN selection page: `https://[your-hostname]/vpn-select.html`
2. Choose your VPN from the list
3. Log in to the management interface with provided credentials

### Verify Settings

1. Click on Configuration → OpenVPN Server: Edit config (at the top of the page) to ensure everything is set up correctly.

2. Click on Configuration → OpenVPN Client: View config (at the bottom of the page this time).

3. Click on Configuration → EasyRSA: View vars to ensure everything is okay.

4. If everything is set up correctly, you can access Certificates and create a certificate.

#### Troubleshooting
**Verify your .opvn files** if it's not correct you should update the OpenVPN client manually in the UI dashboard → 
configuration → OpenVPN Client and redownload the .opvn files or you can edit yourself the .opvn file