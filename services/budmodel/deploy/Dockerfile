FROM python:3.11.0

#dependency of GitPython
RUN apt-get update && apt-get install -y curl aria2 && \
    curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash && \
    apt-get install -y git-lfs && \
    git-lfs

RUN apt-get install -y clamav clamav-daemon

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y firejail
# Update ClamAV virus database
RUN freshclam

RUN mkdir -p /var/run/clamav && \
    chown clamav:clamav /var/run/clamav && \
    chmod 750 /var/run/clamav

COPY clamd.conf.example /etc/clamav/clamd.conf

WORKDIR /app
COPY . .

RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt
RUN pip install .

RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt

# Install playwright
RUN playwright install

# Install playwright browsers
RUN playwright install-deps

# Install dependencies for playwright
# RUN apt-get install -y libgtk-3-0 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxi6 libxtst6 libnss3 libxrandr2 libasound2 libpangocairo-1.0-0 libatk1.0-0 libatk-bridge2.0-0 libepoxy0 libgbm-dev libxshmfence1

# Install xauth
# RUN apt-get install xauth
