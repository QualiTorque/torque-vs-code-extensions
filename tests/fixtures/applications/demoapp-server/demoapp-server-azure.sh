#!/bin/bash

set -e

echo 'Install NodeJs'
curl -sL https://deb.nodesource.com/setup_6.x | /bin/bash -E;
apt-get update -y;
apt-get install --no-install-recommends --no-install-suggests -y nodejs;

echo 'Unzip'
cd $ARTIFACTS_PATH;
tar -xvf demoapp-server.tar.gz;

echo 'Run App'
cd $ARTIFACTS_PATH;

set +e

