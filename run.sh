#! /bin/bash
docker run -it -v $(pwd):/media -v $HOME/.google:/root/.google -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$DISPLAY --device /dev/snd media_tools:latest "$@"
