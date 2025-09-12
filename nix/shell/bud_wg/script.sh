#!/bin/sh

key_prv="$(wg genkey)"
key_pub="$(echo "$key_prv" | wg pubkey)"

wg_config_prv_gen() {
	host_addr="${1:?}"

	cat <<-EOF
		[interface]
		Address = 10.54.132.$host_addr/24
		PrivateKey = $key_prv
		MTU = 1420

		[Peer]
		PublicKey = O2GRMEWf22YRGKexHAdg1fitucTZ/U/om2MWEJMeyFQ=
		Endpoint = primary.k8s.bud.studio:51820
		PersistentKeepalive = 25
		AllowedIPs = 10.54.132.0/24
	EOF
}

wg_config_pub_gen() {
	host_addr="${1:?}"
	name="${2:?}"

	cat <<-EOF
		[Peer]
		# friendly_name = $name
		PublicKey = $key_pub
		AllowedIPs = 10.54.132.$host_addr/32
	EOF
}

if [ "$#" != 2 ]; then
	echo "Usage: ${0##*/} <host_addr> <name>"
	exit 1
fi

wg_config_prv_gen "$1" | qrencode -t ANSI256UTF8
echo "----------------"
wg_config_prv_gen "$1"
echo "----------------"
wg_config_pub_gen "$1" "$2"
