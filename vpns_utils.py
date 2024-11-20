# vpns_utils.py
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
    characts = string.ascii_letters + string.digits + "@#$%"
    return "".join(secrets.choice(characts) for _ in range(12))


def get_backup_path() -> str:
    wiw_path = "/opt/wiw/backup"
    vpn_path = "/opt/vpn/backup"
    base_path = wiw_path if os.path.exists(wiw_path) else vpn_path
    if not os.path.exists(base_path):
        os.system(f"sudo mkdir -p {base_path}")
        os.system(f"sudo chown -R $USER:$USER {os.path.dirname(base_path)}")
    return base_path


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
    try:
        with open(file_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    settings[key.strip().lower()] = value.strip()
        return settings
    except FileNotFoundError:
        raise Exception(f"Settings file {file_path} not found")


def load_template_with_update(template_path: str, context: dict) -> str:
    try:
        with open(template_path) as f:
            content = f.read()
            for key, value in context.items():
                content = content.replace(f"${{{key}}}", str(value))
        return content
    except FileNotFoundError:
        raise Exception(f"Template {template_path} not found")
