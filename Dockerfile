FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

RUN addgroup --system arms && adduser --system --ingroup arms --home /home/arms arms

ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r "${REQUIREMENTS}"

COPY . .

RUN SECRET_KEY=collectstatic-only \
    ALLOWED_HOSTS=localhost \
    DATABASE_URL=sqlite://:memory: \
    python manage.py collectstatic --noinput \
    && mkdir -p /app/media \
    && chown -R arms:arms /app/media /app/staticfiles

USER arms

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
