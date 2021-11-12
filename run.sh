#!/usr/bin/env bash

imageName="networks-mqtt-client"
dataDirName="data"
if [[ -z $(docker images --filter=reference=$imageName --format "{{.Repository}}") ]]; then
    docker build -t $imageName .
fi
echo "Image has been built"
[[ ! -x "run-client.sh" ]] && chmod +x run-client.sh
curDir=""
case "$(uname -s)" in
   Darwin|Linux)
     curDir=$PWD
     ;;
   CYGWIN*|MINGW32*|MSYS*|MINGW*)
     curDir=$(cd)
     ;;
   *)
     echo 'Other OS, please add a command for getting your current working directory'
     ;;
esac
echo "Current working directory: $curDir"
echo "Executing docker run with following arguments: $@"
port="5001"
if [[ $1 == "pub" ]]; then
    port="5002"
fi
docker run --rm --name mqtt-client-$1 -p $port:$port -v $curDir:/src $imageName $@