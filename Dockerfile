FROM openvino/ubuntu24_runtime:latest

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_BIN=python3

ARG SUBTITLE_EDIT_VERSION=4.0.13
ARG SUBTITLE_EDIT_ARCHIVE=SE4013.zip
ARG SUBTITLE_EDIT_SHA256=cf32b80696666f4fc2e44d07c1cfa48e8dcae90d8c381de3472598d66ab8af6a

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/tdarr-subtitle-ocr \
    PIP_NO_CACHE_DIR=1 \
    OCR_HOST=0.0.0.0 \
    OCR_PORT=8484 \
    OCR_ALLOWED_ROOTS=/media,/cache,/work \
    OCR_ALLOWED_EXTENSIONS=.sup,.sub,.idx,.mkv,.json,.png,.bmp,.jpg,.jpeg,.tif,.tiff,.webp \
    OCR_MAX_INPUT_SIZE_MB=256 \
    OCR_MAX_CONCURRENT_JOBS=1 \
    OCR_REQUEST_TIMEOUT_SECONDS=3600 \
    OCR_JOB_WORK_ROOT=/tmp/tdarr-subtitle-ocr \
    OCR_SUBTITLE_EDIT_BIN=/opt/subtitleedit/SubtitleEdit.exe \
    OCR_PREFERRED_ENGINE=auto \
    OCR_BACKEND_POLICY=auto \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends gnupg software-properties-common \
    && curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
      | gpg --dearmor -o /usr/share/keyrings/intel-openvino.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/intel-openvino.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu24 main" \
      > /etc/apt/sources.list.d/intel-openvino-2024.list \
    && add-apt-repository -y ppa:kobuk-team/intel-graphics \
    && add-apt-repository -y universe \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      ffmpeg \
      intel-gsc \
      intel-metrics-discovery \
      intel-opencl-icd \
      libgomp1 \
      libgl1 \
      libglib2.0-0 \
      libze-intel-gpu1 \
      libze1 \
      libstdc++6 \
      ocl-icd-libopencl1 \
      clinfo \
      mono-complete \
      openvino \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-osd \
      unzip \
    && ${PYTHON_BIN} -m pip install --upgrade pip setuptools wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
    
WORKDIR /opt/tdarr-subtitle-ocr

COPY requirements.txt /opt/tdarr-subtitle-ocr/requirements.txt
RUN pip install -r /opt/tdarr-subtitle-ocr/requirements.txt \
    && pip install openvino==2024.6.0 \
    && pip install --no-deps rapidocr-openvino==1.4.4

RUN curl -fsSL -o /tmp/subtitleedit.zip "https://github.com/SubtitleEdit/subtitleedit/releases/download/${SUBTITLE_EDIT_VERSION}/${SUBTITLE_EDIT_ARCHIVE}" \
    && echo "${SUBTITLE_EDIT_SHA256}  /tmp/subtitleedit.zip" | sha256sum -c - \
    && mkdir -p /opt/subtitleedit \
    && unzip -q /tmp/subtitleedit.zip -d /opt/subtitleedit \
    && rm -f /tmp/subtitleedit.zip

COPY src /opt/tdarr-subtitle-ocr/src
COPY client /opt/tdarr-subtitle-ocr/client

RUN install -d /opt/tdarr-subtitle-ocr/bin \
    && cp /opt/tdarr-subtitle-ocr/src/bin/auto_ocr_engine.py /opt/tdarr-subtitle-ocr/bin/auto_ocr_engine.py \
    && cp /opt/tdarr-subtitle-ocr/src/bin/gpu_ocr_engine.py /opt/tdarr-subtitle-ocr/bin/gpu_ocr_engine.py \
    && cp /opt/tdarr-subtitle-ocr/src/bin/subtitle_edit_engine.py /opt/tdarr-subtitle-ocr/bin/subtitle_edit_engine.py \
    && chmod +x /opt/tdarr-subtitle-ocr/bin/auto_ocr_engine.py \
    && chmod +x /opt/tdarr-subtitle-ocr/bin/gpu_ocr_engine.py \
    && chmod +x /opt/tdarr-subtitle-ocr/bin/subtitle_edit_engine.py \
    && chmod +x /opt/tdarr-subtitle-ocr/client/tdarr-ocr-client.sh \
    && useradd --system --create-home --uid 10001 tdarr \
    && mkdir -p /config /work /media /cache /tmp/tdarr-subtitle-ocr \
    && chown -R tdarr:tdarr /opt/tdarr-subtitle-ocr /config /work /media /cache /tmp/tdarr-subtitle-ocr

USER tdarr

EXPOSE 8484

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8484/healthz', timeout=3).read()"

CMD ["python3", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8484"]
