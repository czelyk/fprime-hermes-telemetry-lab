FROM python:3.12-bookworm@sha256:903c1a88edb0a18dbc4e02ef07545d18eefea9839ee40761266a640f8d5213d6
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/fprime-venv
ENV PATH="/opt/fprime-venv/bin:${PATH}"
COPY requirements.lock.txt /tmp/requirements.lock.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.lock.txt
WORKDIR /work
