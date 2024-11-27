# Peony OpenVPN Management Scripts

Scripts for deploying and managing OpenVPN servers with Caddy integration. Built on [d3vilh/openvpn-server](https://github.com/d3vilh/openvpn-server).

For detailed specifications and architecture details, please refer to the [documentation](https://docs.google.com/document/d/1sQOw4j7yWPoopRipE6pQS8Y7TJhqU4xim82za_FugUA/).

## Installation

```bash
git clone [repository-url]
cd peony
pip install -r requirements.txt
```

## Directory Structure
The script checks directories in this order:
1. Looks for `/opt/wiw/` first
   - If found, uses:
     - `/opt/wiw/config/`: Configurations  
     - `/opt/wiw/backup/`: Backups
2. If `/opt/wiw/` is not found, creates and uses `/opt/vpn/` (for customers):
   - `/opt/vpn/config/`: Configurations
   - `/opt/vpn/backup/`: Backups

The scripts will automatically create the required directories with proper permissions if dont exist.


### 1. caddy_settings
```bash
# Mandatory
HOSTNAME=

# Optional (shown with default values)
CADDY_VOLUME_PATH=/opt/docker/volumes/${container_name}
VPN_PROXY_NETWORK=vpns-proxy
VPN_DOCKER_SUBNET=172.28.0.0/24
```

### 2. vpn_settings
```bash
# Mandatory
CADDY_HOSTNAME= # Must match the HOSTNAME from caddy_settings

EASYRSA_DN=org
EASYRSA_REQ_COUNTRY=FR
EASYRSA_REQ_PROVINCE=GE
EASYRSA_REQ_CITY=Nancy
EASYRSA_REQ_ORG=TheWiw
EASYRSA_REQ_EMAIL=willy@thewiw.com
openvpn_prot=udp
```

## Scripts Usage

### Caddy Management (vpns-caddy.py)
Must be run first
```bash
# Create Caddy server (required before any VPN creation)
sudo python3 vpns-caddy.py create [name]

# Remove Caddy (fails if VPNs exist)
sudo python3 vpns-caddy.py remove [name]
```

### VPN Management (vpns-vpn.py)
```bash
# Create new VPN
sudo python3 vpns-vpn.py create vpn01

# Monitor initialization
docker logs -f vpn001

# Update existing VPN
sudo python3 vpns-vpn.py update vpn01

# Remove VPN
sudo python3 vpns-vpn.py remove vpn01
```

### Backup Management (vpns-backup.py)
```bash
# Default backup
sudo python3 vpns-backup.py

# Custom backup location
sudo python3 vpns-backup.py --dest /path/to/backup

# Custom filename (using --file)
sudo python3 vpns-backup.py --file custom-backup.tgz

# Specify Caddy name
sudo python3 vpns-backup.py --caddy custom_caddy
```

## Automatic Backup System
Backups are automatically created in these situations:
- Before VPN removal: `[caddy-name]-[vpn-name]-YYYYMMDD_HHMM-remove.tgz`
- Before Caddy removal: `[caddy-name]-YYYYMMDD_HHMM-remove.tgz`
- During manual backup: `[caddy-name]-YYYYMMDD_HHMM.tgz`

Backups contain:
- Caddy configurations
- VPN configurations
- All associated files and settings

Backup location follows the same directory checking logic:
1. First try: `/opt/wiw/backup/`
2. If not found, uses: `/opt/vpn/backup/`

## Post-Initialization Steps

Once you have ensured with the VPN logs that everything is initialized, you can access the dashboard UI.

→ Click on **Configuration** → **OpenVPN Server**: Edit config (at the top of the page) to ensure everything is set up correctly.

→ Click on **Configuration** → **OpenVPN Client**: View config (at the bottom of the page this time).

→ Click on **Configuration** → **EasyRSA**: View vars to ensure everything is okay.

If everything is set up correctly, you can access **Certificates** and create a certificate.


## Notes
- First run must be Caddy creation before any VPN operations
- After creating a new vpn this can take a bit of time to be operational because DH parameter generation can be time-consuming, especially with 4096-bit keys on slower hardware 
you can monitor VPN initialization with `docker logs -f [vpn-name]` before attempting connection
- All scripts require sudo 
- Settings files must be properly configured before first use
