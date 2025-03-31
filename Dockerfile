# docker build -t caitest .
# docker run -it caitest

FROM ubuntu:24.04

# Update and install dependencies
RUN apt-get update && \
    apt-get install -y git python3-pip python3.12-venv

# Create virtual environment
RUN python3 -m venv cai
SHELL ["/bin/bash", "-c"]

# Create a directory for the application
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app/

# Install the package from the local directory
RUN source /cai/bin/activate && \
    pip install -e /app

# Set the default command to activate the virtual environment
CMD ["/bin/bash", "-c", "source /cai/bin/activate && bash"]
