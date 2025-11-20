# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables for non-interactive installs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    libgl1 \
	libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# We also install gunicorn, a professional web server for Django
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt gunicorn

# Copy the Django project into the container
COPY ./rag_webapp/ .

# Tell Docker that the container will listen on this port
EXPOSE 8000

# The command to run your application
# This uses Gunicorn, a production-ready server, instead of the dev server.
# It points to your project's wsgi file.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "rag_webapp.wsgi:application"]
