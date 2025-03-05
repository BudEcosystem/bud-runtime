FROM node:21
WORKDIR /app
COPY . .
RUN npm i
RUN npm i pm2 -g
RUN npm run build
ENTRYPOINT["pm2", "start" , ""]

