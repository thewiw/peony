Scripts for deploying and managing OpenVPN servers with Caddy integration. Built on [d3vilh/openvpn-server](https://github.com/d3vilh/openvpn-server).

For detailed specifications and architecture, please refer to the [documentation](https://docs.google.com/document/d/1sQOw4j7yWPoopRipE6pQS8Y7TJhqU4xim82za_FugUA/).

## Overview

This system consists of three main components:
1. Caddy Server (Reverse Proxy)
2. OpenVPN Management
3. Backup System

## Prerequisites
- Linux system with sudo privileges
- Docker installed and running
- Python 3.9 or higher

## Installation

There are two ways to install and use Peony:

### Method 1: Via pip (Recommended)

1. Create and activate a virtual environment:
```bash
python -m venv venv_peony
source venv_peony/bin/activate
```

2. Install Peony:
```bash
pip install [projet-name]
```

Commands will be available as:
```bash
sudo peony-caddy init
sudo peony-vpn create vpn01
sudo peony-backup
```

### Method 2: From Source

1. Clone the repository:
```bash
git clone [repository-url] peony
cd peony
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

When running from source, commands should be executed from the project root as:
```bash
sudo python3 src/peony/caddy.py init
sudo python3 src/peony/vpn.py create vpn01
sudo python3 src/peony/backup.py
```
## Getting Started

### Initialize Configuration Files:
```bash
# If installed with pip:

sudo peony-caddy init
```
```bash
# If running from source:
sudo python3 src/peony/caddy.py init
```

This will create the necessary configuration files in ~/.config/peony/.

### Edit the Configuration Files:

#### Caddy Configuration (~/.config/peony/caddy_settings):
```bash
HOSTNAME= # Your server hostname or IP (e.g., serv.company.com) Required:

# Optional (default values shown):
CADDY_VOLUME_PATH=/opt/docker/volumes/${container_name}
VPN_PROXY_NETWORK=vpns-proxy
VPN_DOCKER_SUBNET=172.28.0.0/24
```

#### VPN Configuration (~/.config/peony/vpn_settings):
```bash
# Easy-RSA Certificate Configuration:
EASYRSA_REQ_COUNTRY=     # Two-letter country code (e.g., "FR")
EASYRSA_REQ_PROVINCE=    # State or province
EASYRSA_REQ_CITY=        # City name
EASYRSA_REQ_ORG=         # Organization name
EASYRSA_REQ_EMAIL=       # Admin email address
EASYRSA_REQ_OU=          # Organizational Unit (optional)

# Certificate Parameters (optional with defaults):
EASYRSA_KEY_SIZE=    # Key size in bits (2048 or 4096 recommended)
EASYRSA_CA_EXPIRE=   # CA certificate expiry in days
EASYRSA_CERT_EXPIRE= # Server certificate expiry in days
EASYRSA_CERT_RENEW=  # Certificate renewal period in days
EASYRSA_CRL_DAYS=    # Certificate validity period

# OpenVPN Configuration (optional with defaults):
OPENVPN_PROT=udp     # Protocol (udp or tcp)
OPENVPN_GATEWAY=false # Route all client traffic through VPN
OPENVPN_DNS=false    # Use VPN DNS servers
```

## Usage

Commands below are shown for pip installation. If running from source, replace peony-command with python3 src/peony/command.py.

### Caddy Management:
```bash
# Initialize configuration files (first time setup)

sudo peony-caddy init
# Create Caddy server

sudo peony-caddy create [caddy-name]

# Remove Caddy server
sudo peony-caddy remove [caddy-name]
```

### VPN Management:
```bash

# Create a new VPN
sudo peony-vpn create vpn01

# Update existing VPN
sudo peony-vpn update vpn01

# Remove VPN
sudo peony-vpn remove vpn01

# List all VPNs
sudo peony-vpn list
```


### Backup Management:
```bash

# Create backup with default settings
sudo peony-backup

# Available options:
--dest /path/to/backup    # Custom backup location
--file backup-name.tgz    # Custom backup filename
--caddy custom-caddy      # Specify Caddy container name
```

## Directory Structure and Path Management

### Configuration Files:
- ~/.config/peony/caddy_settings
- ~/.config/peony/vpn_settings

### Application Directories:
- /opt/docker/volumes/[caddy-name]: Caddy server files
- /opt/vpn/config/[vpn-name]: VPN configurations
- /opt/vpn/backup/: Backup files

## Important Notes

### Setup Order:
1. Run init to create configuration files.
2. Edit configuration files in ~/.config/peony/.
3. Create Caddy server **BEFORE** creating any VPNs.
4. Create VPNs after Caddy is running.

### First VPN Creation:
- Initial setup may take time (key generation).
- Monitor initialization: docker logs -f [vpn-name].
- Wait for completion before attempting connections.

### System Requirements:
- All commands require sudo privileges.
- Docker must be installed and running.
- Virtual environment recommended for installation.

## Accessing Your VPNs

After setup is complete:
1. Access the VPN selection page: https://[your-hostname]/vpn-select.html.
2. Choose your VPN from the list.
3. Log in to the management interface with provided Admin credentials.

### Verify Settings:
1. Click on Configuration → OpenVPN Server: Edit config.
2. Click on Configuration → OpenVPN Client: View config.
3. Click on Configuration → EasyRSA: View vars.
4. Create certificates from the Certificates section.

### Create Users:
Administrators can manage profiles and create new users from the Profile Configuration page.
(Click on the user icon → Profile Configuration).

### Troubleshooting:
Verify your .ovpn files if connections fail. Update the OpenVPN client configuration from the UI dashboard if needed.