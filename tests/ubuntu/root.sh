#!/bin/bash

set -e

# python, git, openssl etc
apt-get update
apt-get -y install python3 python3-dev python3-venv python3-pip 
apt-get -y install openssl ca-certificates curl gnupg lsb-release
apt-get -y install git-all


# docker

test -d /etc/apt/keyrings || mkdir -p /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list

apt-get -y update
apt-get -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-compose


# cairo and imagemagick
apt-get -y install libcairo2-dev imagemagick fonts-dejavu

# pipenv
pip install --no-input pipenv

# node
curl -sL https://deb.nodesource.com/setup_14.x -o nodesource_setup.sh
bash nodesource_setup.sh

apt-get -y install gcc g++ make
apt-get -y install nodejs


# create repo user
adduser --disabled-password --gecos "" repo
usermod -aG docker repo

