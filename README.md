# RTSP Streaming Server

A simple yet powerful RTSP (Real-Time Streaming Protocol) server that streams video files with automatic looping functionality. Built using GStreamer and Python, this server provides authenticated access to video streams over the network to allow remote access to video files.

## Features

- **Looping Video Playback**: Automatically loops video files continuously without interruption
- **Authentication**: Built-in basic authentication for secure access
- **H.264 Support**: Optimized for H.264 encoded video files
- **No Re-encoding**: Streams video using passthrough mode for minimal CPU usage
- **Network Streaming**: Access video streams from any RTSP-compatible client on your network

## Prerequisites

### System Requirements
- Python 3.6 or higher
- GStreamer 1.0
- GStreamer RTSP Server

### Installation

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-gi \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gir1.2-gst-rtsp-server-1.0
```

#### Fedora/RHEL
```bash
sudo dnf install -y \
    python3 \
    python3-pip \
    python3-gobject \
    gstreamer1 \
    gstreamer1-plugins-base \
    gstreamer1-plugins-good \
    gstreamer1-plugins-bad-free \
    gstreamer1-rtsp-server
```

## Usage

### Basic Usage

Stream a video file using default settings:

```bash
python3 rtsp_streamer.py --source /path/to/your/video.mp4
```

### Default Configuration

- **Port**: 8777
- **Mount Point**: /stream
- **Username**: admin
- **Password**: admin

### Accessing the Stream

Once the server is running, you can access the stream using any RTSP-compatible client:

**VLC Media Player**:
```
rtsp://admin:admin@localhost:8777/stream
```

**FFmpeg**:
```bash
ffplay rtsp://admin:admin@localhost:8777/stream
```

**GStreamer**:
```bash
gst-launch-1.0 rtspsrc location=rtsp://admin:admin@localhost:8777/stream latency=0 ! decodebin ! autovideosink
```

### Remote Access

To access the stream from another machine on your network, replace `localhost` with the server's IP address:

```
rtsp://admin:admin@192.168.1.100:8777/stream
```

## Sample Videos

The repository includes two sample video files for testing:
- `sample_test.mp4` - General test video
- `arm_revolving.mp4` - Arm revolving demonstration video

Example:
```bash
python3 rtsp_streamer.py --source sample_test.mp4
```

## How It Works

The RTSP server uses the following GStreamer pipeline:

```
filesrc → qtdemux → h264parse → rtph264pay → RTSP
```

1. **filesrc**: Reads the video file from disk
2. **qtdemux**: Demuxes the MP4 container to extract H.264 video stream
3. **h264parse**: Parses H.264 elementary stream
4. **rtph264pay**: Packages H.264 into RTP packets for streaming
5. **RTSP**: Delivers the stream via RTSP protocol

### Looping Mechanism

The server implements automatic looping by:
1. Monitoring the GStreamer pipeline for End-of-Stream (EOS) events
2. Intercepting EOS events before they reach the client
3. Performing a seek operation back to timestamp 0
4. Continuing playback seamlessly

## Troubleshooting

### Missing GStreamer Dependencies

If you encounter an error about missing GStreamer dependencies:

```
Error: Missing GStreamer dependencies.
Please install: gir1.2-gst-rtsp-server-1.0
```

Make sure you've installed all the required packages listed in the Prerequisites section.

### Source File Not Found

Ensure the video file path is correct:
```bash
# Use absolute path
python3 rtsp_streamer.py --source /absolute/path/to/video.mp4

# Or relative path
python3 rtsp_streamer.py --source ./sample_test.mp4
```

### Connection Refused

If clients can't connect:
1. Check if the server is running without errors
2. Verify the port (8777) is not blocked by a firewall
3. Ensure the server's IP address is accessible from the client machine

### Authentication Failures

Double-check the username and password in your RTSP URL:
```
rtsp://admin:admin@<server-ip>:8777/stream
      ^^^^^ ^^^^^
      user  pass
```

## Technical Details

### Video Format Compatibility

The server is optimized for H.264 encoded MP4 files. For other formats, you may need to modify the GStreamer pipeline in `rtsp_streamer.py`.

### Performance

The server uses **passthrough mode** (no re-encoding), which means:
- Minimal CPU usage
- Low latency
- Preservation of original video quality
- Multiple clients can connect simultaneously with minimal performance impact

## License

This project is open source. Please check the repository for license information.

## Repository

GitHub: [leonardograndosilveira/rtsp_streaming](https://github.com/leonardograndosilveira/rtsp_streaming)

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Author

Leonardo Grando Silveira
