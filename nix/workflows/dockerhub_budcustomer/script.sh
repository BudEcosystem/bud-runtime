#!/bin/sh
set -e

repo_root="$(git rev-parse --show-toplevel)"

note() {
	echo "$@"
}

secret_get() {
	sops decrypt --extract "[\"app.docker.com\"][\"$1\"]" "$repo_root/nix/workflows/secrets.yaml"
}

image_push() {
	# $1: nix arch
	# $2: tag
	package="packages.$1.container_budcustomer"

	nix build ".#$package" -L
	image_tag="$(docker image load -i result | cut -d' ' -f3)"
	# tag="${image_tag##*:}"
	image="${image_tag%%:*}"

	note "updating $image_tag with $package"
	docker image tag "$image_tag" "$image:$2"
	docker push "$image:$2"
}

multiarch_image_push() {
	# $1: multiarch tag
	# $2: arch tag 1
	# $3: arch tag 1

	docker manifest \
		create "$image:$1" \
		--amend "$image:$2" \
		--amend "$image:$3"

	docker manifest push "$image:$1"
}

########
# MAIN #
########

docker login \
	--username "$(secret_get username)" \
	--password "$(secret_get password)"

image_push x86_64-linux nightly
# image_push x86_64-linux x86_64-linux-nightly
# image_push aarch64-linux aarch64-linux-nightly
# multiarch_image_push nightly x86_64-linux-nightly x86_64-linux-nightly
