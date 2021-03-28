FROM ubuntu:latest
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Los_Angeles

RUN apt-get update \
  && apt-get install -y python3 python3-pip python3-tk \
  && apt-get install -y libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-doc gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-alsa gstreamer1.0-gl gstreamer1.0-gtk3 gstreamer1.0-qt5 gstreamer1.0-pulseaudio \
  && apt-get install -y python3-gi \
  && apt-get install -y python3-gst-1.0 \
  && python3 -m pip install Pillow \
  && python3 -m pip install pyheif \
  && python3 -m pip install pygsheets \
  && python3 -m pip install pandas

WORKDIR /app
COPY show_media.py .
WORKDIR /media
ENTRYPOINT ["python3", "/app/show_media.py"]
