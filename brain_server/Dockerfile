FROM nvcr.io/nvidia/pytorch@sha256:d724ba5b68075cd3b96eefbc510a45d36e60dd16fd70b217708625f1f4b37bc1
USER root
RUN python3 -m venv /opt/reflexguard-venv
COPY brain_server/requirements.txt /tmp/reflexguard-requirements.txt
# The NVIDIA constraints govern its base environment. This clean venv has its
# own complete hash lock; the base site-packages are not put on sys.path.
RUN PIP_CONSTRAINT= /opt/reflexguard-venv/bin/python -m pip install --require-hashes -r /tmp/reflexguard-requirements.txt
RUN /opt/reflexguard-venv/bin/python -c "import pathlib; source=pathlib.Path('/usr/local/lib/python3.12/dist-packages'); target=pathlib.Path('/opt/reflexguard-venv/lib/python3.12/site-packages'); names=['torch','functorch','torchgen']; names += [p.name for p in source.glob('torch-*.dist-info')]; [(target/name).symlink_to(source/name) for name in names]"
WORKDIR /app
COPY src /app/src
COPY brain_server /app/brain_server
COPY scripts/check_gpu.py /app/check_gpu.py
ENV PYTHONPATH=/app/src:/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
ENTRYPOINT ["/opt/reflexguard-venv/bin/python", "-m", "brain_server"]
