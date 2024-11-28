import os
import string
import secrets


def get_config_path(name: str = None) -> str:
    wiw_path = "/opt/wiw/config"
    vpn_path = "/opt/vpn/config"
    base_path = wiw_path if os.path.exists(wiw_path) else vpn_path
    if not os.path.exists(base_path):
        os.system(f"sudo mkdir -p {base_path}")
        os.system(f"sudo chown -R $USER:$USER {os.path.dirname(base_path)}")
    return os.path.join(base_path, name) if name else base_path


def get_caddy_path(caddy_name: str = None) -> str:
    base_path = "/opt/docker/volumes"
    return os.path.join(base_path, caddy_name) if caddy_name else base_path


def create_vpn_directories(output_dir: str) -> None:
    directories = ["config", "pki", "clients", "db", "staticclients", "log"]
    for dir in directories:
        os.makedirs(os.path.join(output_dir, dir), exist_ok=True)


def generate_password() -> str:
    characts = string.ascii_letters + string.digits
    return "".join(secrets.choice(characts) for _ in range(12))


def get_backup_path() -> str:
    wiw_base = "/opt/wiw"
    vpn_base = "/opt/vpn"
    
    base_dir = wiw_base if os.path.exists(wiw_base) else vpn_base
    backup_path = os.path.join(base_dir, "backup")
    
    if not os.path.exists(backup_path):
        os.system(f"sudo mkdir -p {backup_path}")
        os.system(f"sudo chown -R $USER:$USER {base_dir}")
        
    return backup_path


def find_caddy_server() -> str:
    volumes_dir = "/opt/docker/volumes"
    if not os.path.exists(volumes_dir):
        return None
    return next(
        (
            d
            for d in os.listdir(volumes_dir)
            if os.path.exists(os.path.join(volumes_dir, d, "Caddyfile"))
        ),
        None,
    )


def read_settings(file_path: str, defaults: dict = None) -> dict:
    settings = defaults or {}
    
    wiw_path = "/opt/wiw"
    vpn_path = "/opt/vpn"

    base_paths = [
        os.path.join(wiw_path, file_path),
        os.path.join(vpn_path, file_path),
        file_path
    ]
    
    for path in base_paths:
        try:
            with open(path) as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        settings[key.strip().lower()] = value.strip()
                return settings
        except FileNotFoundError:
            continue
            
    raise Exception(f"Settings file {file_path} not found in {base_paths}")

def load_template_with_update(template_path: str, context: dict) -> str:
    try:
        with open(template_path) as f:
            content = f.read()
            for key, value in context.items():
                content = content.replace(f"${{{key}}}", str(value))
        return content
    except FileNotFoundError:
        raise Exception(f"Template {template_path} not found")
