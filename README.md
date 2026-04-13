# Tdarr Subtitle OCR Sidecar

External OCR sidecar for Tdarr image-based subtitles with secure HTTP execution, Subtitle Edit compatibility fallback, and accelerator auto-detection for NVIDIA CUDA, Intel iGPU/Arc, and Intel NPU via OpenVINO.

## Features

- secure OCR sidecar for Tdarr external tool execution
- bearer-token protected HTTP API
- allow-listed filesystem roots and extensions
- non-root container runtime
- read-only-container-friendly design
- NVIDIA CUDA OCR auto-detection
- Intel iGPU / Arc OpenVINO OCR auto-detection
- Intel NPU OpenVINO detection and backend selection support
- Subtitle Edit fallback for direct `.sup`, `.sub`, `.idx`, and `.mkv` subtitle-container OCR
- exported Tdarr client wrapper script for `OCR Tool Path`
- unRAID-friendly Docker and template examples

## Repo layout

- `Dockerfile`
- `Dockerfile.intel`
- `requirements.txt`
- `src/`
- `client/`
- `examples/`

## Backend selection

The default backend policy is `auto`.

Behavior:

- raster image or OCR-manifest JSON input:
  - prefer NVIDIA CUDA when available
  - otherwise prefer Intel OpenVINO GPU when available
  - otherwise prefer Intel OpenVINO NPU when available
  - otherwise fall back to Subtitle Edit if allowed
- subtitle-container input like `.sup`, `.sub`, `.idx`, or `.mkv`:
  - use Subtitle Edit because it remains the safest bundled parser/OCR path for those formats

Control variables:

- `OCR_BACKEND_POLICY=auto|nvidia|intel|npu|subtitleedit`
- `OCR_BACKEND_STRICT=true|false`

If `OCR_BACKEND_STRICT=true`, the service fails instead of falling back when the requested GPU backend cannot run.

## Build

Build from the repo root:

```bash
docker build -t local/tdarr-subtitle-ocr:latest .
```

Dedicated Intel/OpenVINO build from the repo root:

```bash
docker build -f Dockerfile.intel -t local/tdarr-subtitle-ocr:intel .
```

## Tdarr Integration

This sidecar is meant to work with a Tdarr subtitle flow that supports an external OCR tool path.

High-level flow:

1. Tdarr extracts the selected image subtitle stream to a shared path
2. Tdarr calls `tdarr-ocr-client.sh`
3. the client sends the OCR request to this sidecar
4. the sidecar validates paths and runs OCR
5. the generated `.srt` is written back to the shared path

## unRAID Installation

Two common ways to install on unRAID:

1. build the image yourself and create the container manually
2. build the image yourself and use the provided unRAID XML template as a starting point

Files provided:

- `examples/docker-compose.yml`
- `examples/docker-compose.intel.yml`
- `examples/unraid-template.xml`

### Prerequisites

- unRAID server with Docker enabled
- Tdarr server and node already working
- shared paths available to both Tdarr and this OCR sidecar
- for NVIDIA:
  - NVIDIA GPU installed
  - NVIDIA driver/plugin/runtime configured on unRAID
- for Intel iGPU or Arc:
  - `/dev/dri` available on the host
  - Intel GPU stack working on unRAID
- for Intel NPU:
  - `/dev/accel` available on the host
  - host kernel/driver support for the platform NPU

### Path planning

The safest setup is to mount the same host paths into both `Tdarr_Node` and this OCR sidecar using the same container paths.

Example shared paths:

- `/mnt/user/media` -> `/media`
- `/mnt/user/cache` -> `/cache`
- `/mnt/user/appdata/tdarr-node/transcode_cache` -> `/work`

### Option A: Build and run manually on unRAID

#### 1. Place the repo on your unRAID host

Copy this standalone repo to a location on unRAID, for example:

- `/mnt/user/appdata/tdarr-subtitle-ocr-repo`

#### 2. Build the image

From an unRAID terminal:

```bash
cd /mnt/user/appdata/tdarr-subtitle-ocr-repo
docker build -t local/tdarr-subtitle-ocr:latest .
```

For the dedicated Intel-focused image:

```bash
cd /mnt/user/appdata/tdarr-subtitle-ocr-repo
docker build -f Dockerfile.intel -t local/tdarr-subtitle-ocr:intel .
```

#### 3. Create the container

Example equivalent settings:

- image: `local/tdarr-subtitle-ocr:latest`
- port: `8484`
- appdata path: `/mnt/user/appdata/tdarr-subtitle-ocr` -> `/config`
- media path: `/mnt/user/media` -> `/media`
- cache path: `/mnt/user/cache` -> `/cache`
- Tdarr temp/work path: `/mnt/user/appdata/tdarr-node/transcode_cache` -> `/work`

Recommended extra parameters:

```text
--read-only --tmpfs /tmp:size=512m,mode=1777 --cap-drop=ALL --security-opt=no-new-privileges:true --pids-limit=256
```

Recommended environment variables:

```text
PUID=99
PGID=100
OCR_API_TOKEN=change-this-to-a-long-random-token
OCR_COPY_CLIENT_DIR=/config/client
OCR_ALLOWED_ROOTS=/media,/cache,/work
OCR_ALLOWED_EXTENSIONS=.sup,.sub,.idx,.mkv,.json,.png,.bmp,.jpg,.jpeg,.tif,.tiff,.webp
OCR_BACKEND_POLICY=auto
OCR_BACKEND_STRICT=false
OCR_MAX_CONCURRENT_JOBS=1
OCR_MAX_INPUT_SIZE_MB=256
```

On unRAID, `PUID=99` and `PGID=100` match the default `nobody:users` ownership of appdata shares. That lets the container create `/config/client` without having to pre-create it manually or open the folder up with `777`.

For NVIDIA add:

```text
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

For Intel add:

- pass `/dev/dri` into the container
- pass `/dev/accel` into the container for NPU-capable Intel systems
- if unRAID still reports only CPU, confirm the host itself exposes `/dev/dri/renderD*`
- restart the container after adding the device mapping

### Option B: Use the template as a starting point

Use:

- `examples/unraid-template.xml`

This template is intended as a starting point. You may still want to adjust host paths and environment variables for your setup.

The template includes an icon URL that points at:

- `examples/assets/tdarr-subtitle-ocr-icon.svg`
- an optional `/dev/dri` path mapping for Intel GPU passthrough
- an optional `/dev/accel` path mapping for Intel NPU passthrough

### Verify the container

Open in a browser:

- `http://YOUR-UNRAID-IP:8484/healthz`

You should see JSON reporting:

- `ok: true`
- backend policy
- allowed roots
- accelerator detection results for NVIDIA and Intel

For Intel GPU acceleration, the healthy target is an `intel.available: true` result. If you see `OpenVINO did not report a GPU device: ['CPU']`, the container is running but OpenVINO still cannot see an Intel GPU from inside the container.

For Intel NPU acceleration, the healthy target is an `npu.available: true` result and `openvinoAvailableDevices` including `NPU`.

## Tdarr Node Setup

### 1. Export the client wrapper

Set this environment variable on the OCR sidecar:

```text
PUID=99
PGID=100
OCR_COPY_CLIENT_DIR=/config/client
```

On startup, the sidecar copies:

- `client/tdarr-ocr-client.sh`

into:

- `/config/client/tdarr-ocr-client.sh`

### 2. Mount the exported client into Tdarr_Node

Mount the host folder backing `/config/client` into `Tdarr_Node`, for example:

- host: `/mnt/user/appdata/tdarr-subtitle-ocr/client`
- container: `/external-tools/tdarr-ocr`

Then Tdarr will see:

- `/external-tools/tdarr-ocr/tdarr-ocr-client.sh`

### 3. Set Tdarr node environment variables

Add these to `Tdarr_Node`:

```text
TDARR_OCR_ENDPOINT=http://tdarr-subtitle-ocr:8484/v1/ocr
TDARR_OCR_API_TOKEN=change-this-to-the-same-token
TDARR_OCR_TIMEOUT_SECONDS=3700
```

If your OCR sidecar container name is different, update the hostname accordingly.

### 4. Configure the Tdarr flow node

In the subtitle flow node:

- `Enable OCR For Image Subs`: `true`
- `OCR Tool Path`: `/external-tools/tdarr-ocr/tdarr-ocr-client.sh`
- `OCR Args Template`: `--input {input} --output {output} --language {language}`

### 5. Test with one file first

Run the flow against a single file with a PGS subtitle stream and confirm:

- the OCR sidecar receives the request
- the output `.srt` is created
- Tdarr remuxes the generated subtitle correctly

## Docker Compose Example

See:

- `examples/docker-compose.yml`
- `examples/docker-compose.intel.yml`

The compose example includes:

- `read_only: true`
- `/tmp` mounted as `tmpfs`
- dropped Linux capabilities
- `no-new-privileges`
- NVIDIA environment variables
- `/dev/dri` mapping for Intel
- optional `/dev/accel` mapping for Intel NPU

## Environment variables

- `OCR_API_TOKEN`: optional bearer token
- `PUID`: runtime user ID for bind-mounted storage ownership alignment
- `PGID`: runtime group ID for bind-mounted storage ownership alignment
- `OCR_ALLOWED_ROOTS`: comma-separated allow-list of readable/writable roots
- `OCR_ALLOWED_EXTENSIONS`: accepted input extensions
- `OCR_MAX_INPUT_SIZE_MB`: default `256`
- `OCR_MAX_CONCURRENT_JOBS`: default `1`
- `OCR_REQUEST_TIMEOUT_SECONDS`: default `3600`
- `OCR_COPY_CLIENT_DIR`: exports the Tdarr client wrapper to persistent storage
- `OCR_BACKEND_COMMAND`: defaults to the auto-dispatcher
- `OCR_BACKEND_POLICY`: `auto`, `nvidia`, `intel`, `npu`, or `subtitleedit`
- `OCR_BACKEND_STRICT`: force failure instead of fallback
- `OCR_SUBTITLE_EDIT_BIN`: default `/opt/subtitleedit/SubtitleEdit.exe`

## Security model

- no shell execution for OCR requests
- allow-listed filesystem roots only
- allow-listed file extensions only
- optional bearer authentication
- non-root container user
- compatible with read-only root filesystem
- temporary working files isolated under `/tmp/tdarr-subtitle-ocr`

## Limitations

- direct `.sup` parsing still falls back to Subtitle Edit for now
- the GPU engines currently operate on raster-image inputs or OCR-manifest JSON inputs
- Intel NPU execution depends on host driver support and current OpenVINO device availability
- only English Tesseract data is installed by default in the image
- for additional OCR languages, add the relevant Tesseract packages or mount your own tessdata set

## References

- [NVIDIA Container Toolkit Docker GPU exposure](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)
- [OpenVINO GPU device availability](https://docs.openvino.ai/2023.3/notebooks/108-gpu-device-with-output.html)
- [OpenVINO Intel GPU configuration](https://docs.openvino.ai/2023.3/openvino_docs_install_guides_configurations_for_intel_gpu.html)
- [Subtitle Edit releases](https://github.com/SubtitleEdit/subtitleedit/releases)
