#!/bin/bash
set -e

echo 'Unzip'
cd $ARTIFACTS_PATH;
tar -xvf demoapp-server.tar.gz;

set +e