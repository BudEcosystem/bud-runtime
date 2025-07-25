# Use a lightweight official Python base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
# This layer is cached unless requirements.txt changes, speeding up builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application script into the container
COPY app.py .

# Expose the port that the intermediary service will listen on
# This port is where the aibrix.ai autoscaler will scrape metrics
EXPOSE 9090

# --- Optional: Create a non-root user for security ---
# Running as root inside a container is generally discouraged.
# We define a user and group ID (arbitrary, common practice)
# and switch to this user.
# Update the script permissions below if needed after switching user.
ARG UID=10001
RUN adduser --system --uid $UID --no-create-home appuser
USER appuser
# ------------------------------------------------------

# Command to run the application when the container starts
# Assuming your intermediary.py script reads the LISTEN_PORT ENV var
CMD ["python", "app.py"]