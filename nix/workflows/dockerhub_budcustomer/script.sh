#!/bin/sh
set -e

repo_root="$(git rev-parse --show-toplevel)"

note() {
	echo "$@"
}

secret_get() {
	sops decrypt --extract "[\"app.docker.com\"][\"$1\"]" "$repo_root/nix/workflows/dockerhub_budcustomer/secrets.yaml"
}

image_push() {
	# $1: nix arch
	# $2: tag
	package="packages.$1.container_budcustomer"

	nix build ".#$package" -L
	image_tag="$(docker image load -i result | cut -d' ' -f3 | head -n1)"
	# tag="${image_tag##*:}"
	image="${image_tag%%:*}"

	note "updating $image:$2 with $package"
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

# Get tag from environment variable or default to "nightly"
TAG="${IMAGE_TAG:-nightly}"

note "Building and pushing version: $TAG"

docker login \
	--username "$(secret_get username)" \
	--password "$(secret_get password)"

# Push with specified tag
image_push x86_64-linux "$TAG"

# For release tags, also push as latest
case "$TAG" in
  v* | [0-9]*)
	note "Also pushing as latest tag"
	image_push x86_64-linux latest
	;;
esac

# Uncomment for multi-arch support in the future
# image_push x86_64-linux "x86_64-linux-$TAG"
# image_push aarch64-linux "aarch64-linux-$TAG"
# multiarch_image_push "$TAG" "x86_64-linux-$TAG" "aarch64-linux-$TAG"
