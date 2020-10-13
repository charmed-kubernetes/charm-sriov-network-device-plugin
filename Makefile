CHANNEL ?= unpublished
CHARM_BUILD_DIR ?= .
CHARM := sriov-network-device-plugin

setup-env:
	@bash script/bootstrap

charm: setup-env
	@env CHARM=$(CHARM) CHARM_BUILD_DIR=$(CHARM_BUILD_DIR) bash script/build

upload:
ifndef NAMESPACE
	$(error NAMESPACE is not set)
endif

	@env CHARM=$(CHARM) NAMESPACE=$(NAMESPACE) CHANNEL=$(CHANNEL) CHARM_BUILD_DIR=$(CHARM_BUILD_DIR) bash script/upload

.phony: charm upload setup-env
all: charm
