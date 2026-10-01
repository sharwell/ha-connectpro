"""Constants for the ConnectPro KVM integration."""

DOMAIN = "connectpro"
DEFAULT_NAME = "ConnectPro KVM"
SERVICE_SEND_COMMAND = "send_command"
ATTR_COMMAND = "command"

CONF_DEVICE = "device"
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"

DEFAULT_BAUDRATE = 115200
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1

BYTESIZE_OPTIONS = [5, 6, 7, 8]
PARITY_OPTIONS = ["N", "E", "O", "M", "S"]
STOPBITS_OPTIONS = [1, 2]
