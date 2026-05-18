from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "dev-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "topology",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]
    },
}]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = True

SNMP_COMMUNITY = os.getenv("SNMP_COMMUNITY", "public")
ROUTER_IP = os.getenv("ROUTER_IP", "10.10.10.1")
ROUTER_PRIMARY_LINK_IP = os.getenv("ROUTER_PRIMARY_LINK_IP", "103.4.116.146")
ROUTER_SECONDARY_LINK_IP = os.getenv("ROUTER_SECONDARY_LINK_IP", "202.51.186.226")
ROUTER_PRIMARY_GATEWAY_IP = os.getenv("ROUTER_PRIMARY_GATEWAY_IP", "103.4.116.145")
ROUTER_SECONDARY_GATEWAY_IP = os.getenv("ROUTER_SECONDARY_GATEWAY_IP", "202.51.186.225")
ROUTER_PRIMARY_INTERFACE_NAME = os.getenv("ROUTER_PRIMARY_INTERFACE_NAME", "WAN1")
ROUTER_SECONDARY_INTERFACE_NAME = os.getenv("ROUTER_SECONDARY_INTERFACE_NAME", "WAN2")
SWITCH_IP = os.getenv("SWITCH_IP", "10.10.10.100")
LAPTOP_IP = os.getenv("LAPTOP_IP", "10.10.10.253")
SERVER_IP = os.getenv("SERVER_IP", "10.10.10.3")

ROUTER_TO_SWITCH_ROUTER_PORT_INDEX = 2
ROUTER_TO_SWITCH_SWITCH_PORT_INDEX = 1
ROUTER_TO_SERVER_ROUTER_INTERFACE_NAME = os.getenv(
    "ROUTER_TO_SERVER_ROUTER_INTERFACE_NAME",
    "LAN",
)

SWITCH_UPLINK_PORT_INDEX = 1
AUTO_DISCOVER_LAPTOP_SWITCH_PORT = True
AUTO_DISCOVER_SERVER_ROUTER_PORT = True
LAPTOP_WIFI_EXTEND_TOKEN = "wifi_info"
LAPTOP_GPU_EXTEND_TOKEN = "gpu_info"
SERVER_METRICS_EXTEND_TOKEN = "server_metrics"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "")
