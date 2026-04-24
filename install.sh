#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo: sudo ./install.sh" >&2
  exit 1
fi

DECK_USER=${DECK_USER:-deck}
DECK_HOME=$(getent passwd "${DECK_USER}" | cut -d: -f6)

if [[ -z "${DECK_HOME}" || ! -d "${DECK_HOME}" ]]; then
  echo "Could not find home directory for user ${DECK_USER}" >&2
  exit 1
fi

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
src_dir="${DECK_HOME}/src/deck-dictate"
bin_dir="${DECK_HOME}/.local/deck-dictate/bin"
model_dir="${DECK_HOME}/.local/share/deck-dictate/models"
voxtype_url="https://github.com/peteonrails/voxtype/releases/download/v0.6.6/voxtype-0.6.6-linux-x86_64-vulkan"
sums_url="https://github.com/peteonrails/voxtype/releases/download/v0.6.6/SHA256SUMS"
model_url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
model_sha256="a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002"

install -d -o "${DECK_USER}" -g "${DECK_USER}" "${src_dir}" "${bin_dir}" "${model_dir}" "${DECK_HOME}/bin"
install -m 0755 -o "${DECK_USER}" -g "${DECK_USER}" "${repo_dir}/scripts/uinput_type.py" "${src_dir}/uinput_type.py"
install -m 0755 -o "${DECK_USER}" -g "${DECK_USER}" "${repo_dir}/scripts/hold_l4_warm.py" "${src_dir}/hold_l4_warm.py"
install -m 0755 -o "${DECK_USER}" -g "${DECK_USER}" "${repo_dir}/scripts/deck-dictate-daemon" "${src_dir}/deck-dictate-daemon"
install -m 0644 -o "${DECK_USER}" -g "${DECK_USER}" "${repo_dir}/config.toml" "${src_dir}/config.toml"

ln -sfn "${src_dir}/hold_l4_warm.py" "${DECK_HOME}/bin/deck-dictate-l4-warm"

tmp=$(mktemp -d)
trap 'rm -rf "${tmp}"' EXIT

curl -fL "${sums_url}" -o "${tmp}/SHA256SUMS"
curl -fL "${voxtype_url}" -o "${tmp}/voxtype"
expected=$(awk '/voxtype-0.6.6-linux-x86_64-vulkan$/ {print $1}' "${tmp}/SHA256SUMS")
actual=$(sha256sum "${tmp}/voxtype" | awk '{print $1}')
if [[ "${expected}" != "${actual}" ]]; then
  echo "voxtype SHA256 mismatch" >&2
  exit 1
fi
install -m 0755 -o "${DECK_USER}" -g "${DECK_USER}" "${tmp}/voxtype" "${bin_dir}/voxtype"

if [[ ! -s "${model_dir}/ggml-base.en.bin" ]]; then
  curl -fL "${model_url}" -o "${tmp}/ggml-base.en.bin"
  actual_model=$(sha256sum "${tmp}/ggml-base.en.bin" | awk '{print $1}')
  if [[ "${actual_model}" != "${model_sha256}" ]]; then
    echo "model SHA256 mismatch" >&2
    exit 1
  fi
  install -m 0644 -o "${DECK_USER}" -g "${DECK_USER}" "${tmp}/ggml-base.en.bin" "${model_dir}/ggml-base.en.bin"
fi

install -d -o "${DECK_USER}" -g "${DECK_USER}" "${DECK_HOME}/.config/systemd/user/deck-dictate.service.d"
install -m 0644 -o "${DECK_USER}" -g "${DECK_USER}" "${repo_dir}/systemd/user/deck-dictate.service" "${DECK_HOME}/.config/systemd/user/deck-dictate.service"
install -m 0644 -o "${DECK_USER}" -g "${DECK_USER}" "${repo_dir}/systemd/drop-ins/deck-dictate-user-resources.conf" "${DECK_HOME}/.config/systemd/user/deck-dictate.service.d/resources.conf"

install -d /etc/systemd/system/deck-dictate-l4.service.d
install -m 0644 "${repo_dir}/systemd/system/deck-dictate-l4.service" /etc/systemd/system/deck-dictate-l4.service
install -m 0644 "${repo_dir}/systemd/drop-ins/deck-dictate-l4-resources.conf" /etc/systemd/system/deck-dictate-l4.service.d/resources.conf

systemctl daemon-reload
sudo -u "${DECK_USER}" XDG_RUNTIME_DIR="/run/user/1000" systemctl --user daemon-reload
sudo -u "${DECK_USER}" XDG_RUNTIME_DIR="/run/user/1000" systemctl --user enable --now deck-dictate.service
systemctl enable --now deck-dictate-l4.service

echo "Installed. Focus a text field, hold L4, speak, release."
