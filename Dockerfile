FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_BIN=python3
ARG INTEL_IGC_VERSION=v2.30.1
ARG INTEL_IGC_BUILD=2.30.1+20950
ARG INTEL_COMPUTE_RUNTIME_VERSION=26.09.37435.1
ARG INTEL_GMM_VERSION=22.9.0

ARG SUBTITLE_EDIT_VERSION=4.0.13
ARG SUBTITLE_EDIT_ARCHIVE=SE4013.zip
ARG SUBTITLE_EDIT_SHA256=cf32b80696666f4fc2e44d07c1cfa48e8dcae90d8c381de3472598d66ab8af6a

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/tdarr-subtitle-ocr \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
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

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      ffmpeg \
      libgomp1 \
      libgl1 \
      libglib2.0-0 \
      libstdc++6 \
      ocl-icd-libopencl1 \
      mono-complete \
      python3 \
      python3-pip \
      python3-venv \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-osd \
      unzip \
    && install -d /tmp/intel-gpu \
    && curl -fsSL -o /tmp/intel-gpu/intel-igc-core-2.deb "https://github.com/intel/intel-graphics-compiler/releases/download/${INTEL_IGC_VERSION}/intel-igc-core-2_${INTEL_IGC_BUILD}_amd64.deb" \
    && curl -fsSL -o /tmp/intel-gpu/intel-igc-opencl-2.deb "https://github.com/intel/intel-graphics-compiler/releases/download/${INTEL_IGC_VERSION}/intel-igc-opencl-2_${INTEL_IGC_BUILD}_amd64.deb" \
    && curl -fsSL -o /tmp/intel-gpu/intel-ocloc.deb "https://github.com/intel/compute-runtime/releases/download/${INTEL_COMPUTE_RUNTIME_VERSION}/intel-ocloc_${INTEL_COMPUTE_RUNTIME_VERSION}-0_amd64.deb" \
    && curl -fsSL -o /tmp/intel-gpu/intel-opencl-icd.deb "https://github.com/intel/compute-runtime/releases/download/${INTEL_COMPUTE_RUNTIME_VERSION}/intel-opencl-icd_${INTEL_COMPUTE_RUNTIME_VERSION}-0_amd64.deb" \
    && curl -fsSL -o /tmp/intel-gpu/libigdgmm12.deb "https://github.com/intel/compute-runtime/releases/download/${INTEL_COMPUTE_RUNTIME_VERSION}/libigdgmm12_${INTEL_GMM_VERSION}_amd64.deb" \
    && curl -fsSL -o /tmp/intel-gpu/libze-intel-gpu1.deb "https://github.com/intel/compute-runtime/releases/download/${INTEL_COMPUTE_RUNTIME_VERSION}/libze-intel-gpu1_${INTEL_COMPUTE_RUNTIME_VERSION}-0_amd64.deb" \
    && apt-get install -y --no-install-recommends /tmp/intel-gpu/*.deb \
    && ${PYTHON_BIN} -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/tdarr-subtitle-ocr

COPY requirements.txt /opt/tdarr-subtitle-ocr/requirements.txt
RUN pip install -r /opt/tdarr-subtitle-ocr/requirements.txt

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

CMD ["python", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8484"]
