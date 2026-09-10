# The portal's API, packaged so it runs identically on any server.
#
# Nothing in here is specific to Alok Ingots: all configuration arrives as
# environment variables at run time, so the same image can be used for a
# staging server and the real one without rebuilding.

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

# Dependencies first, so a code change does not reinstall them every build.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# The API runs as an unprivileged user. /app/storage is where customer
# documents are mounted, and must be writable by that user.
RUN useradd --system --uid 10001 portal \
    && mkdir -p /app/storage \
    && chown -R portal:portal /app

USER portal

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
