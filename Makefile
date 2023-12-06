# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

# ----The Makefile for automated building (and hopefully) deployment
SHELL=bash

.DEFAULT_GOAL := nothing

# By default, 'make' does nothing and only prints available options
nothing:
	@echo -e "\nHi! How can I help you?"
	@echo -e "  - 'make package':"
	@echo -e "          Build the agent package distribution (sdist and bdist)."
	@echo -e "  - 'make sdist':"
	@echo -e "          Build sdist zip archive (.tar.gz in dist/)."
	@echo -e "  - 'make manylinux-wheels':"
	@echo -e "          Build manylinux 64-bit Python bdist (.whl in dist/)."
	@echo -e "  - 'make aws-lambda':"
	@echo -e "          Build the AWS Lambda layer (zip archive in dist/)."
	@echo -e "  - 'make wrapper':"
	@echo -e "          Locally generate SWIG wrapper for C/C++ headers."
	@echo -e "  - 'STAGING_OBOE=1 make wrapper':"
	@echo -e "          Locally generate SWIG wrapper for C/C++ headers using liboboe VERSION from staging."
	@echo -e "  - 'make wrapper-from-local':"
	@echo -e "          Locally generate SWIG wrapper for C/C++ headers using neighbouring oboe checkout."
	@echo -e "Check the Makefile for other targets/options.\n"

#----------------------------------------------------------------------------------------------------------------------#
# variable definitions and recipes for downloading of required header and library files
#----------------------------------------------------------------------------------------------------------------------#

# Platform for wheel tagging: x86_64 or aarch64
platform := ${shell uname -p}
ifeq (${platform},aarch64)
    wheel_tag := manylinux_2_28_aarch64
else
    platform := x86_64
    wheel_tag := manylinux_2_28_x86_64
endif

# LIBOBOE is the name of the liboboe shared library
LIBOBOEALPINEAARCH := "liboboe-1.0-alpine-aarch64.so"
LIBOBOEALPINEX86 := "liboboe-1.0-alpine-x86_64.so"
LIBOBOEORGAARCH := "liboboe-1.0-aarch64.so"
LIBOBOEORGX86 := "liboboe-1.0-x86_64.so"
LIBOBOESERVERLESSAARCH := "liboboe-1.0-lambda-aarch64.so"
LIBOBOESERVERLESSX86 := "liboboe-1.0-lambda-x86_64.so"
# Version of the C-library extension is stored under /solarwinds_apm/extension/VERSION (Otel export compatible as of 10.3.4)
OBOEVERSION := $(shell cat ./solarwinds_apm/extension/VERSION)

# specification of source of header and library files
OBOEREPO := "https://agent-binaries.global.st-ssp.solarwinds.com/apm/c-lib/${OBOEVERSION}"

verify-oboe-version:
	@echo -e "Downloading Oboe VERSION file from ${OBOEREPO}"
	@cd solarwinds_apm/extension; \
		curl -f "${OBOEREPO}/VERSION" -o "VERSION.tmp" ; \
		if [ $$? -ne 0 ]; then echo " **** Failed to download VERSION  ****" ; exit 1; fi; \
		diff -q VERSION.tmp VERSION; \
		if [ $$? -ne 0 ]; then \
			echo " **** Failed version verification! Local VERSION differs from downloaded version   ****" ; \
			echo "Content of local VERSION file:"; \
			cat VERSION; \
			echo "Content of downloaded VERSION file:"; \
			cat VERSION.tmp; \
			rm VERSION.tmp; \
			exit 1; \
		fi; \
		rm VERSION.tmp
	@echo -e "VERSION verification successful"

# Download the pre-compiled liboboe shared library from source specified in OBOEREPO
download-liboboe: verify-oboe-version
	@echo -e "Downloading ${LIBOBOEORGAARCH}, ${LIBOBOEORGX86}, ${LIBOBOEALPINEAARCH} and ${LIBOBOEALPINEX86} shared libraries.\n"
	@cd solarwinds_apm/extension; \
		curl -o ${LIBOBOEORGAARCH}  "${OBOEREPO}/${LIBOBOEORGAARCH}"; \
		if [ $$? -ne 0 ]; then echo " **** fail to download ${LIBOBOEORGAARCH} ****" ; exit 1; fi; \
		curl -o ${LIBOBOEORGX86}  "${OBOEREPO}/${LIBOBOEORGX86}"; \
		if [ $$? -ne 0 ]; then echo " **** fail to download ${LIBOBOEORGX86} ****" ; exit 1; fi; \
		curl -o ${LIBOBOEALPINEAARCH}  "${OBOEREPO}/${LIBOBOEALPINEAARCH}"; \
		if [ $$? -ne 0 ]; then echo " **** fail to download ${LIBOBOEALPINEAARCH} ****" ; exit 1; fi; \
		curl -o ${LIBOBOEALPINEX86}  "${OBOEREPO}/${LIBOBOEALPINEX86}"; \
		if [ $$? -ne 0 ]; then echo " **** fail to download ${LIBOBOEALPINEX86} ****" ; exit 1; fi; \
		curl -f -O "${OBOEREPO}/VERSION"; \
		if [ $$? -ne 0 ]; then echo " **** fail to download VERSION  ****" ; exit 1; fi
	@echo -e "Downloading ${LIBOBOESERVERLESSAARCH} and ${LIBOBOESERVERLESSX86} shared libraries.\n"
	@cd solarwinds_apm/extension; \
		curl -o $(LIBOBOESERVERLESSAARCH)  "${OBOEREPO}/${LIBOBOESERVERLESSAARCH}"; \
		if [ $$? -ne 0 ]; then echo " **** failed to download ${LIBOBOESERVERLESSAARCH} ****" ; exit 1; fi; \
		curl -o $(LIBOBOESERVERLESSX86)  "${OBOEREPO}/${LIBOBOESERVERLESSX86}"; \
		if [ $$? -ne 0 ]; then echo " **** failed to download ${LIBOBOESERVERLESSX86} ****" ; exit 1; fi;

# Download liboboe header files (Python wrapper for Oboe c-lib) from source specified in OBOEREPO
download-headers: verify-oboe-version download-bson-headers
	@echo -e "Downloading header files (.hpp, .h, .i)"
	@echo "Downloading files from ${OBOEREPO}:"
	@cd solarwinds_apm/extension; \
		for i in oboe.h oboe_api.h oboe_api.cpp oboe.i oboe_debug.h; do \
			echo "Downloading $$i"; \
			curl -f -O "${OBOEREPO}/include/$$i"; \
			if [ $$? -ne 0 ]; then echo " **** fail to download $$i ****" ; exit 1; fi; \
		done

# Download bson header files from source specified in OBOEREPO
download-bson-headers:
	@echo -e "Downloading bson header files (.hpp, .h)"
	@if [ ! -d solarwinds_apm/extension/bson ]; then \
		mkdir solarwinds_apm/extension/bson; \
		echo "Created solarwinds_apm/extension/bson"; \
	 fi
	@echo "Downloading files from ${OBOEREPO}:"
	@cd solarwinds_apm/extension/bson; \
		for i in bson.h platform_hacks.h; do \
			echo "Downloading $$i"; \
			curl -f -O "${OBOEREPO}/include/bson/$$i"; \
			if [ $$? -ne 0 ]; then echo " **** fail to download $$i ****" ; exit 1; fi; \
		done

# download all required header and library files
download-all: download-headers download-liboboe

#----------------------------------------------------------------------------------------------------------------------#
# check if build deps are installed
#----------------------------------------------------------------------------------------------------------------------#

check-swig:
	@echo -e "Is SWIG installed?"
	@command -v swig >/dev/null 2>&1 || \
		{ echo >&2 "Swig is required to build the distribution. Aborting."; exit 1;}
	@echo -e "Yes."

check-zip:
	@echo -e "Is zip installed?"
	@command -v zip >/dev/null 2>&1 || \
		{ echo >&2 "zip is required to build lambda layer. Installing."; dnf install zip -y;}
	@echo -e "Yes."

#----------------------------------------------------------------------------------------------------------------------#
# recipes for building the package distribution
#----------------------------------------------------------------------------------------------------------------------#

# Build the Python wrapper from liboboe headers inside build container
wrapper: check-swig download-all
	@echo -e "Generating SWIG wrapper for C/C++ headers."
	@cd solarwinds_apm/extension && ./gen_bindings.sh

# Create package source distribution archive
sdist: wrapper
	@echo -e "Generating python agent sdist package"
	@python3.8 setup.py sdist
	@echo -e "\nDone."

# Check local package source distribution archive contents, without install
CURR_DIR := $(shell pwd)
check-sdist-local:
	@cd ./tests/docker/install && MODE=local APM_ROOT=$(CURR_DIR) ./_helper_check_sdist.sh
	@cd $(CURR_DIR)

# Build the Python agent package bdist (wheels) for 64 bit many linux systems (except Alpine).
# The recipe builds the wheels for all Python versions available in the docker image EXCEPT py36, similarly to the example provided
# in the corresponding repo of the Docker images: https://github.com/pypa/manylinux#example.
manylinux-wheels: wrapper
	@echo -e "Generating python agent package any-linux wheels for 64 bit systems"
	@set -e; for PYBIN in /opt/python/*/bin; do if [ "$${PYBIN}" != "/opt/python/cp36-cp36m/bin" ]; then "$${PYBIN}/pip" -v wheel . -w ./tmp_dist/ --no-deps; fi; done
	@echo -e "Tagging wheels with $(wheel_tag)"
	@set -e; for whl in ./tmp_dist/*.whl; do auditwheel repair --plat $(wheel_tag) "$$whl" -w ./dist/; done
	@rm -rf ./tmp_dist
	@echo -e "\nDone."

# Check local package wheel contents, without install
check-wheel-local:
	@cd ./tests/docker/install && MODE=local APM_ROOT=$(CURR_DIR) ./_helper_check_wheel.sh
	@cd $(CURR_DIR)

# Build and check the full Python agent distribution (sdist and wheels)
package: sdist check-sdist-local manylinux-wheels check-wheel-local

# Build APM Python AWS lambda layer as zip artifact
# with extension compatible with current environment
# (x86_64 OR aarch64)
target_dir := "./tmp-lambda"
aws-lambda: export AWS_LAMBDA_FUNCTION_NAME = set-for-build
aws-lambda: export LAMBDA_TASK_ROOT = set-for-build
aws-lambda: check-zip wrapper
	@if [ -f ./dist/solarwinds_apm_lambda_${platform}.zip ]; then \
		echo -e "Deleting old solarwinds_apm_lambda_${platform}.zip"; \
		rm ./dist/solarwinds_apm_lambda_${platform}.zip; \
	 fi
	rm -rf ${target_dir}
	@echo -e "Creating target directory ${target_dir} for AWS Lambda layer artifacts."
	mkdir -p ${target_dir}/python
	@echo -e "Install upstream dependencies to include in layer"
	@/opt/python/cp38-cp38/bin/pip3.8 install -t ${target_dir}/python -r lambda/requirements.txt
	@echo -e "Install upstream dependencies without deps to include in layer"
	@/opt/python/cp38-cp38/bin/pip3.8 install -t ${target_dir}/nodeps -r lambda/requirements-nodeps.txt --no-deps
	@echo -e "Install solarwinds_apm to be packed up in zip archive to target directory."
	@/opt/python/cp38-cp38/bin/pip3.8 install . -t ${target_dir}/nodeps --no-deps
	@echo -e "Removing non-lambda C-extension library files generated by pip install under target directory."
	@rm -rf ${target_dir}/nodeps/solarwinds_apm/extension/*.so*
	@echo -e "Building AWS Lambda version of C-extensions for all supported Python versions in target directory."
	@set -e; for PYBIN in cp37-cp37m cp38-cp38 cp39-cp39 cp310-cp310 cp311-cp311; do /opt/python/$${PYBIN}/bin/python setup.py build_ext -b ${target_dir}/nodeps; done
	@echo -e "Copying AWS Lambda specific Oboe library liboboe-1.0-lambda-${platform}.so into target directory."
	@cp solarwinds_apm/extension/liboboe-1.0-lambda-${platform}.so ${target_dir}/nodeps/solarwinds_apm/extension/liboboe.so
	@echo -e "Moving no-deps dependencies, needed for full opentelemetry/instrumentation path"
	@cp -r ${target_dir}/nodeps/* ${target_dir}/python
	@rm -rf ${target_dir}/nodeps
	@echo -e "Copying OpenTelemetry lambda wrapper and entry script into target directory."
	@cp lambda/otel_wrapper.py ${target_dir}/python/otel_wrapper.py
	@cp lambda/otel-instrument ${target_dir}/otel-instrument
	@chmod 755 ${target_dir}/otel-instrument
	@echo -e "Removing unnecessary boto, six, setuptools, urllib3 installations"
	@rm -rf ${target_dir}/python/boto*
	@rm -rf ${target_dir}/python/six*
	@rm -rf ${target_dir}/python/setuptools*
	@rm -rf ${target_dir}/python/urllib3*
	@find ${target_dir}/python -type d -name '__pycache__' | xargs rm -rf
	@if [[ ! -d dist ]]; then mkdir dist; fi
	@pushd ${target_dir} && zip -r ../dist/solarwinds_apm_lambda_${platform}.zip . && popd
	@rm -rf ${target_dir} ./build
	@echo -e "\nDone."

#----------------------------------------------------------------------------------------------------------------------#
# recipes for local development
#----------------------------------------------------------------------------------------------------------------------#

# neighbouring local liboboe directory
OTELOBOEREPO := /code/solarwinds-apm-liboboe/liboboe

# Copy the pre-compiled liboboe shared library from source specified in OTELOBOEREPO
copy-liboboe:
	@echo -e "Copying shared library.\n"
	@cd solarwinds_apm/extension; \
		cp "${OTELOBOEREPO}/liboboe-1.0-${platform}.so" .; \
		if [ $$? -ne 0 ]; then echo " **** failed to copy shared library ****" ; exit 1; fi;

# Copy liboboe header files (Python wrapper for Oboe c-lib) from source specified in OTELOBOEREPO
copy-headers: copy-bson-headers
	@echo -e "Copying header files (.hpp, .h, .i)"
	@echo "Copying files from ${OTELOBOEREPO}:"
	@cd solarwinds_apm/extension; \
		for i in oboe.h oboe_api.h oboe_api.cpp oboe_debug.h; do \
			echo "Copying $$i"; \
			cp "${OTELOBOEREPO}/$$i" .; \
			if [ $$? -ne 0 ]; then echo " **** failed to copy $$i ****" ; exit 1; fi; \
		done
	@cd solarwinds_apm/extension; \
		echo "Copying oboe.i"; \
		cp "${OTELOBOEREPO}/swig/oboe.i" .; \
		if [ $$? -ne 0 ]; then echo " **** failed to copy oboe.i ****" ; exit 1; fi; \

# Copy bson header files from source specified in OTELOBOEREPO
copy-bson-headers:
	@echo -e "Copying bson header files (.hpp, .h)"
	@if [ ! -d solarwinds_apm/extension/bson ]; then \
		mkdir solarwinds_apm/extension/bson; \
		echo "Created solarwinds_apm/extension/bson"; \
	 fi
	@echo "Copying files from ${OTELOBOEREPO}:"
	@cd solarwinds_apm/extension/bson; \
		for i in bson.h platform_hacks.h; do \
			echo "Copying $$i"; \
			cp "${OTELOBOEREPO}/bson/$$i" .; \
			if [ $$? -ne 0 ]; then echo " **** fail to copy $$i ****" ; exit 1; fi; \
		done

# copy artifacts from local oboe
copy-all: copy-headers copy-liboboe

# Build the Python wrapper from liboboe headers inside build container
wrapper-from-local: check-swig copy-all
	@echo -e "Generating SWIG wrapper for C/C++ headers, from local neighbouring oboe checkout"
	@cd solarwinds_apm/extension && ./gen_bindings.sh

#----------------------------------------------------------------------------------------------------------------------#
# variable definitions and recipes for testing, linting, cleanup
#----------------------------------------------------------------------------------------------------------------------#

# Example: make tox OPTIONS="-e py37-nh-staging"
# Example: make tox OPTIONS="-e lint -- --check-only"
tox:
	@python3.8 -m tox $(OPTIONS)

format:
	@echo -e "Not implemented."

lint:
	@echo -e "Not implemented."

# clean up extension and intermediate build/dist files.
clean:
	@echo -e "Cleaning up extension and intermediate build/dist files."
	@cd solarwinds_apm/extension; rm -f _oboe* oboe* liboboe*so*; rm -rf bson
	@cd ..
	@find . -type f -name '*.pyc' -delete
	@find . -type d -name '__pycache__' | xargs rm -rf
	@find . -type d -name '*.ropeproject' | xargs rm -rf
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg*
	@rm -f MANIFEST
	@rm -rf docs/build/
	@rm -f .coverage.*
	@echo -e "Done."

# clean up tox files
clean-tox:
	@echo -e "Cleaning up tox files."
	@rm -rf .tox/
	@echo -e "Done."

.PHONY: nothing verify-oboe-version download-liboboe download-headers download-bson-headers download-all check-swig check-zip wrapper sdist manylinux-wheels package aws-lambda publish-lambda-layer-rc copy-liboboe copy-headers copy-bson-headers copy-all wrapper-from-local tox format lint clean
