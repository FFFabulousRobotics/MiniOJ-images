ARG GRADLE_VERSION=9.1.0
FROM gradle:${GRADLE_VERSION}-jdk21

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
        python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG MINIOJ_VERSION=0.2.0
RUN python3 -m venv /opt/minioj \
    && /opt/minioj/bin/python -m pip install --no-cache-dir "minioj==${MINIOJ_VERSION}"

ENV PATH=/opt/minioj/bin:${PATH} \
    GRADLE_USER_HOME=/tmp/gradle-home \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /workspace
USER gradle
ENTRYPOINT ["minioj"]
CMD ["--help"]
