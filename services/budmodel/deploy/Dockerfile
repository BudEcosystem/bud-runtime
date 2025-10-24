FROM python:3.11.0

#dependency of GitPython
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y curl aria2 clamav clamav-daemon firejail && \
    curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y git-lfs && \
    git-lfs && \
    rm -rf /var/lib/apt/lists/*

# Update ClamAV virus database and clean temp files
RUN freshclam && rm -rf /tmp/* /var/tmp/*

RUN mkdir -p /var/run/clamav && \
    chown clamav:clamav /var/run/clamav && \
    chmod 750 /var/run/clamav

COPY clamd.conf.example /etc/clamav/clamd.conf

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --prefer-binary -r ./requirements.txt

# Install playwright
RUN playwright install

# Install playwright browsers
RUN playwright install-deps

COPY . .

RUN pip install --no-cache-dir .


# Install dependencies for playwright
# RUN apt-get install -y libgtk-3-0 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxi6 libxtst6 libnss3 libxrandr2 libasound2 libpangocairo-1.0-0 libatk1.0-0 libatk-bridge2.0-0 libepoxy0 libgbm-dev libxshmfence1

# Install xauth
# RUN apt-get install xauth
