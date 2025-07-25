# 🥡 Deployment Setup

Welcome to the land of hassle-free deployments! This section is all about making your life easier when setting up and
running your microservices across different environments—whether it’s development, testing, or production. Let’s break
it down:

### 🛒 Key Components

- `.dapr/components/`: This is your treasure chest of Dapr configurations. Inside, you’ll find files like
  `configstore.yaml`, `local-secretstore.yaml`, and `pubsub.yaml`. These gems ensure that your microservices play nice
  with external resources, making integration smooth and seamless.
- `.dapr/appconfig-dev.yaml`: Think of this as the brains behind your Dapr sidecar in a development environment. It
  manages how your app talks to other services, handles state, and keeps everything in check for your development setup.
  It’s like having a super-organized project manager for your microservices!
- `dapr-local.yaml`: This file is your backstage pass to running the show in a local development environment. It covers
  everything from environment variables to port settings and entry commands, ensuring that your local setup is as smooth
  as butter.
- `deploy/docker-compose-*.yaml`: Inside the `deploy/` directory, these Docker Compose files are the secret sauce for
  spinning up your entire application stack. They handle everything—from the Dapr sidecar to placement services and any
  other resources your app needs. Just toss them in, and you’re good to go!
- `deploy/start_dev.sh`, `deploy/stop_dev.sh`: These scripts are your personal assistants for managing the application
  lifecycle. Want to start the app and all its dependencies? Just run `start_dev.sh`. Need to stop it? `stop_dev.sh` has
  got you covered. They make orchestrating your app and Dapr components a breeze!

### 🤔 Why This Matters

These scripts and configurations are like the ultimate deployment toolkit, designed to keep your process consistent,
reliable, and—most importantly—stress-free. You could manually juggle all these components, but why would you when this
setup does all the heavy lifting for you? It lets you focus on what really matters: building awesome features, not
wrangling with complex setups.

**Pro Tip**: Always prefer the **Build & Deploy** step for everything, including local development. It’s
your one-stop solution to ensure everything runs smoothly without the need to manually tweak configurations.

Remember, the easier your deployment process, the more time you have for the fun stuff—like coding, or, you know, maybe
taking a break! 😉

## Table of Contents

- [Pre-Requisites](#-pre-requisites)
- [Build & Deploy](#-build--deploy)
    - [Build Configuration](#-build-configuration)
    - [Component & Resource Configurations](#-component--resource-configurations)
    - [Deploy Configurations](#-deploy-configurations)
    - [Deploy Scripts](#-deploy-scripts)
- [Local Setup & Troubleshooting](#-local-setup--troubleshooting)
- [Service Invocation](#-service-invocation)

## 🤌 Pre-Requisites

- [Docker](https://docs.docker.com/engine/install/) >= 27.1.1
- [Dapr Runtime](https://docs.dapr.io/getting-started/install-dapr-cli/) >= 1.13.5
- [Dapr CLI](https://docs.dapr.io/getting-started/install-dapr-cli/) >= 1.13.0
- [Pre-Commit Hooks](./hooks_and_workflows.md)

## 😋 Build & Deploy

This section is your go-to guide for the scripts and configuration files that make deploying your application a breeze.
Designed with flexibility in mind, these configurations can be easily adapted to suit various project needs. From
environment variables to Dapr components and Docker Compose files, you’ll find everything you need to tailor your
microservices just right.

### 🧑‍🌾 Component & Resource Configurations

#### Dapr Components

The Dapr components, are preconfigured and defined in the`.dapr/components` folder. These configurations are critical to
the functioning of your microservice, handling tasks like state management, pub/sub, and secret management.

- **No Need for Modifications**: Generally, there’s no need to alter these configuration files. They are set up to work
  seamlessly with the deployment setup provided by PyGuard.
- **Local Development Adjustments**: If you need to make changes for local development that don’t affect the deployment,
  you can copy the `.dapr/components` folder to `.dapr/components-local` and make your adjustments there. This folder is
  specifically for local changes and should not be pushed to the repository.

More details about each component can be found in their respective sections, ensuring you have all the information you
need to understand and manage your microservice's infrastructure effectively.

#### Redis

Redis is your trusty sidekick for managing config and state storage, and it might even handle pub/sub duties depending
on your app's scale. Fire up Redis with `deploy/docker-compose-redis.yaml` (🛑 Stoooop!!! don't do this yet, wait till
the end). Since authentication is a must, make sure to
set the `REDIS_PASSWORD` environment variable.

Got more resources your project needs that aren't included with PyGuard? No problem! Just create a new compose file
using this naming style: `deploy/docker-compose-<resource_name>.yaml`.

### 🧑‍🍳 Build Configuration

The `deploy/Dockerfile` is where the magic happens—it’s the blueprint for building your Docker images. This file is
essential and must be configured for each project. Here’s a simple example:

```dockerfile
FROM python:3.11.0

RUN mkdir /app/
COPY .. /app/

WORKDIR /app
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r ./requirements.txt

```

For most projects, this should do the trick. Need more tweaks or dependencies? Go ahead and modify, but remember: the
`WORKDIR` should always stay as `/app/`.

### 🥘 Deploy Configurations

The `deploy/docker-compose-dev.yaml` file is the backbone of your deployment setup. It rolls out your entire application
stack—including the app, Dapr sidecar, placement service, and any other needed resources. This file is non-negotiable
for every project, and here’s how to get it right:

- **Services**: The core trio—your app, Dapr sidecar, and placement service—are already configured with all the
  essentials: names, environment variables, commands, networks, volumes, and ports. Stick to the naming conventions
  provided, and only tweak things like environment variables or ports when necessary. Most of the time, you’ll only need
  to adjust the app service’s environment settings.
- **Link resource compose files**: This deployment file is designed to spin up all necessary services and resources.
  Instead of cluttering it with direct service additions, we recommend reusing the existing resource compose files by
  simply including them.
  ```dockerfile
  include:
    - ./docker-compose-redis.yaml
  
  services:
    ...
  ```
- **Dapr Application Config**: The Dapr application configuration is defined in `.dapr/appconfig-dev.yaml`, specifying
  the Dapr sidecar settings. We don't recommend changing this file since it already contains the essential
  configurations needed for most environments. However, if you need to make changes specifically for local development,
  you can create a `.dapr/appconfig-local.yaml` file and make your adjustments there.

### 🍲 Deploy Scripts

- `deploy/start_dev.sh` - Your handy helper script for setting up environment variables and spinning up the specified
  Docker Compose file. If you have made local adjustments and are using a `.dapr/components-local` directory, make sure
  to specify it using the `--dapr-components ../.dapr/components-local` option. Similarly, if you have created an
  `appconfig-local.yaml` file, specify it with `--dapr-app-config ../.dapr/appconfig-local.yaml`. Need more help? Just
  run `./deploy/start_dev.sh --help`.
- `deploy/stop_dev.sh` - This script gracefully shuts down your deployment using the specified Docker Compose file,
  which is especially useful if you’ve got things running in the background. For usage details,
  run `./deploy/stop_dev.sh --help`.

**Pro Tip**: It’s mandatory and strongly recommended to use these deploy scripts for all your deployment tasks, even in
local development. They’ll make sure your environment variables are set up correctly without the need to hardcode them
in your Docker Compose files.

If your local development needs diverge from the standard `deploy/docker-compose-dev.yaml`, feel free to create a custom
file using the naming convention: `deploy/docker-compose-local.yaml`, `deploy/docker-compose-redis-local.yaml`, etc. Any
file with a `-local` suffix is strictly for local development and should not be pushed to the repo. This way, your dev
environment stays neat and separate, while your deployment process remains smooth and consistent.

## 🙅‍♂️ Local Setup & Troubleshooting

### 🚨 Quick Heads-Up!

We highly recommend sticking to `deploy/docker-compose-dev.yaml` for all your development needs, as explained in the
[Build & Deploy section](#-build--deploy). It’s the smoothest path to getting things up and running. Unless you're on a
🥔 potato PC or don't have the time to wait for those builds, trust us, this is the way to go! 🥱

### 🤨 Need to Troubleshoot? Here’s a Quick & Dirty Local Setup

This part is totally optional and should only be used if you want to initialize Dapr locally without Docker builds for
some quick troubleshooting. While it might seem convenient for a quick fix, remember this method requires you to run the
Dapr sidecar and other related components separately. If you skip this, your Dapr integrations won't play nice.

### 🤓 Initialize dapr

First things first, you need to get Dapr running locally. Follow the
official [Dapr installation guide](https://docs.dapr.io/getting-started/install-dapr-selfhost/) to set it up. Once
done, you should be able to run `dapr --version` from your CLI, and the following containers will be up and running:

- **Redis container**: Used as a config, state store, and message broker.
- **Zipkin container**: For observability—so you know what’s going on.
- **Dapr placement service container**: Essential for local actor support.

### 🫢 Prepare Configurations

Your `.dapr/appconfig-dev.yaml` holds the dapr sidecar configuration, while `.dapr/components` contains the component
configurations. These files are crucial for running your app and any related Dapr resources. If you're feeling
adventurous and not using the provided Docker Compose files in the `deploy` directory, you'll likely need to tweak these
configurations.

**Pro Tip**: If you need to make changes to `.dapr/appconfig-dev.yaml` for your local setup, create a
`.dapr/appconfig-local.yaml` instead. This keeps your changes isolated, and you guessed it—don't push this file to the
repo!

For more details on app configuration, check out the
official [Dapr configuration overview](https://docs.dapr.io/operations/configuration/configuration-overview/).

### 🫠 Run the application

For those of you brave enough to handle it manually, your run configurations should be defined in a `dapr-local.yaml`
file. This file isn't mandatory and is mainly for quick troubleshooting and testing. Here’s an example of what it might
look like:

```yaml
version: 1
apps:
  - appID: pyguard
    appDirPath: .
    resourcesPaths: [ .dapr/components ]
    configFilePath: .dapr/appconfig-dev.yaml
    appChannelAddress: 127.0.0.1
    appProtocol: http
    appPort: 9081
    appHealthCheckPath: "/healthz"
    daprHTTPPort: 3500
    command: [ "uvicorn","pyguard.main:app", "--port", "9081" ]
    logLevel: DEBUG
    env:
      NAMESPACE: development
      LOG_LEVEL: DEBUG
      DAPR_API_TOKEN: ""
      CONFIGSTORE_NAME: configstore
      SECRETSTORE_NAME: "local-secretstore"
```

Tweak the configurations as needed, but be careful not to expose any sensitive information. And yep, this file shouldn't
be pushed to the repo either!

Before you kick things off, ensure that the required resources and Dapr placement services are running. Then, start your
app with the following command:

```shell
dapr run -f dapr-local.yaml
```

For more info on using dapr run, check out the
official [Dapr multi-app run guide](https://docs.dapr.io/developing-applications/local-development/multi-app-dapr-run/multi-app-template/).

### ⚠️ One Last Thing: Stick to the Plan

We can’t stress this enough: Use the Build & Deploy steps as your go-to method. It’s smoother, cleaner, and far less
likely to result in a debugging nightmare. This local setup is like a fire extinguisher—only break the glass if you
really need it. 🧯

## 🍜 Service Invocation

So, you’ve made it to the final step—invoking your service! If you followed the **Build & Deploy** path (which, let’s be
honest, you really should have), your app will be running on the `APP_PORT` you set. By default, that’s port **3510**.
Access it just like any other FastAPI setup.

### 🚀 FastAPI Invocation

If you’re familiar with FastAPI, you already know the drill. Point your browser or your HTTP client to the designated
port, and you’re in! Not sure how to do that? Check out the [FastAPI docs](https://fastapi.tiangolo.com/#check-it) for
all the juicy details.

### 🙆‍♂️ Local Setup

Now, if you decided to go rogue and use the Local Setup method, you’ll need to use whatever port you configured. It’s
all on you now, so remember the port number you chose!

### 🍱 Production Invocation

When you’re ready for prime time in production, your app won’t be invoked directly. Instead, it will be summoned through
the Dapr sidecar’s invoke endpoint. It’s like having a magical gateway that handles all the heavy lifting. Want to dive
into the details?
The [Dapr docs](https://docs.dapr.io/developing-applications/building-blocks/service-invocation/howto-invoke-discover-services/)
have got you covered.

### 💡 Quick Tips

- **Build & Deploy Step**: Always your best bet for a smooth ride. Stick with it, and you’ll have your app running in no
  time.
- **Local Setup**: Great for quick troubleshooting, but be sure to keep track of those custom configs!
- **Dapr Sidecar**: Your gateway to the production world. Don’t forget to check out the docs if you’re curious about how
  it all works.

Now, go forth and invoke those services like a pro! 🚀