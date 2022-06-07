#!/bin/bash

set -ex

# configure dsyslog to send to logz.io
curl -sL https://qsdevops.s3-eu-west-1.amazonaws.com/rsyslog_install.sh | /bin/bash -s demoapp-server;

if [ -z "$(nodejs --version | grep -E 'v6.*')" ] ; then 
  echo 'Install NodeJs'
  curl -sL https://deb.nodesource.com/setup_6.x | /bin/bash -E;
  apt-get update && apt-get install --no-install-recommends --no-install-suggests -y nodejs;
fi

echo 'Unzip'
cd $ARTIFACTS_PATH;
tar -xvf demoapp-server.tar.gz;

echo 'Run App'
cd $ARTIFACTS_PATH;

set +ex

