#!/usr/bin/env bash
# Copyright (c) Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

# Created with antsibull-docs 2.23.0

set -e

pushd "$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
trap "{ popd; }" EXIT

# Create collection documentation
mkdir -p rst
chmod og-w rst  # antsibull-docs wants that directory only readable by itself
antsibull-docs \
    --config-file antsibull-docs.cfg \
    collection \
    --cleanup everything \
    --use-current \
    --dest-dir rst \
    m1yag1.globus

# Fix title case in generated RST (antsibull-docs title-cases collection names)
find rst -name '*.rst' -exec sed -i '' 's/M1Yag1\.Globus/m1yag1.globus/g' {} \;
find rst -name '*.rst' -exec sed -i '' 's/M1yag1/m1yag1/g' {} \;

# Copy conf.py and index.rst into source directory for Sphinx
cp conf.py index.rst rst/

# Build Sphinx site
sphinx-build -M html rst _build -W --keep-going
