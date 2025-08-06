# Dockerfile
FROM python:3.9-slim-buster 

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the start.sh script and make it executable
COPY start.sh .
RUN chmod +x start.sh

# Copy the application code
COPY app.py .
COPY models.py .
COPY extensions.py .
COPY routes.py .

# Copy static and templates directories
COPY static /app/static/
COPY templates /app/templates/

# Expose the port the app runs on
EXPOSE 3000

# Use the start.sh script as the entry point
CMD ["./start.sh"]