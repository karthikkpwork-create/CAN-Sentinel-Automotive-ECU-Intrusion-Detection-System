#!/usr/bin/env bash
# Create, inspect or remove a VIRTUAL CAN interface.
#
#   sudo scripts/setup_vcan.sh up      [vcan0]   load module, create interface, bring it up
#   scripts/setup_vcan.sh status       [vcan0]   show interface details
#   sudo scripts/setup_vcan.sh down    [vcan0]   bring it down and delete it
#
# Safety: only interfaces named vcanN are ever touched, so a physical CAN
# device (can0, ...) cannot be modified by this script.
set -euo pipefail

ACTION="${1:-}"
IFACE="${2:-vcan0}"

if [[ ! "$IFACE" =~ ^vcan[0-9]{1,3}$ ]]; then
  echo "ERROR: '$IFACE' is not allowed. Only virtual interfaces (vcan0, vcan1, ...) are supported." >&2
  exit 2
fi

if ! command -v ip >/dev/null 2>&1; then
  echo "ERROR: 'ip' command not found. Install it with: sudo apt install iproute2" >&2
  exit 1
fi

SUDO=""
if [[ "$(id -u)" -ne 0 ]]; then
  SUDO="sudo"
fi

case "$ACTION" in
  up)
    if ! ip link show "$IFACE" >/dev/null 2>&1; then
      if ! $SUDO modprobe vcan 2>/dev/null; then
        echo "ERROR: could not load the 'vcan' kernel module." >&2
        echo "  Check support with:  modinfo vcan" >&2
        echo "  Containers, some VMs and the default WSL2 kernel do not include it." >&2
        echo "  See docs/week1_troubleshooting.md ('Kernel module unavailable')." >&2
        exit 1
      fi
      $SUDO ip link add dev "$IFACE" type vcan
    else
      echo "Interface $IFACE already exists; reusing it."
    fi
    $SUDO ip link set up "$IFACE"
    ip -brief link show "$IFACE"
    ;;
  status)
    ip -details link show "$IFACE"
    ;;
  down)
    if ! ip link show "$IFACE" >/dev/null 2>&1; then
      echo "Interface $IFACE does not exist; nothing to do."
      exit 0
    fi
    if ! ip -details link show "$IFACE" | grep -q "vcan"; then
      echo "ERROR: $IFACE is not a virtual CAN interface; refusing to delete it." >&2
      exit 1
    fi
    $SUDO ip link set down "$IFACE"
    $SUDO ip link delete "$IFACE"
    echo "Removed $IFACE."
    ;;
  *)
    echo "Usage: $0 {up|status|down} [vcanN]" >&2
    exit 2
    ;;
esac
